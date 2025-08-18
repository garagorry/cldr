# RDS Baseline Collector with CSV Report Generation

This script collects comprehensive RDS baseline information from AWS and generates both JSON metadata files and a CSV report for easy analysis.

## Features

- **Comprehensive Data Collection**: Gathers RDS instance details, VPC info, security groups, subnets, and more
- **CSV Report Generation**: Creates a formatted CSV with key RDS metrics for easy analysis
- **CDP CLI Integration**: Can resolve RDS instances from CDP cluster CRNs
- **Region Auto-Discovery**: Automatically finds the correct AWS region for your RDS instance
- **Multiple Output Formats**: JSON files for detailed analysis, CSV for quick review
- **Enhanced Error Handling**: Comprehensive validation and error reporting

## Prerequisites

- AWS CLI configured with appropriate permissions
- `jq` command-line JSON processor
- CDP CLI Beta (optional, for cluster CRN resolution)

## Usage

### Basic Usage (Direct RDS Identifier)

```bash
./rds_baseline.sh my-rds-instance --region us-east-1
```

### CDP Cluster Integration

```bash
# For Data Lake
./rds_baseline.sh --cluster-crn crn:cdp:datalake:us-east-1:123:cluster:my-dl --type datalake

# For Data Hub
./rds_baseline.sh --cluster-crn crn:cdp:datahub:us-east-1:123:cluster:my-dh --type datahub
```

### Help and Version

```bash
./rds_baseline.sh --help
./rds_baseline.sh --version
```

## Output Files

### CSV Report (`rds_baseline_report.csv`)

Contains the following columns:

- **Endpoint**: RDS instance endpoint
- **DB Instance ID**: RDS instance identifier
- **Engine Version**: Database engine version
- **Created Time**: Instance creation timestamp
- **Instance Class**: AWS instance type
- **vCPU**: Number of virtual CPUs (automatically mapped from instance class)
- **RAM**: Memory configuration (automatically mapped from instance class)
- **Primary Storage Encryption**: Storage encryption status
- **Primary Storage Storage Type**: Storage type (gp2, gp3, io1, etc.)
- **Primary Storage Storage (GB)**: Allocated storage in GB
- **Primary Storage Provisioned IOPS**: Provisioned IOPS (if applicable)
- **Primary Storage Storage Throughput (MB/s)**: Storage throughput (if applicable)

### JSON Files

- `rds_summary.json`: Condensed RDS configuration summary
- `db_instance.json`: Full RDS instance details
- `db_parameters.json`: Database parameter group settings
- `subnet_group.json`: Subnet group configuration
- `vpc.json`: VPC details
- `security_groups/`: Security group configurations
- `subnets/`: Subnet details

## Example Output

```
📊 RDS Baseline Report:
========================
"dbsvr-16b6c7c5-5b06-4208-acfe-3734a1aaf655.cx9bqfeps2qo.us-east-2.rds.amazonaws.com","dbsvr-16b6c7c5-5b06-4208-acfe-3734a1aaf655","14.17","2025-08-16T10:50:29.570000+00:00","db.m5.large","2","8GB","true","gp3","100","3000","N/A"

📁 Generated Files Summary:
============================
CSV Report: /tmp/rds_baseline_20250818142736/rds_baseline_report.csv
Summary JSON: /tmp/rds_baseline_20250818142736/rds_summary.json
Full Instance Details: /tmp/rds_baseline_20250818142736/db_instance.json
Parameter Group: /tmp/rds_baseline_20250818142736/db_parameters.json
Subnet Group: /tmp/rds_baseline_20250818142736/subnet_group.json
VPC Details: /tmp/rds_baseline_20250818142736/vpc.json
Security Groups: /tmp/rds_baseline_20250818142736/security_groups/
Subnets: /tmp/rds_baseline_20250818142736/subnets/

💡 Tip: Open the CSV file in Excel or Google Sheets for better formatting
```

## Enhanced Features

### Error Handling & Validation

- **File Existence Checks**: Validates all required JSON files before CSV generation
- **JSON Data Validation**: Ensures RDS instance data is properly structured
- **Graceful Fallbacks**: Uses "N/A" for missing or unavailable data
- **Comprehensive Error Messages**: Clear feedback for troubleshooting

### User Experience

- **Help System**: `--help` flag with detailed usage instructions
- **Version Information**: `--version` flag to check script version
- **Progress Logging**: Step-by-step progress indicators
- **File Summary**: Clear overview of all generated outputs

## Error Handling

The script includes comprehensive error handling for:

- Missing required tools (AWS CLI, jq)
- Invalid regions
- RDS instance not found
- CDP CLI authentication issues
- JSON parsing failures
- Missing or corrupted JSON files
- CSV generation failures

## Troubleshooting

- **"CDP CLI not found"**: Install CDP CLI Beta from the official documentation
- **"RDS instance not found"**: Verify the instance identifier and region
- **"Permission denied"**: Ensure your AWS credentials have RDS read permissions
- **"jq command not found"**: Install jq: `sudo apt-get install jq` (Ubuntu) or `brew install jq` (macOS)
- **"Empty CSV report"**: Check that the JSON files contain valid RDS instance data
- **"Invalid RDS instance data"**: Verify the AWS CLI has proper permissions and the instance exists

## Version History

- **v2.0.0**: Added CSV report generation, smart vCPU/RAM detection, enhanced error handling
- **v1.0.0**: Initial release with JSON metadata collection and CDP CLI integration
