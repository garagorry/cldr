#!/usr/bin/env bash
# E.g dbsvr-86ef75e3-a122-44b8-9609-11021dd9e3c5
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <db-instance-identifier> [--region <aws-region>]"
  exit 1
fi

DB_IDENTIFIER=$1
shift
REGION_FLAG=""
OUTPUT_DIR="/tmp/rds_baseline_$(date +%Y%m%d%H%M%S)"
mkdir -p "$OUTPUT_DIR"

if [[ "$@" =~ "--region" ]]; then
  REGION_FLAG="--region $(echo "$@" | grep -oP '(?<=--region )[^ ]+')"
fi

echo "[INFO] Gathering details for DB Instance: $DB_IDENTIFIER"
echo "[INFO] Output will be saved in $OUTPUT_DIR"

echo "[STEP] Describing DB Instance..."
aws rds describe-db-instances --db-instance-identifier "$DB_IDENTIFIER" $REGION_FLAG \
  > "$OUTPUT_DIR/db_instance.json"

DB_INFO=$(cat "$OUTPUT_DIR/db_instance.json" | jq -r '.DBInstances[0]')
DB_PARAMETER_GROUP=$(echo "$DB_INFO" | jq -r '.DBParameterGroups[0].DBParameterGroupName')
DB_SUBNET_GROUP=$(echo "$DB_INFO" | jq -r '.DBSubnetGroup.DBSubnetGroupName')
VPC_ID=$(echo "$DB_INFO" | jq -r '.DBSubnetGroup.VpcId')
SEC_GROUP_IDS=$(echo "$DB_INFO" | jq -r '.VpcSecurityGroups[].VpcSecurityGroupId' | xargs)

echo "[INFO] Parameter Group: $DB_PARAMETER_GROUP"
echo "[INFO] Subnet Group: $DB_SUBNET_GROUP"
echo "[INFO] VPC ID: $VPC_ID"
echo "[INFO] Security Groups: $SEC_GROUP_IDS"

echo "[STEP] Describing Parameter Group: $DB_PARAMETER_GROUP"
aws rds describe-db-parameters --db-parameter-group-name "$DB_PARAMETER_GROUP" $REGION_FLAG \
  > "$OUTPUT_DIR/db_parameters.json"

echo "[STEP] Describing Subnet Group: $DB_SUBNET_GROUP"
aws rds describe-db-subnet-groups --db-subnet-group-name "$DB_SUBNET_GROUP" $REGION_FLAG \
  > "$OUTPUT_DIR/subnet_group.json"

for sg in $SEC_GROUP_IDS; do
  echo "[STEP] Describing Security Group: $sg"
  aws ec2 describe-security-groups --group-ids "$sg" $REGION_FLAG \
    > "$OUTPUT_DIR/security_group_$sg.json"
done

echo "[STEP] Describing VPC: $VPC_ID"
aws ec2 describe-vpcs --vpc-ids "$VPC_ID" $REGION_FLAG > "$OUTPUT_DIR/vpc.json"

echo "[STEP] Describing VPC Subnets"
SUBNET_IDS=$(jq -r '.DBInstances[0].DBSubnetGroup.Subnets[].SubnetIdentifier' "$OUTPUT_DIR/db_instance.json")
for subnet in $SUBNET_IDS; do
  aws ec2 describe-subnets --subnet-ids "$subnet" $REGION_FLAG > "$OUTPUT_DIR/subnet_$subnet.json"
done

echo "[✅ DONE] All data collected in: $OUTPUT_DIR"