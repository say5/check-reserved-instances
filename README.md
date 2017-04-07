## Why?

You are running Kubernetes cluster on AWS and using `Reserved Instances` to save money. Also you are using DataDog to monitor things. This project can help you to be notified when you have Reserved Instance not in use or EC2 instance not being reserved.

## How?

You need:

1. Create IAM role to allow script to talk to AWS API, check `Required IAM Permissions`.
2. Deploy this project in your cluster, i.e. `kubectl create -f https://raw.githubusercontent.com/say5/check-reserved-instances/master/check-ri.do`
3. Check DataDog metrics.
4. Configure DataDog monitor to get notifications.

## What the Metrics?

1. `{{ DD_METRIC }}.{{ TYPE }}.unused_reservations` number of unused reservations (probably the best metric to monitor).
2. `{{ DD_METRIC }}.{{ TYPE }}.unreserved_instances` number of instances running and not being reserved.
3. `{{ DD_METRIC }}.{{ TYPE }}.qty_running_instances` number of running instances.
4. `{{ DD_METRIC }}.{{ TYPE }}.qty_reserved_instances` number of reserved instances.

Where `DD_METRIC` is env variable (`ri` by default). And `Type` is: `ec2`, `rds`, `elasticache`.


## Required IAM Permissions

The following example IAM policy is the minimum set of permissions
needed to run the reporter:


```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:DescribeReservedInstances",
                "rds:DescribeDBInstances",
                "rds:DescribeReservedDBInstances",
                "elasticache:DescribeCacheClusters",
                "elasticache:DescribeReservedCacheNodes"
            ],
            "Resource": "*"
        }
    ]
}
```

## Credits

Original project:
https://github.com/TerbiumLabs/check-reserved-instances

This version just sends metrics to DataDog.
