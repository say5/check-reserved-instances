#!/usr/bin/env python


"""Compare instance reservations and running instances for AWS services and send metrics to DataDog"""
import boto3
import click
import datetime

from collections import defaultdict
from datadog import initialize
from datadog import statsd

@click.command()
@click.option('--dd-host', default='127.0.0.1', help='DataDog statd host')
@click.option('--dd-port', default=8125, help='DataDog statd host')
@click.option('--dd-metric', default='aws', help='DataDog metric prefix')
@click.option('--aws-region', default='us-east-1', help='Region we get statistic for')
@click.option('--aws-access-key', default=None, help='AWS access key')
@click.option('--aws-access-secret', default=None, help='AWS access secret')
@click.option('--check-ec2', default=True, help='Check EC2 instances')
@click.option('--check-rds', default=True, help='Check RDS instances')
@click.option('--check-elc', default=True, help='Check ElastiCache instances')


def cli(dd_host, dd_port, dd_metric,
        aws_region, aws_access_key, aws_access_secret,
        check_ec2, check_rds, check_elc):
    """
    Compare instance reservations and running instances for AWS services.

    """
    options = {
        'statsd_host' : dd_host,
        'statsd_port' : dd_port
    }
    initialize(**options)
    diff = {}
    if check_ec2:
        diff.update(calculate_ec2_ris(aws_region, aws_access_key, aws_access_secret))
        send_metrics(dd_metric, diff, 'EC2')
    if check_rds:
        diff.update(calculate_rds_ris(aws_region, aws_access_key, aws_access_secret))
        send_metrics(dd_metric, diff, 'RDS')
    if check_elc:
        diff.update(calculate_elc_ris(aws_region, aws_access_key, aws_access_secret))
        send_metrics(dd_metric, diff, 'ElastiCache')


# instance IDs/name to report with unreserved instances
instance_ids = defaultdict(list)

# reserve expiration time to report with unused reservations
reserve_expiry = defaultdict(list)


def calc_expiry_time(expiry):
    """Calculate the number of days until the reserved instance expires.

    Args:
        expiry (DateTime): A timezone-aware DateTime object of the date when
            the reserved instance will expire.

    Returns:
        The number of days between the expiration date and now.
    """
    return (expiry.replace(tzinfo=None) - datetime.datetime.utcnow()).days


def calculate_ec2_ris(aws_region, aws_access_key_id, aws_secret_access_key):
    """Calculate the running/reserved instances in EC2.

    Args:
        aws_region, aws_access_key_id, aws_secret_access_key

    Returns:
        Results of running the `report_diffs` function.
    """

    ec2_conn = boto3.client(
        'ec2', aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key, region_name=aws_region)
    paginator = ec2_conn.get_paginator('describe_instances')
    page_iterator = paginator.paginate(
        Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])

    # Loop through running EC2 instances and record their AZ, type, and
    # Instance ID or Name Tag if it exists.
    ec2_running_instances = {}
    for page in page_iterator:
        for reservation in page['Reservations']:
            for instance in reservation['Instances']:
                # Ignore spot instances
                if 'SpotInstanceRequestId' not in instance:
                    az = instance['Placement']['AvailabilityZone']
                    instance_type = instance['InstanceType']
                    ec2_running_instances[(
                        instance_type, az)] = ec2_running_instances.get(
                        (instance_type, az), 0) + 1

                    # Either record the ec2 instance name tag, or the ID
                    found_tag = False
                    if 'Tags' in instance:
                        for tag in instance['Tags']:
                            if tag['Key'] == 'Name' and len(tag['Value']) > 0:
                                instance_ids[(instance_type, az)].append(
                                    tag['Value'])
                                found_tag = True

                    if not found_tag:
                        instance_ids[(instance_type, az)].append(
                            instance['InstanceId'])

    # Loop through active EC2 RIs and record their AZ and type.
    ec2_reserved_instances = {}
    for reserved_instance in ec2_conn.describe_reserved_instances(
            Filters=[{'Name': 'state', 'Values': ['active']}])[
            'ReservedInstances']:
        # Detect if an EC2 RI is a regional benefit RI or not
        if reserved_instance['Scope'] == 'Availability Zone':
            az = reserved_instance['AvailabilityZone']
        else:
            az = 'All'

        instance_type = reserved_instance['InstanceType']
        ec2_reserved_instances[(
            instance_type, az)] = ec2_reserved_instances.get(
            (instance_type, az), 0) + reserved_instance['InstanceCount']

        reserve_expiry[(instance_type, az)].append(calc_expiry_time(
            expiry=reserved_instance['End']))

    results = report_diffs(
        ec2_running_instances, ec2_reserved_instances, 'EC2')
    return results


