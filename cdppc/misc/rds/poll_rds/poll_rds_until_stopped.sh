#!/bin/bash

# Defaults
POLL_INTERVAL=10
DEFAULT_REGION="sa-east-1"
DEFAULT_PROFILE="default"

usage() {
  echo "Usage: $0 --cluster-crn <datalake-cluster-crn> [--region REGION] [--profile PROFILE]"
  echo ""
  echo "Required:"
  echo "  --cluster-crn   Cloudera Data Lake cluster CRN"
  echo ""
  echo "Optional:"
  echo "  --region        AWS region (default: $DEFAULT_REGION)"
  echo "  --profile       AWS CLI profile name (default: $DEFAULT_PROFILE)"
  exit 1
}

CLUSTER_CRN=""
REGION="$DEFAULT_REGION"
PROFILE="$DEFAULT_PROFILE"

while [[ $# -gt 0 ]]; do
  case "$1" in
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
      echo "Unknown option: $1"
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

echo "✅ Resolved RDS DB Identifier: $DB_ID"
echo "🔄 Polling RDS status until 'stopped'..."
echo "📍 Region: $REGION | Profile: $PROFILE"
echo "------------------------------------------------------------"

# Step 2: Polling loop
while true; do
  STATUS=$(aws rds describe-db-instances --db-instance-identifier "$DB_ID" \
    --query "DBInstances[0].DBInstanceStatus" --output text "${AWS_ARGS[@]}" 2>/dev/null)

  echo "[INFO] $(date '+%H:%M:%S') - Current RDS status: $STATUS"

  if [[ "$STATUS" == "stopped" ]]; then
    echo "✅ Instance '$DB_ID' is now in 'stopped' state."
    break
  fi

  sleep "$POLL_INTERVAL"
done

# Step 3: Show final details
echo "📋 Fetching final instance details..."
aws rds describe-db-instances --db-instance-identifier "$DB_ID" --output table "${AWS_ARGS[@]}"
