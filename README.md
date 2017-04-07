## Why?

You are running Kubernetes cluster on AWS and using `Reserved Instances` to save money. Also you are using DataDog to monitor things. This project can help you to be notified when you have Reserved Instance not in use or EC2 instance not being reserved.

## How?

You need:

1. Create IAM role to allow script to talk to AWS API, check `Required IAM Permissions`.
2. Deploy this project in your cluster, i.e. `kubectl create -f https://raw.githubusercontent.com/say5/check-reserved-instances/master/check-ri.do`
3. Check DataDog metrics.
4. Configure DataDog monitor to get notifications.

## check-reserved-instances

Original project:
https://github.com/TerbiumLabs/check-reserved-instances

This version just sends metrics to DataDog.

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
