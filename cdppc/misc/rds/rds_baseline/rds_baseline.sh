#!/usr/bin/env bash
# RDS Baseline Collector with CSV Report Generation
# Version: 2.0.0
# Description: Collects comprehensive RDS baseline data and generates CSV reports
set -euo pipefail

SCRIPT_VERSION="2.0.0"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Requirements
for cmd in aws jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "[ERROR] '$cmd' is required but not found in PATH."
    exit 1
  fi
done

DEFAULT_OUTPUT_BASE="/tmp/rds_baseline"
TIMESTAMP=$(date +%Y%m%d%H%M%S)
OUTPUT_DIR="${DEFAULT_OUTPUT_BASE}_${TIMESTAMP}"
mkdir -p "$OUTPUT_DIR"

DB_IDENTIFIER=""
REGION=""
CLUSTER_CRN=""
CLUSTER_TYPE=""

usage() {
  echo "Usage:"
  echo "  $0 <db-identifier> [--region <aws-region>]"
  echo "  $0 --cluster-crn <crn> --type <datalake|datahub> [--region <aws-region>]"
  echo ""
  echo "Description:"
  echo "  This script collects comprehensive RDS baseline information and generates:"
  echo "  - JSON files with detailed RDS metadata"
  echo "  - CSV report with key RDS metrics"
  echo "  - Summary JSON for quick reference"
  echo ""
  echo "Output files:"
  echo "  - rds_baseline_report.csv: CSV with key RDS metrics"
  echo "  - rds_summary.json: Summary of RDS configuration"
  echo "  - db_instance.json: Full RDS instance details"
  echo "  - Additional JSON files for VPC, security groups, etc."
  echo ""
  echo "Examples:"
  echo "  $0 my-rds-instance --region us-east-1"
  echo "  $0 --cluster-crn crn:cdp:datalake:us-east-1:123:cluster:my-dl --type datalake"
  exit 1
}

# Argument parsing
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      usage
      ;;
    --version|-v)
      echo "RDS Baseline Collector v$SCRIPT_VERSION"
      exit 0
      ;;
    --region) REGION="$2"; shift 2 ;;
    --cluster-crn) CLUSTER_CRN="$2"; shift 2 ;;
    --type) CLUSTER_TYPE="$2"; shift 2 ;;
    -*)
      echo "[ERROR] Unknown option: $1"
      usage
      ;;
    *)
      DB_IDENTIFIER="$1"; shift ;;
  esac
done

# ======= CDP CLI Resolution =======
if [[ -n "$CLUSTER_CRN" ]]; then
  if [[ -z "$CLUSTER_TYPE" ]]; then
    echo "[ERROR] Must specify --type datalake or datahub"
    usage
  fi

  if [[ "$CLUSTER_TYPE" != "datalake" && "$CLUSTER_TYPE" != "datahub" ]]; then
    echo "[ERROR] Invalid cluster type: $CLUSTER_TYPE"
    usage
  fi

  if [[ "$CLUSTER_TYPE" == "datalake" && "$CLUSTER_CRN" != *":datalake:"* ]]; then
    echo "[ERROR] Expected datalake CRN but got something else"
    exit 1
  fi

  if [[ "$CLUSTER_TYPE" == "datahub" && "$CLUSTER_CRN" != *":datahub:"* ]]; then
    echo "[ERROR] Expected datahub CRN but got something else"
    exit 1
  fi

  log "[STEP] Validating CDP CLI"
  if ! command -v cdp &>/dev/null; then
    echo "[ERROR] CDP CLI Beta not found. Install it from:"
    echo "        https://docs.cloudera.com/cdp-public-cloud/cloud/cli/topics/mc_beta_cdp_cli.html"
    exit 1
  fi

  if ! cdp iam get-user &>/dev/null; then
    echo "[ERROR] CDP CLI is not authenticated. Run: cdp configure"
    exit 1
  fi

  log "[STEP] Getting DB host from CDP CLI ($CLUSTER_TYPE)"
  if [[ "$CLUSTER_TYPE" == "datalake" ]]; then
    DB_HOST=$(cdp datalake describe-database-server --cluster-crn "$CLUSTER_CRN" 2>/dev/null | jq -r '.host')
  else
    DB_HOST=$(cdp datahub describe-database-server --cluster-crn "$CLUSTER_CRN" 2>/dev/null | jq -r '.host')
  fi

  if [[ -z "$DB_HOST" || "$DB_HOST" == "null" ]]; then
    echo "[ERROR] Could not retrieve DB host using CDP CLI."
    exit 1
  fi

  DB_IDENTIFIER=$(echo "$DB_HOST" | cut -d'.' -f1)
  log "[INFO] Resolved DB Identifier: $DB_IDENTIFIER"
