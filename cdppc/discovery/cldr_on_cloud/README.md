# CDP Discovery All Instances

A comprehensive Python script for discovering and analyzing all Cloudera Data Platform (CDP) resources across environments, with AWS cost analysis and resource enrichment.

## Overview

This script performs a complete discovery of CDP resources including:
- **DataHub clusters** and their instance groups
- **Datalakes** and associated database servers
- **FreeIPA** instances
- **ML Workspaces** (Cloudera AI)
- **Operational Databases** (OpDB/COD)
- **Data Engineering** workspaces
- **Data Warehouse** resources
- **DataFlow** deployments

The script enriches discovered resources with AWS metadata and cost information:
- **EC2 instance** details and pricing
- **EBS volume** information
- **RDS database** server details
- **Cost Explorer** analysis for EC2, EBS, and RDS

## Features

### Resource Discovery
- Discovers all CDP resources in a specified environment
- Extracts instance group information with detailed metadata
- Captures upgrade options and available images
- Handles multiple CDP service types (DataHub, Datalake, ML, etc.)

### AWS Integration
- Enriches CDP instances with EC2 metadata
- Discovers and analyzes EBS volumes
- Identifies and describes RDS database servers
- Extracts AWS tags and resource relationships

### Cost Analysis
- Queries AWS Cost Explorer for historical costs
- Provides daily cost breakdowns by service type
- Filters costs by Cloudera-Resource-Name tags
- Generates comprehensive cost summaries

### Output Formats
- **JSON**: Raw resource descriptions and metadata
- **CSV**: Flattened instance data for analysis
- **Archived**: Compressed output for easy sharing

## Prerequisites

### Required Tools
- **Python 3.7+** with the following packages:
  - `boto3` (AWS SDK)
  - Standard library modules: `argparse`, `csv`, `json`, `os`, `shutil`, `subprocess`, `sys`, `pathlib`, `datetime`, `collections`

### CDP CLI Setup
- **CDP CLI** installed and configured
- Valid CDP profiles in `~/.cdp/credentials`
- Appropriate permissions for the target environment

### AWS Configuration
- **AWS CLI** configured or AWS credentials available
- Permissions for:
  - EC2: `DescribeInstances`, `DescribeVolumes`
  - RDS: `DescribeDBInstances`
  - Cost Explorer: `GetCostAndUsage`
  - IAM permissions for resource tagging

## Installation

1. Clone the repository:
```bash
git clone git@github.com:garagorry/cldr.git
cd cldr/cdppc/discovery/cldr_on_cloud
```

2. Install Python dependencies:
```bash
pip install boto3
```

3. Ensure CDP CLI is installed and configured:
```bash
cdp --version
cdp environments list-environments --profile your-profile
```

## Usage

### Basic Usage
```bash
python cldr_discovery_all_instances.py \
  --environment-name your-env-name \
  --profile your-cdp-profile
```

### Advanced Options
```bash
python cldr_discovery_all_instances.py \
  --environment-name your-env-name \
  --profile your-cdp-profile \
  --output-dir /path/to/output \
  --cost-days 60 \
  --debug
```

### Command Line Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--environment-name` | Yes | - | CDP environment name to discover |
| `--profile` | No | `default` | CDP CLI profile to use |
| `--output-dir` | No | `/tmp/cldr_discovery-<timestamp>` | Output directory |
| `--cost-days` | No | `30` | Days of cost data to retrieve |
| `--debug` | No | `False` | Enable debug logging |

## Output Structure

The script generates a comprehensive output structure:

```
/tmp/cldr_discovery-<timestamp>/
├── environment/
│   ├── ENV_<env-name>.json
│   ├── FREEIPA_<env-name>.json
│   └── FREEIPA_<env-name>_UpgradeOptions.json
├── datalake/
│   └── <datalake-name>/
│       ├── DL_<datalake-name>.json
│       ├── DL_<datalake-name>_DB.json
│       ├── DL_<datalake-name>_AvailableImages.json
│       └── DL_<datalake-name>_InstanceGroups.csv
├── datahubs/
│   └── <cluster-name>/
│       ├── DH_<cluster-name>.json
│       ├── DH_<cluster-name>_AvailableImages.json
│       ├── DH_<cluster-name>_COD_<db-name>.json
│       └── DH_<cluster-name>_InstanceGroups.csv
├── ml/
│   └── <workspace-name>/
│       └── ML_<workspace-name>.json
├── opdb/
│   └── <database-name>/
│       └── OPDB_<database-name>.json
├── de/
│   └── <workspace-name>/
│       ├── DE_<workspace-name>_list.json
│       ├── DE_<workspace-name>_virtual_clusters.json
│       └── <virtual-cluster-name>/
│           └── DE_<virtual-cluster-name>.json
├── dw/
│   ├── DW_database_catalogs.json
│   └── DW_virtual_warehouses.json
├── dataflow/
│   ├── DF_environments.json
│   └── DF_deployments_<env-crn>.json
├── aws/
│   ├── ec2_instances.csv
│   ├── ebs_volumes.csv
│   └── rds_instances.csv
├── costs/
│   ├── summary.csv
│   └── <region>/
│       ├── ec2_daily_<tag>.csv
│       ├── ebs_daily_<tag>.csv
│       └── rds_daily_<tag>.csv
└── flattened/
    ├── cdp_instances_flat.csv
    └── _summary.json
```

## Key Output Files

### Instance Groups CSV
Contains flattened instance data with columns:
- `environment`, `sourceType`, `sourceName`, `hostgroup`
- `instanceId`, `instanceType`, `state`, `privateIp`, `publicIp`
- `availabilityZone`, `subnetId`, `recipes`
- `attachedVolume_count`, `attachedVolume_size`, `attachedVolume_type`

### AWS Enrichment CSVs
- **ec2_instances.csv**: EC2 metadata including tags, launch time, architecture
- **ebs_volumes.csv**: EBS volume details including size, type, encryption
- **rds_instances.csv**: RDS database server information

### Cost Analysis
- **summary.csv**: Aggregated costs by region and Cloudera-Resource-Name tag
- **Daily CSVs**: Detailed daily cost breakdowns by service type

## Examples

### Discover Production Environment
```bash
python cldr_discovery_all_instances.py \
  --environment-name prod-cluster \
  --profile production \
  --cost-days 90 \
  --output-dir /tmp/prod-discovery
```

### Debug Mode for Troubleshooting
```bash
python cldr_discovery_all_instances.py \
  --environment-name test-env \
  --profile test \
  --debug
```

## Error Handling

The script includes comprehensive error handling:
- **Graceful degradation**: Continues processing if individual resources fail
- **Detailed logging**: Debug mode provides extensive troubleshooting information
- **Resource validation**: Validates required fields before processing
- **AWS API resilience**: Handles rate limiting and API errors

## Troubleshooting

### Common Issues

1. **CDP CLI Profile Not Found**
   ```
   ⚠️ Profile 'your-profile' not found. Available: ['default', 'prod']
   ```
   - Verify profile exists in `~/.cdp/credentials`
   - Check profile name spelling

2. **AWS Permissions Error**
   ```
   ⚠️ Failed EC2/Volumes describe in us-east-1: AccessDenied
   ```
   - Ensure AWS credentials have required permissions
   - Check IAM policies for EC2, RDS, and Cost Explorer

3. **Environment Not Found**
   ```
   ⚠️ Failed to describe environment your-env
   ```
   - Verify environment name exists
   - Check CDP profile has access to environment

### Debug Mode
Enable debug logging for detailed troubleshooting:
```bash
python cldr_discovery_all_instances.py --debug --environment-name your-env
```

## Performance Considerations

- **Large environments**: Processing time scales with resource count
- **Cost queries**: AWS Cost Explorer has API rate limits
- **Memory usage**: Large JSON responses are processed in memory
- **Network**: Multiple API calls to CDP and AWS services

## Security Notes

- **Credentials**: Script uses existing CDP CLI and AWS configurations
- **Data sensitivity**: Output contains resource metadata and cost information
- **Access control**: Ensure appropriate permissions for target environments
- **Data retention**: Consider data retention policies for output files

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is part of the CLDR (Cloudera) toolkit. Please refer to the main repository license.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Enable debug mode for detailed logging
3. Review CDP CLI and AWS CLI configurations
4. Create an issue in the repository

## Changelog

### Version 1.0.0
- Initial release with comprehensive CDP resource discovery
- AWS EC2, EBS, and RDS enrichment
- Cost Explorer integration
- Multi-format output (JSON, CSV, archived)
- Support for all major CDP service types
