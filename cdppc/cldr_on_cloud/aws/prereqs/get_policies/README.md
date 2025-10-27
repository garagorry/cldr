# AWS IAM Policy Downloader

A Python script to download all attached managed and inline IAM policies, plus trust relationships, for a specified AWS role. The script saves each policy as a JSON file and optionally creates a compressed bundle.

## Features

- Downloads both managed and inline IAM policies
- **Downloads trust relationships (AssumeRolePolicyDocument)**
- **Extracts and categorizes trusted entities:**
  - AWS principals (accounts, users, roles)
  - Service principals
  - Federated identities (SAML, OIDC)
  - Conditions for assuming the role
- Saves policies as formatted JSON files
- Automatic timestamp-based directory naming
- Automatic .tgz bundle creation with timestamp
- Comprehensive logging to file and console
- Error handling for AWS API calls

## Prerequisites

- Python 3.6+
- boto3 library
- AWS credentials configured via one of:
  - Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
  - AWS credentials file (`~/.aws/credentials`)
  - IAM instance profile (when running on EC2)

## Installation

```bash
pip install boto3
```

## Usage

### Basic Usage

Download policies and trust relationships for a role to a temporary directory:

```bash
python aws_get_xa_attached_policies.py --role-name my-iam-role
```

### Specify Output Directory

Download policies and trust relationships to a specific directory:

```bash
python aws_get_xa_attached_policies.py --role-name my-iam-role --output /path/to/output
```

A `.tgz` bundle is automatically created with all downloaded files.

## Arguments

| Argument      | Required | Description                                                    |
| ------------- | -------- | -------------------------------------------------------------- |
| `--role-name` | Yes      | Name of the IAM role to download policies from                 |
| `--output`    | No       | Output directory for policy files (always creates .tgz bundle) |

## Output Structure

### Without `--output` flag

```
/tmp/role-name_20231201_143022/
├── execution.log
├── role-name_trust_relationship.json
├── PolicyName1.json
├── PolicyName2.json
└── role-name_inline-policy-name_inline.json
```

### With `--output` flag

```
/path/to/output/
├── output_role-name_20231201_143022/
│   ├── execution.log
│   ├── role-name_trust_relationship.json
│   ├── PolicyName1.json
│   ├── PolicyName2.json
│   └── role-name_inline-policy-name_inline.json
└── role-name_20231201_143022.tgz
```

## File Naming Convention

- **Trust relationship**: `<RoleName>_trust_relationship.json`
- **Managed policies**: `<PolicyName>.json`
- **Inline policies**: `<RoleName>_<PolicyName>_inline.json`
- **Log file**: `execution.log`
- **Bundle**: `<role_name>_<timestamp>.tgz`

## Trust Relationship File Contents

The `<RoleName>_trust_relationship.json` file contains comprehensive information about who can assume the role and under what conditions:

```json
{
  "RoleName": "example-role",
  "RoleArn": "arn:aws:iam::123456789012:role/example-role",
  "CreatedDate": "2023-12-01T14:30:22",
  "Description": "Role description",
  "MaxSessionDuration": 3600,
  "AssumeRolePolicyDocument": {
    "Version": "2012-10-17",
    "Statement": [...]
  },
  "TrustedEntities": {
    "AWS": ["arn:aws:iam::987654321098:root"],
    "Service": ["ec2.amazonaws.com", "lambda.amazonaws.com"],
    "Federated": ["arn:aws:iam::123456789012:saml-provider/ExampleProvider"],
    "Conditions": [
      {
        "Statement": "StatementId",
        "Principal": {...},
        "Condition": {...}
      }
    ]
  }
}
```

## Examples

### Download policies for a development role

```bash
python aws_get_xa_attached_policies.py --role-name dev-application-role
```

### Download and bundle policies for production

```bash
python aws_get_xa_attached_policies.py --role-name prod-database-role --output ./policy-backups
```

### Download policies for a cross-account role

```bash
python aws_get_xa_attached_policies.py --role-name cross-account-access-role --output /shared/policies
```

## Error Handling

The script handles various error scenarios:

- Invalid role names
- Missing AWS permissions
- Network connectivity issues
- Invalid policy versions
- File system errors

All errors are logged to both the console and the execution log file.

## Logging

The script provides detailed logging including:

- Policy discovery and download progress
- Error messages with context
- File creation confirmations
- Bundle creation status

Logs are written to both:

- Console output (stdout)
- `execution.log` file in the output directory

## Security Considerations

- Ensure AWS credentials have appropriate IAM permissions
- Review downloaded policies before sharing
- Consider encrypting sensitive policy files
- Use temporary directories for sensitive operations

## Required IAM Permissions

The script requires the following IAM permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iam:GetRole",
        "iam:ListAttachedRolePolicies",
        "iam:ListRolePolicies",
        "iam:GetPolicy",
        "iam:GetPolicyVersion",
        "iam:GetRolePolicy"
      ],
      "Resource": "*"
    }
  ]
}
```

**Note**: `iam:GetRole` is required to retrieve the trust relationship (AssumeRolePolicyDocument) and role metadata.

## Troubleshooting

### Common Issues

1. **Access Denied**: Ensure AWS credentials have proper IAM permissions
2. **Role Not Found**: Verify the role name exists in the current AWS account
3. **No Policies Found**: The role may not have any attached policies
4. **Permission Errors**: Check if the role has policies that require additional permissions

### Debug Mode

For additional debugging, you can modify the logging level in the script:

```python
logger.setLevel(logging.DEBUG)
```