def calculate_elc_ris(aws_region, aws_access_key_id, aws_secret_access_key):
    """Calculate the running/reserved instances in ElastiCache.

    Args:
        aws_region, aws_access_key_id, aws_secret_access_key

    Returns:
        Results of running the `report_diffs` function.
    """
    elc_conn = boto3.client(
        'elasticache', aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key, region_name=aws_region)

    paginator = elc_conn.get_paginator('describe_cache_clusters')
    page_iterator = paginator.paginate()
    # Loop through running ElastiCache instance and record their engine,
    # type, and name.
    elc_running_instances = {}
    for page in page_iterator:
        for instance in page['CacheClusters']:
            if instance['CacheClusterStatus'] == 'available':
                engine = instance['Engine']
                instance_type = instance['CacheNodeType']

                elc_running_instances[(
                    instance_type, engine)] = elc_running_instances.get(
                        (instance_type, engine), 0) + 1

                instance_ids[(instance_type, engine)].append(
                    instance['CacheClusterId'])

    paginator = elc_conn.get_paginator('describe_reserved_cache_nodes')
    page_iterator = paginator.paginate()
    # Loop through active ElastiCache RIs and record their type and engine.
    elc_reserved_instances = {}
    for page in page_iterator:
        for reserved_instance in page['ReservedCacheNodes']:
            if reserved_instance['State'] == 'active':
                engine = reserved_instance['ProductDescription']
                instance_type = reserved_instance['CacheNodeType']

                elc_reserved_instances[(instance_type, engine)] = (
                    elc_reserved_instances.get((
                        instance_type, engine), 0) + reserved_instance[
                        'CacheNodeCount'])

                # No end datetime is returned, so calculate from 'StartTime'
                # (a `DateTime`) and 'Duration' in seconds (integer)
                expiry_time = reserved_instance[
                    'StartTime'] + datetime.timedelta(
                        seconds=reserved_instance['Duration'])

                reserve_expiry[(instance_type, engine)].append(
                    calc_expiry_time(expiry=expiry_time))

    results = report_diffs(elc_running_instances, elc_reserved_instances,
                           'ElastiCache')
    return results


def calculate_rds_ris(aws_region, aws_access_key_id, aws_secret_access_key):
    """Calculate the running/reserved instances in RDS.

    Args:
        aws_region, aws_access_key_id, aws_secret_access_key

    Returns:
        Results of running the `report_diffs` function.
    """


    rds_conn = boto3.client(
        'rds', region_name=aws_region, aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key)

    paginator = rds_conn.get_paginator('describe_db_instances')
    page_iterator = paginator.paginate()

    # Loop through running RDS instances and record their Multi-AZ setting,
    # type, and Name
    rds_running_instances = {}
    for page in page_iterator:
        for instance in page['DBInstances']:
            az = instance['MultiAZ']
            instance_type = instance['DBInstanceClass']
            rds_running_instances[(
                instance_type, az)] = rds_running_instances.get(
                    (instance_type, az), 0) + 1
            instance_ids[(instance_type, az)].append(
                instance['DBInstanceIdentifier'])

    paginator = rds_conn.get_paginator('describe_reserved_db_instances')
    page_iterator = paginator.paginate()
    # Loop through active RDS RIs and record their type and Multi-AZ setting.
    rds_reserved_instances = {}
    for page in page_iterator:
        for reserved_instance in page['ReservedDBInstances']:
            if reserved_instance['State'] == 'active':
                az = reserved_instance['MultiAZ']
                instance_type = reserved_instance['DBInstanceClass']
                rds_reserved_instances[(
                    instance_type, az)] = rds_reserved_instances.get(
                    (instance_type, az), 0) + reserved_instance[
                    'DBInstanceCount']

                # No end datetime is returned, so calculate from 'StartTime'
                # (a `DateTime`) and 'Duration' in seconds (integer)
                expiry_time = reserved_instance[
                    'StartTime'] + datetime.timedelta(
                        seconds=reserved_instance['Duration'])

                reserve_expiry[(instance_type, az)].append(calc_expiry_time(
                    expiry=expiry_time))

    results = report_diffs(
        rds_running_instances, rds_reserved_instances, 'RDS')
    return results


