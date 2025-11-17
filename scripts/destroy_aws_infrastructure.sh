#!/bin/bash
set -euo pipefail # Strict bash deployment mode (stop on error, unset variables and catch errors in piped commands)


#  Load environment variables
if [ ! -f .env ]; then
  echo "Error: .env file not found. Please run the creation script first."
  exit 1
fi

source .env

echo "Loaded environment variables from .env"
echo "Beginning teardown of AWS resources in region: ${REGION}"

# Terminate EC2 instance
if [ -n "${EC2_INSTANCE_ID:-}" ]; then
  echo "Terminating EC2 instance: ${EC2_INSTANCE_ID}"
  aws ec2 terminate-instances --instance-ids "$EC2_INSTANCE_ID" --region "$REGION"
  echo "Waiting for EC2 instance to terminate..."
  aws ec2 wait instance-terminated --instance-ids "$EC2_INSTANCE_ID" --region "$REGION"
fi


# Wait until EIP is fully disassociated
if [ -n "${EIP_ALLOCATION_ID:-}" ]; then
  echo "Waiting for Elastic IP to fully disassociate..."
  for i in {1..10}; do
    ASSOC_CHECK=$(aws ec2 describe-addresses \
      --allocation-id "$EIP_ALLOCATION_ID" \
      --query "Addresses[0].AssociationId" \
      --output text)

    if [ "$ASSOC_CHECK" = "None" ]; then
      echo "Elastic IP is disassociated."
      break
    fi

    echo "Try ${i}. Still associated… retrying in 3 seconds"
    sleep 3
  done
fi

# Release the EIP
echo "Releasing Elastic IP: ${EIP_ALLOCATION_ID}"
aws ec2 release-address --allocation-id "$EIP_ALLOCATION_ID" --region "$REGION" || true


# Delete security groups
if [ -n "${SG_SSH_ID:-}" ]; then
  echo "Deleting security group: ${SG_SSH_ID}"
  aws ec2 delete-security-group --group-id "$SG_SSH_ID" --region "$REGION" || true
fi

if [ -n "${SG_CUSTOM_8443_ID:-}" ]; then
  echo "Deleting security group: ${SG_CUSTOM_8443_ID}"
  aws ec2 delete-security-group --group-id "$SG_CUSTOM_8443_ID" --region "$REGION" || true
fi


# Disassociate route tables and delete
if [ -n "${EC2_RTB_ID:-}" ] && [ -n "${EC2_SUBNET_ID:-}" ]; then
  echo "Disassociating route table: ${EC2_RTB_ID}"
  ASSOC_ID=$(aws ec2 describe-route-tables \
    --route-table-ids "$EC2_RTB_ID" \
    --query "RouteTables[0].Associations[0].RouteTableAssociationId" \
    --output text --region "$REGION" 2>/dev/null || true)

  if [ "$ASSOC_ID" != "None" ]; then
    aws ec2 disassociate-route-table --association-id "$ASSOC_ID" --region "$REGION" || true
  fi

  echo "Deleting route table: ${EC2_RTB_ID}"
  aws ec2 delete-route-table --route-table-id "$EC2_RTB_ID" --region "$REGION" || true
fi

# Delete prefix list
if [ -n "${PREFIX_LIST_ID:-}" ]; then
  echo "Deleting prefix list: ${PREFIX_LIST_ID}"
  aws ec2 delete-managed-prefix-list --prefix-list-id "$PREFIX_LIST_ID" --region "$REGION" || true
fi

# Detach and delete internet gateway
if [ -n "${EC2_IGW_ID:-}" ] && [ -n "${EC2_VPC_ID:-}" ]; then
  echo "Detaching and deleting Internet Gateway: ${EC2_IGW_ID}"
  aws ec2 detach-internet-gateway --internet-gateway-id "$EC2_IGW_ID" --vpc-id "$EC2_VPC_ID" --region "$REGION" || true
  aws ec2 delete-internet-gateway --internet-gateway-id "$EC2_IGW_ID" --region "$REGION" || true
fi


# Delete subnet
if [ -n "${EC2_SUBNET_ID:-}" ]; then
  echo "Deleting subnet: ${EC2_SUBNET_ID}"
  aws ec2 delete-subnet --subnet-id "$EC2_SUBNET_ID" --region "$REGION" || true
fi


# Delete VPC
if [ -n "${EC2_VPC_ID:-}" ]; then
  echo "Deleting VPC: ${EC2_VPC_ID}"
  aws ec2 delete-vpc --vpc-id "$EC2_VPC_ID" --region "$REGION" || true
fi


# Delete key pair and local file
if [ -n "${KEY_PAIR_NAME:-}" ]; then
  echo "Deleting key pair: ${KEY_PAIR_NAME}"
  aws ec2 delete-key-pair --key-name "$KEY_PAIR_NAME" --region "$REGION" || true
fi

if [ -f "${KEY_PAIR_FILE_NAME:-}" ]; then
  echo "Deleting local key file: ${KEY_PAIR_FILE_NAME}"
  rm -f "$KEY_PAIR_FILE_NAME"
fi

# Remove environment file
rm -f .env

# Cleanup confirmation
echo "All infrastructure deleted successfully."
