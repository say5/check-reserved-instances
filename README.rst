check-reserved-instances
--------------------------
Original:
https://github.com/TerbiumLabs/check-reserved-instances

This version just sends metrics to DD.

Required IAM Permissions
------------------------

The following example IAM policy is the minimum set of permissions
needed to run the reporter:

::

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
