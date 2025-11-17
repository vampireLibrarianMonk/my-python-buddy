#!/bin/bash

# Set desired vCPU value
DESIRED_VCPU=$1

# Get the quota code out of the None matches
GPU_QUOTA_CODE=$(
  aws service-quotas list-service-quotas \
    --service-code ec2 \
    --query "Quotas[?contains(QuotaName, 'G') && contains(QuotaName, 'On-Demand')].QuotaCode" \
    --output text | tr '\t' '\n' | grep -v None | head -n 1
)

# Request the increase in quota
aws service-quotas request-service-quota-increase \
  --service-code ec2 \
  --quota-code "$GPU_QUOTA_CODE" \
  --desired-value "$DESIRED_VCPU"

echo "Check here for updates to your quota: https://support.console.aws.amazon.com/support/home#/case/history"