def report_diffs(running_instances, reserved_instances, service):
    """Calculate differences between reserved instances and running instances.

    Prints a message string containg unused reservations, unreserved instances,
    and counts of running and reserved instances.

    Args:
        running_instances (dict): Dictionary object of running instances. Key
            is the unique identifier for RI's (instance type and availability
            zone). Value is the count of instances with those properties.
        reserved_instances (dict): Dictionary of reserved instances in the same
            format as running_instances.
        service (str): The AWS service of reservation to report, such as EC2,
            RDS, etc. Used only for outputting in the report.

    Returns:
        A dict of the unused reservations, unreserved instances and counts of
        each.
    """
    instance_diff = {}
    regional_benefit_ris = {}
    # loop through the reserved instances
    for placement_key in reserved_instances:
        # if the AZ from an RI is 'All' (regional benefit RI)
        if placement_key[1] == 'All':
            # put into another dict for these RIs and break
            regional_benefit_ris[placement_key[0]] = reserved_instances[
                placement_key]
        else:
            instance_diff[placement_key] = reserved_instances[
                placement_key] - running_instances.get(placement_key, 0)

    # add unreserved instances to instance_diff
    for placement_key in running_instances:
        if placement_key not in reserved_instances:
            instance_diff[placement_key] = -running_instances[
                placement_key]

    # loop through regional benefit RI's
    for ri in regional_benefit_ris:
        # loop through the entire instace diff
        for placement_key in instance_diff:
            # find unreserved instances with the same type as the regional
            # benefit RI
            if (placement_key[0] == ri and placement_key[1] != 'All' and
                    instance_diff[placement_key] < 0):
                # loop while incrementing unreserved instances (less than 0)
                # and decrementing count of regional benefit RI's
                while True:
                    if (instance_diff[placement_key] == 0 or
                            regional_benefit_ris[ri] == 0):
                        break
                    instance_diff[placement_key] += 1
                    regional_benefit_ris[ri] -= 1

        instance_diff[(ri, 'All')] = regional_benefit_ris[ri]

    unused_reservations = dict((key, value) for key, value in
                               instance_diff.items() if value > 0)

    unreserved_instances = dict((key, -value) for key, value in
                                instance_diff.items() if value < 0)

    qty_running_instances = 0
    for instance_count in running_instances.values():
        qty_running_instances += instance_count

    qty_reserved_instances = 0
    for instance_count in reserved_instances.values():
        qty_reserved_instances += instance_count

    return {
        service: (
            unused_reservations, unreserved_instances,
            qty_running_instances, qty_reserved_instances
        )
    }


def send_metrics(dd_metric, diff, what):
    if not what in diff:
        click.echo("WARNING: {} is not id diff, strange".format(what))
        return
    unused_reservations = 0
    unreserved_instances = 0
    qty_running_instances = diff[what][2]
    qty_reserved_instances = diff[what][3]
    for c in diff[what][0].values():
        unused_reservations += c
    for c in diff[what][1].values():
        unreserved_instances += c
    metric = "{}.{}.unused_reservations".format(dd_metric, what.lower())
    statsd.gauge(metric, unused_reservations)
    print "{}: {}".format(metric, unused_reservations)
    metric = "{}.{}.unreserved_instances".format(dd_metric, what.lower())
    statsd.gauge(metric, unreserved_instances)
    print "{}: {}".format(metric, unreserved_instances)
    metric = "{}.{}.qty_running_instances".format(dd_metric, what.lower())
    statsd.gauge(metric, qty_running_instances)
    print "{}: {}".format(metric, qty_running_instances)
    metric = "{}.{}.qty_reserved_instances".format(dd_metric, what.lower())
    statsd.gauge(metric, qty_reserved_instances)
    print "{}: {}".format(metric, qty_reserved_instances)


if __name__ == '__main__':
    cli()
