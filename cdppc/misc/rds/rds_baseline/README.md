# RDS Baseline Collector with CDP CLI Integration and Interactive AWS Region Validation

## Overview

This script collects detailed baseline metadata from an AWS RDS instance, supporting two input modes:

- Directly providing the RDS DB instance identifier.
- Providing a CDP cluster CRN (`datalake` or `datahub`) and cluster type, to resolve the DB identifier via the **CDP CLI Beta**.

It automatically handles AWS region validation and discovery, ensuring accurate API calls and improving the user experience with an interactive menu.

## Features

- Accepts either:
  - RDS DB instance identifier directly.
  - CDP cluster CRN plus cluster type (`datalake` or `datahub`) to resolve the DB identifier.
- Validates:
  - CDP CLI Beta installation and authentication.
  - CRN pattern matches the specified cluster type.
  - AWS region validity against official AWS regions.
- Interactive AWS region selection menu if an invalid or no region is provided.
- Automatic AWS region discovery by querying all regions if necessary.
- Detailed data collection:
  - RDS DB instance description
  - DB parameter group details
  - DB subnet group details
  - Security groups descriptions
  - VPC and subnet descriptions
- Organized output saved to timestamped directory under `/tmp`.

## Requirements

- AWS CLI configured with necessary permissions.
- `jq` installed for JSON parsing.
- CDP CLI Beta installed and configured if using cluster CRNs.

## Usage

```bash
# Using direct DB identifier:
./rds_baseline.sh <db-identifier> [--region <aws-region>]

# Using CDP cluster CRN and type:
./rds_baseline.sh --cluster-crn <crn> --type <datalake|datahub> [--region <aws-region>]
```

Example:

```bash
./rds_baseline.sh --cluster-crn crn:cdp:datalake:us-east-1:acct:datalake:abc123 --type datalake
```

If the AWS region is not specified or invalid, you will be presented with an interactive menu to select or auto-discover the correct region.

## Output

All collected metadata will be saved under `/tmp/rds_baseline_<timestamp>/` with JSON files organized by resource type.

## Notes

- The script requires valid AWS credentials configured (`~/.aws/credentials` or environment variables).
- For CDP CLI usage, ensure you have the Beta CLI version installed and authenticated (`cdp configure`).
- If the DB instance cannot be found in any region, the script will exit with an error.
