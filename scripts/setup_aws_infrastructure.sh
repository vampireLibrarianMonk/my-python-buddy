#!/bin/bash
set -euo pipefail # Strict bash deployment mode (stop on error, unset variables and catch errors in piped commands)

REGION=$1
AZ=$2
KEY_PAIR_NAME=$3
KEY_PAIR_FILE_NAME=$4

#  Error handling
if [ -z "$REGION" ] || [ -z "$AZ" ] || [ -z "$KEY_PAIR_NAME" ]; then
  echo "Error: Missing required arguments."
  echo "Usage: $0 <region> <availability-zone> <key-pair-name>"
  echo "Example: $0 us-east-1 us-east-1a my-ec2-key"
  exit 1
fi

#  Validate AWS region format
if ! [[ "$REGION" =~ ^[a-z]{2}-[a-z]+-[0-9]+$ ]]; then
  echo "Error: Invalid AWS region format ($REGION). Expected something like 'us-east-1'."
  exit 1
fi

#  Validate availability zone format
if ! [[ "$AZ" =~ ^[a-z]{2}-[a-z]+-[0-9]+[a-z]$ ]]; then
  echo "Error: Invalid availability zone format ($AZ). Expected something like 'us-east-1a'."
  exit 1
fi

#  Verify AWS CLI configured
if ! aws sts get-caller-identity --region "$REGION" >/dev/null 2>&1; then
  echo "Error: AWS CLI not configured or credentials invalid for region $REGION."
  exit 1
fi

#  Continue execution
echo "Using Region: $REGION"
echo "Availability Zone: $AZ"
echo "Key Pair Name: $KEY_PAIR_NAME"
echo "Key File Name: $KEY_PAIR_FILE_NAME"

# Create environment file
touch .env

# Limit the permissions of the file
chmod 660 .env

#  Save all environment variables to .env file for the destruction script later
echo "Saving environment variables to .env file as they are created..."

echo "REGION=${REGION}" >> .env
echo "AZ=${AZ}" >> .env
echo "KEY_PAIR_NAME=${KEY_PAIR_NAME}" >> .env
echo "KEY_PAIR_FILE_NAME=${KEY_PAIR_FILE_NAME}" >> .env

echo "Creating VPC"

EC2_VPC_ID=$(aws ec2 create-vpc \
  --cidr-block 192.168.0.0/24 \
  --query 'Vpc.VpcId' \
  --output text)

echo "EC2_VPC_ID: ${EC2_VPC_ID} created."

echo "EC2_VPC_ID=${EC2_VPC_ID}" >> .env

echo "Creating Public Subnet: "

EC2_SUBNET_ID=$(aws ec2 create-subnet \
  --vpc-id "$EC2_VPC_ID" \
  --cidr-block 192.168.0.0/25 \
  --availability-zone "$AZ" \
  --query 'Subnet.SubnetId' \
  --output text)

echo "Public Subnet ID: ${EC2_SUBNET_ID} created."

echo "EC2_SUBNET_ID=${EC2_SUBNET_ID}" >> .env

echo "Creating IGW:"

EC2_IGW_ID=$(aws ec2 create-internet-gateway \
  --query 'InternetGateway.InternetGatewayId' \
  --output text)

echo "IGW ID: ${EC2_IGW_ID} created."

echo "EC2_IGW_ID=${EC2_IGW_ID}" >> .env

aws ec2 attach-internet-gateway \
 --internet-gateway-id "$EC2_IGW_ID" \
 --vpc-id "$EC2_VPC_ID"

echo "Creating the routing table."

EC2_RTB_ID=$(aws ec2 create-route-table \
 --vpc-id "$EC2_VPC_ID" \
 --query 'RouteTable.RouteTableId' \
 --output text)

echo "The following route table was created: ${EC2_RTB_ID}."

echo "EC2_RTB_ID=${EC2_RTB_ID}" >> .env

echo "Creating the route to the IGW."

aws ec2 create-route \
 --route-table-id "$EC2_RTB_ID" \
 --destination-cidr-block 0.0.0.0/0 \
 --gateway-id "$EC2_IGW_ID"

echo "Creating the route table association for the Public Subnet."

aws ec2 associate-route-table \
 --subnet-id "$EC2_SUBNET_ID" \
 --route-table-id "$EC2_RTB_ID"

echo "Querying current IP Address."

