#!/bin/sh

EC2_REGION=$(curl -s http://169.254.169.254/latest/dynamic/instance-identity/document | jq .region -r)
LOCAL_IPV4=$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4)
DD_METRIC=${DD_METRIC:-ri}
REPORT_INTERVAL=${REPORT_INTERVAL:-86400}

while true
do
  echo $(date)
  /check-reserved-instances.py --aws-region="$EC2_REGION" --dd-host="$LOCAL_IPV4" --dd-metric="$DD_METRIC"
  sleep ${REPORT_INTERVAL}
done