fi

if [[ -z "$DB_IDENTIFIER" ]]; then
  echo "[ERROR] You must provide a DB identifier or cluster CRN."
  usage
fi

# ======= Region Discovery Loop =======
ALL_REGIONS=$(aws ec2 describe-regions --query "Regions[].RegionName" --output text)
REGIONS_ARRAY=($ALL_REGIONS)

choose_region_menu() {
  echo ""
  echo "🔎 DB '$DB_IDENTIFIER' was not found in region '$REGION'."
  echo "What would you like to do?"
  echo "----------------------------------------------"
  for i in "${!REGIONS_ARRAY[@]}"; do
    printf " [%2d] %s\n" $((i + 1)) "${REGIONS_ARRAY[$i]}"
  done
  echo " [ 0] Auto-discover region"
  echo " [ x] Exit and fix manually"
  echo "----------------------------------------------"
  read -rp "Select option (number or x): " REGION_CHOICE

  if [[ "$REGION_CHOICE" =~ ^[0-9]+$ && "$REGION_CHOICE" -ge 1 && "$REGION_CHOICE" -le ${#REGIONS_ARRAY[@]} ]]; then
    REGION="${REGIONS_ARRAY[$((REGION_CHOICE - 1))]}"
    return 0
  elif [[ "$REGION_CHOICE" == "0" ]]; then
    REGION=""
    return 0
  else
    echo "[EXIT] Aborting. Please re-run the script with a correct region."
    exit 1
  fi
}

REGION_FLAG=""
while true; do
  if [[ -n "$REGION" ]]; then
    if ! printf "%s\n" "${REGIONS_ARRAY[@]}" | grep -Fxq "$REGION"; then
      echo "[⚠️ WARNING] '$REGION' is not a valid AWS region."
      choose_region_menu
      continue
    fi

    log "[INFO] Checking region: $REGION"
    if aws rds describe-db-instances --db-instance-identifier "$DB_IDENTIFIER" --region "$REGION" &>/dev/null; then
      REGION_FLAG="--region $REGION"
      break
    else
      choose_region_menu
    fi
  else
    for r in "${REGIONS_ARRAY[@]}"; do
      log "[INFO] Auto-checking region: $r"
      if aws rds describe-db-instances --db-instance-identifier "$DB_IDENTIFIER" --region "$r" &>/dev/null; then
        REGION="$r"
        REGION_FLAG="--region $REGION"
        log "[✅ FOUND] DB found in region: $REGION"
        break 2
      fi
    done
    echo "[❌ ERROR] DB '$DB_IDENTIFIER' was not found in any region."
    exit 1
  fi
done

log "[STEP] Collecting RDS baseline for DB: $DB_IDENTIFIER"
log "[INFO] Region: $REGION"
log "[INFO] Output Dir: $OUTPUT_DIR"

# ======= Collect Metadata =======
log "[STEP] Describing DB Instance..."
aws rds describe-db-instances --db-instance-identifier "$DB_IDENTIFIER" $REGION_FLAG \
  > "$OUTPUT_DIR/db_instance.json"

DB_INFO=$(jq -r '.DBInstances[0]' "$OUTPUT_DIR/db_instance.json")
DB_PARAMETER_GROUP=$(echo "$DB_INFO" | jq -r '.DBParameterGroups[0].DBParameterGroupName')
DB_SUBNET_GROUP=$(echo "$DB_INFO" | jq -r '.DBSubnetGroup.DBSubnetGroupName')
VPC_ID=$(echo "$DB_INFO" | jq -r '.DBSubnetGroup.VpcId')
SEC_GROUP_IDS=$(echo "$DB_INFO" | jq -r '.VpcSecurityGroups[].VpcSecurityGroupId' | xargs)

log "[INFO] Parameter Group: $DB_PARAMETER_GROUP"
log "[INFO] Subnet Group: $DB_SUBNET_GROUP"
log "[INFO] VPC ID: $VPC_ID"
log "[INFO] Security Groups: $SEC_GROUP_IDS"

log "[STEP] Describing Parameter Group..."
aws rds describe-db-parameters --db-parameter-group-name "$DB_PARAMETER_GROUP" $REGION_FLAG \
  > "$OUTPUT_DIR/db_parameters.json"

log "[STEP] Describing Subnet Group..."
aws rds describe-db-subnet-groups --db-subnet-group-name "$DB_SUBNET_GROUP" $REGION_FLAG \
  > "$OUTPUT_DIR/subnet_group.json"

mkdir -p "$OUTPUT_DIR/security_groups"
for sg in $SEC_GROUP_IDS; do
  log "[STEP] Describing Security Group: $sg"
  aws ec2 describe-security-groups --group-ids "$sg" $REGION_FLAG \
    > "$OUTPUT_DIR/security_groups/security_group_$sg.json"
done

log "[STEP] Describing VPC: $VPC_ID"
aws ec2 describe-vpcs --vpc-ids "$VPC_ID" $REGION_FLAG \
  > "$OUTPUT_DIR/vpc.json"

mkdir -p "$OUTPUT_DIR/subnets"
SUBNET_IDS=$(echo "$DB_INFO" | jq -r '.DBSubnetGroup.Subnets[].SubnetIdentifier')
for subnet in $SUBNET_IDS; do
  log "[STEP] Describing Subnet: $subnet"
  aws ec2 describe-subnets --subnet-ids "$subnet" $REGION_FLAG \
    > "$OUTPUT_DIR/subnets/subnet_$subnet.json"
done

log "[✅ DONE] RDS metadata collected in: $OUTPUT_DIR"

# Function to generate CSV report from collected JSON data
generate_csv_report() {
  local output_dir="$1"
  local csv_file="$output_dir/rds_baseline_report.csv"
  
  log "[STEP] Generating CSV report..."
  
  # Check if required JSON files exist
  if [[ ! -f "$output_dir/db_instance.json" ]]; then
    echo "[ERROR] Required file db_instance.json not found"
    return 1
  fi
  
  # Validate that the JSON contains RDS instance data
  if ! jq -e '.DBInstances[0]' "$output_dir/db_instance.json" >/dev/null 2>&1; then
    echo "[ERROR] Invalid RDS instance data in db_instance.json"
    return 1
  fi
  
  # Create CSV header
  cat > "$csv_file" << EOF
Endpoint,DB Instance ID,Engine Version,Created Time,Instance Class,vCPU,RAM,Primary Storage Encryption,Primary Storage Storage Type,Primary Storage Storage (GB),Primary Storage Provisioned IOPS,Primary Storage Storage Throughput (MB/s)
EOF
  
  # Extract data from JSON and append to CSV with better vCPU/RAM handling
  if ! jq -r '
    .DBInstances[0] | {
      endpoint: .Endpoint.Address,
      db_instance_id: .DBInstanceIdentifier,
      engine_version: .EngineVersion,
      created_time: .InstanceCreateTime,
      instance_class: .DBInstanceClass,
      vcpu: (.DBInstanceClass | if contains("xlarge") then "4" elif contains("large") then "2" elif contains("medium") then "1" elif contains("small") then "1" elif contains("micro") then "1" elif contains("nano") then "1" else "N/A" end),
      ram: (.DBInstanceClass | if contains("xlarge") then "16GB" elif contains("large") then "8GB" elif contains("medium") then "4GB" elif contains("small") then "2GB" elif contains("micro") then "1GB" elif contains("nano") then "0.5GB" else "N/A" end),
      storage_encryption: (.StorageEncrypted // false),
      storage_type: (.StorageType // "N/A"),
      storage_size: (.AllocatedStorage // "N/A"),
      provisioned_iops: (.Iops // "N/A"),
      storage_throughput: (.StorageThroughput // "N/A")
    } | [
      .endpoint,
      .db_instance_id,
      .engine_version,
      .created_time,
      .instance_class,
      .vcpu,
      .ram,
      .storage_encryption,
      .storage_type,
      .storage_size,
      .provisioned_iops,
      .storage_throughput
    ] | @csv
  ' "$output_dir/db_instance.json" >> "$csv_file"; then
    echo "[ERROR] Failed to generate CSV data from JSON"
    return 1
  fi
  
  # Also create a more detailed JSON summary for reference
  if ! jq -r '.DBInstances[0] | {
    endpoint: .Endpoint.Address,
    db_instance_id: .DBInstanceIdentifier,
    engine_version: .EngineVersion,
    created_time: .InstanceCreateTime,
    instance_class: .DBInstanceClass,
          vcpu: (.DBInstanceClass | if contains("xlarge") then "4" elif contains("large") then "2" elif contains("medium") then "1" elif contains("small") then "1" elif contains("micro") then "1" elif contains("nano") then "1" else "N/A" end),
      ram: (.DBInstanceClass | if contains("xlarge") then "16GB" elif contains("large") then "8GB" elif contains("medium") then "4GB" elif contains("small") then "2GB" elif contains("micro") then "1GB" elif contains("nano") then "0.5GB" else "N/A" end),
    storage_encryption: (.StorageEncrypted // false),
    storage_type: (.StorageType // "N/A"),
    storage_size: (.AllocatedStorage // "N/A"),
    provisioned_iops: (.Iops // "N/A"),
    storage_throughput: (.StorageThroughput // "N/A"),
    engine: .Engine,
    status: .DBInstanceStatus,
    availability_zone: .AvailabilityZone,
    multi_az: .MultiAZ,
    backup_retention: .BackupRetentionPeriod,
    maintenance_window: .PreferredMaintenanceWindow,
    backup_window: .PreferredBackupWindow
  }' "$output_dir/db_instance.json" > "$output_dir/rds_summary.json"; then
    echo "[ERROR] Failed to generate summary JSON"
    return 1
  fi
  
  log "[✅ CSV Report] Generated: $csv_file"
  log "[✅ Summary JSON] Generated: $output_dir/rds_summary.json"
  
  # Display the CSV content
  echo ""
  echo "📊 RDS Baseline Report:"
  echo "========================"
  cat "$csv_file"
  echo ""
  
  # Show summary of all generated files
  echo "📁 Generated Files Summary:"
  echo "============================"
  echo "CSV Report: $csv_file"
  echo "Summary JSON: $output_dir/rds_summary.json"
  echo "Full Instance Details: $output_dir/db_instance.json"
  echo "Parameter Group: $output_dir/db_parameters.json"
  echo "Subnet Group: $output_dir/subnet_group.json"
  echo "VPC Details: $output_dir/vpc.json"
  echo "Security Groups: $output_dir/security_groups/"
  echo "Subnets: $output_dir/subnets/"
  echo ""
  echo "💡 Tip: Open the CSV file in Excel or Google Sheets for better formatting"
}

# Generate CSV report from collected data
generate_csv_report "$OUTPUT_DIR"