MY_IP_ADDRESS=$(curl -s https://checkip.amazonaws.com)

echo "The following IP Address was found: ${MY_IP_ADDRESS} and will be used for the Prefix List."

echo "MY_IP_ADDRESS=${MY_IP_ADDRESS}" >> .env

echo "Creating prefix list."

PREFIX_LIST_ID=$(aws ec2 create-managed-prefix-list \
  --address-family IPv4 \
  --max-entries 1 \
  --prefix-list-name my-workstation-pl \
  --entries "Cidr=$MY_IP_ADDRESS/32,Description=Workstation" \
  --region "$REGION" \
  --query 'PrefixList.PrefixListId' \
  --output text)

echo "The following Prefix List was created: ${PREFIX_LIST_ID} with the name my-workstation-pl."

echo "PREFIX_LIST_ID=${PREFIX_LIST_ID}" >> .env

echo "Creating developer access (SSH 22) SG:"

SG_SSH_ID=$(aws ec2 create-security-group \
  --group-name my-sg-ssh \
  --description "Allow SSH 22 from prefix list." \
  --vpc-id "$EC2_VPC_ID" \
  --query 'GroupId' \
  --output text)

echo "SG ID: ${SG_SSH_ID} created."

echo "SG_SSH_ID=${SG_SSH_ID}" >> .env

echo "Authorizing ${SG_SSH_ID} with Prefix ID: ${PREFIX_LIST_ID}."

aws ec2 authorize-security-group-ingress \
  --group-id "$SG_SSH_ID" \
  --ip-permissions "IpProtocol=tcp,FromPort=22,ToPort=22,PrefixListIds=[{PrefixListId=$PREFIX_LIST_ID}]"

echo "Creating developer access (HTTPS 8443) SG:"

SG_CUSTOM_8443_ID=$(aws ec2 create-security-group \
  --group-name my-sg-custom-8443 \
  --description "Allow TCP 8443 from prefix list." \
  --vpc-id "$EC2_VPC_ID" \
  --query 'GroupId' \
  --output text)

echo "SG ID: ${SG_CUSTOM_8443_ID} created."

echo "SG_CUSTOM_8443_ID=${SG_CUSTOM_8443_ID}" >> .env

echo "Authorizing ${SG_CUSTOM_8443_ID} with Prefix ID: ${PREFIX_LIST_ID}."

aws ec2 authorize-security-group-ingress \
  --group-id "$SG_CUSTOM_8443_ID" \
  --ip-permissions "IpProtocol=tcp,FromPort=8443,ToPort=8443,PrefixListIds=[{PrefixListId=$PREFIX_LIST_ID}]"

echo "Creating key pair and modding it for use:"

aws ec2 create-key-pair \
  --key-name "$KEY_PAIR_NAME" \
  --query 'KeyMaterial' \
  --output text > "$KEY_PAIR_FILE_NAME"

chmod 400 "$KEY_PAIR_FILE_NAME"

echo "Key pair ${KEY_PAIR_FILE_NAME} file created with name ${KEY_PAIR_NAME}."

echo "Get the most recent AMI ID for Ubuntu Server 22.04."

EC2_INSTANCE_AMI_ID=$(aws ec2 describe-images \
  --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
  --query 'Images | sort_by(@, &CreationDate)[-1].ImageId' \
  --output text \
  --region "$REGION")

echo "AMI ID: ${EC2_INSTANCE_AMI_ID} found."

echo "EC2_INSTANCE_AMI_ID=${EC2_INSTANCE_AMI_ID}" >> .env

echo "Creating EC2 Instance."

EC2_INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$EC2_INSTANCE_AMI_ID" \
  --count 1 \
  --instance-type g5.2xlarge \
  --key-name "$KEY_PAIR_NAME" \
  --security-group-ids "$SG_CUSTOM_8443_ID" "$SG_SSH_ID" \
  --subnet-id "$EC2_SUBNET_ID" \
  --associate-public-ip-address \
  --block-device-mappings '[
    {
      "DeviceName": "/dev/sda1",
      "Ebs": {
        "VolumeSize": 75,
        "VolumeType": "gp3",
        "DeleteOnTermination": true
      }
    }
  ]' \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "EC2 Instance created with ID ${EC2_INSTANCE_ID}"

echo "EC2_INSTANCE_ID=${EC2_INSTANCE_ID}" >> .env

echo "Creating Elastic IP Address."

EIP_OUTPUT=$(aws ec2 allocate-address \
  --query '[AllocationId, PublicIp]' \
  --output text \
  --region "$REGION")

EIP_ALLOCATION_ID=$(echo "$EIP_OUTPUT" | awk '{print $1}')
ELASTIC_IP_ADDRESS=$(echo "$EIP_OUTPUT" | awk '{print $2}')

echo "Allocated Elastic IP Address: ${ELASTIC_IP_ADDRESS} created."
echo "Allocation ID for Elastic IP Address: ${EIP_ALLOCATION_ID} created."

echo "ELASTIC_IP_ADDRESS=${ELASTIC_IP_ADDRESS}" >> .env
echo "EIP_ALLOCATION_ID=${EIP_ALLOCATION_ID}" >> .env

echo "Elastic IP Address Allocation ID: ${EIP_ALLOCATION_ID} created with address ${ELASTIC_IP_ADDRESS}."

# Wait for instance to enter 'running' state
echo "Waiting for EC2 system checks to pass..."
aws ec2 wait instance-status-ok --instance-ids "$EC2_INSTANCE_ID"

echo "Instance is fully ready. Associating Elastic IP..."
aws ec2 associate-address --public-ip "$ELASTIC_IP_ADDRESS" --instance-id "$EC2_INSTANCE_ID"

echo "Elastic IP successfully associated."

echo "Run the following command to connect to your EC2 Instance."
echo "ssh -i ${KEY_PAIR_FILE_NAME} ubuntu@${ELASTIC_IP_ADDRESS}"