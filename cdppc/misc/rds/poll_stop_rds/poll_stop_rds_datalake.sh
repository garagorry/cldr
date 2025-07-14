#!/bin/bash

# Default values
POLL_INTERVAL=10
DEFAULT_REGION="sa-east-1"
DEFAULT_PROFILE="default"
LOG_DIR="/var/tmp/logs"
mkdir -p "$LOG_DIR"

usage() {
  echo "Usage: $0 --cluster-crn <datalake-cluster-crn> [--region REGION] [--profile PROFILE]"
  echo ""
  echo "Required:"
  echo "  --cluster-crn  Cloudera Data Lake cluster CRN"
  echo ""
  echo "Optional:"
  echo "  --region       AWS region (default: $DEFAULT_REGION)"
  echo "  --profile      AWS CLI profile name (default: $DEFAULT_PROFILE)"
  exit 1
}

CLUSTER_CRN=""
REGION="$DEFAULT_REGION"
PROFILE="$DEFAULT_PROFILE"

while [[ $# -gt 0 ]]; do
  case $1 in
    --cluster-crn)
      CLUSTER_CRN="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    -*|--*)
      echo "Unknown option $1"
      usage
      ;;
    *)
      echo "Unexpected positional argument: $1"
      usage
      ;;
  esac
done

if [ -z "$CLUSTER_CRN" ]; then
  echo "❌ Error: --cluster-crn is required."
  usage
fi

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/stop_rds_${TIMESTAMP}.log"

# Start logging
exec > >(tee -a "$LOG_FILE") 2>&1

echo "🧪 Starting RDS Stop Timer Script"
echo "🔹 Cluster CRN: $CLUSTER_CRN"
echo "🔹 AWS Region: $REGION"
echo "🔹 AWS Profile: $PROFILE"
echo "📄 Logging to: $LOG_FILE"
echo "------------------------------------------------------------"

AWS_ARGS=(--region "$REGION" --profile "$PROFILE")

# Step 1: Get the DB host via CDP CLI
echo "🔍 Fetching DB host from CDP..."
DB_HOST=$(cdp datalake describe-database-server --cluster-crn "$CLUSTER_CRN" 2>/dev/null | jq -r '.host')

if [ -z "$DB_HOST" ] || [ "$DB_HOST" == "null" ]; then
  echo "❌ Failed to retrieve DB host. Check CRN or CDP CLI access."
  exit 1
fi

DB_ID=$(echo "$DB_HOST" | cut -d'.' -f1)
if [ -z "$DB_ID" ]; then
  echo "❌ Could not extract DB ID from host: $DB_HOST"
  exit 1
fi

echo "✅ RDS DB Identifier resolved: $DB_ID"
echo "🕒 Initiating stop request..."

START_TIME=$(date +%s)

# Step 2: Stop the RDS instance
aws rds stop-db-instance --db-instance-identifier "$DB_ID" "${AWS_ARGS[@]}" >/dev/null

# Step 3: Poll for status
while true; do
  STATUS=$(aws rds describe-db-instances --db-instance-identifier "$DB_ID" \
    --query "DBInstances[0].DBInstanceStatus" --output text 2>/dev/null)

  echo "[INFO] $(date '+%H:%M:%S') - Current RDS status: $STATUS"

  if [[ "$STATUS" == "stopped" ]]; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    echo "✅ RDS instance '$DB_ID' successfully stopped in $DURATION seconds."
    break
  fi

  sleep "$POLL_INTERVAL"
done
