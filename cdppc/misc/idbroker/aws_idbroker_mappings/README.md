# AWS IAM Role Validator for IDBroker Mappings

This tool validates IDBroker mappings by checking if the AWS IAM roles exist using AWS CLI. It helps identify missing or incorrect role ARNs before creating IDBroker mappings in CDP.

## Prerequisites

1. **Python 3.6+** installed on your system
2. **AWS CLI** installed and configured

   ```bash
   # Install AWS CLI
   pip install awscli

   # Configure AWS CLI with your credentials
   aws configure
   ```

3. Appropriate AWS IAM permissions to read role information (`iam:GetRole`)

## Features

- ✅ Validates AWS IAM role existence for all IDBroker mappings
- ✅ Supports multiple AWS profiles
- ✅ Generates detailed validation reports in JSON format
- ✅ Creates clean mapping files with only valid roles
- ✅ Provides clear console output with validation status
- ✅ Identifies which users/groups are affected by missing roles
- ✅ Caches role validation to avoid duplicate AWS API calls

## Installation

```bash
# Make the script executable
chmod +x validate_aws_roles.py

# No additional dependencies needed beyond standard library and AWS CLI
```

## Usage

### Basic Usage

```bash
# Validate mappings from a JSON file
python validate_aws_roles.py mappings.json

# Or make it executable and run directly
./validate_aws_roles.py mappings.json
```

### With AWS Profile

```bash
# Use a specific AWS profile
python validate_aws_roles.py mappings.json --aws-profile production

# Or set the profile as an environment variable
export AWS_PROFILE=production
python validate_aws_roles.py mappings.json
```

### Read from stdin

```bash
# Read mappings from stdin
cat mappings.json | python validate_aws_roles.py --stdin

# Or from CDP CLI output (simple)
cdp environments get-id-broker-mappings --environment-name my-env | python validate_aws_roles.py --stdin

# Advanced: Use jq to format CDP output properly
ENV_NAME="my-env"
cdp environments get-id-broker-mappings --environment-name "$ENV_NAME" \
| jq -c --arg env "$ENV_NAME" '{
    environmentName: $env,
    dataAccessRole: .dataAccessRole,
    rangerAuditRole: .rangerAuditRole,
    baselineRole: .baselineRole,
    mappings: (.mappings // []),
    setEmptyMappings: false
  } + (if .rangerCloudAccessAuthorizerRole then
        {rangerCloudAccessAuthorizerRole: .rangerCloudAccessAuthorizerRole}
      else {} end)' \
| python validate_aws_roles.py --stdin
```

### Custom Output Files

```bash
# Specify custom output file names
python validate_aws_roles.py mappings.json \
  --output clean_mappings.json \
  --report validation_report.json
```

## Input Format

The script expects a JSON file with IDBroker mappings in the following format:

```json
{
  "mappings": [
    {
      "accessorCrn": "crn:altus:iam:us-west-1:1234567:user:username/abc123",
      "role": "arn:aws:iam::123456789012:role/CDP-DATALAKE-ADMIN-ROLE"
    },
    {
      "accessorCrn": "crn:altus:iam:us-west-1:1234567:group:groupname/xyz789",
      "role": "arn:aws:iam::123456789012:role/CDP-RANGER-AUDIT-ROLE"
    }
  ],
  "dataAccessRole": "arn:aws:iam::123456789012:role/CDP-DATALAKE-ADMIN-ROLE",
  "rangerAuditRole": "arn:aws:iam::123456789012:role/CDP-RANGER-AUDIT-ROLE",
  "rangerCloudAccessAuthorizerRole": "arn:aws:iam::123456789012:role/CDP-RANGER-RAZ-ROLE"
}
```

> **Note:** When piping from CDP CLI, the output can be used directly or formatted with `jq` to ensure all required fields are present. The `jq` formatting is especially useful for:
>
> - Ensuring consistent structure across environments
> - Adding environment name for tracking
> - Handling optional fields like `rangerCloudAccessAuthorizerRole`
> - Setting defaults like `setEmptyMappings: false`

## Output Files

The script generates two output files:

### 1. Clean Mappings File (default: `clean_aws_mappings.json`)

Contains only the valid mappings that can be safely used for IDBroker configuration:

```json
{
  "mappings": [
    {
      "accessorCrn": "crn:altus:iam:us-west-1:1234567:user:username/abc123",
      "role": "arn:aws:iam::123456789012:role/CDP-DATALAKE-ADMIN-ROLE"
    }
  ],
  "setEmptyMappings": false
}
```

### 2. Validation Report (default: `aws_role_validation_report.json`)

Contains detailed information about the validation process:

```json
{
  "validation_timestamp": "2025-10-30T12:34:56.789012",
  "aws_profile": "default",
  "summary": {
    "total_mappings": 10,
    "valid_mappings": 8,
    "invalid_mappings": 2,
    "unique_roles_found": 5,
    "existing_roles": 4,
    "missing_roles": 1
  },
  "missing_roles": [
    {
      "role_arn": "arn:aws:iam::123456789012:role/MISSING-ROLE",
      "role_name": "MISSING-ROLE",
      "error": "Role does not exist in AWS"
    }
  ],
  "invalid_mappings_details": [
    {
      "entity_type": "user",
      "entity_name": "john.doe",
      "accessor_crn": "crn:altus:iam:us-west-1:1234567:user:john.doe/abc123",
      "role_arn": "arn:aws:iam::123456789012:role/MISSING-ROLE",
      "role_name": "MISSING-ROLE",
      "error": "Role does not exist in AWS"
    }
  ]
}
```

## Console Output Example

```
Validating 10 mappings...
Found 5 unique AWS IAM roles to validate

[1/10] ✓ Valid - user: john.doe -> CDP-DATALAKE-ADMIN-ROLE
[2/10] ✓ Valid - group: data-engineers -> CDP-RANGER-AUDIT-ROLE
[3/10] ✗ Invalid - user: jane.smith -> MISSING-ROLE
    Error: Role does not exist in AWS
[4/10] ✓ Valid - user: bob.jones -> CDP-DATALAKE-ADMIN-ROLE
...

======================================================================
AWS IAM ROLE VALIDATION SUMMARY
======================================================================
Total mappings processed: 10
Valid mappings: 8
Invalid mappings: 2
Unique roles checked: 5
Existing roles: 4
Missing roles: 1

======================================================================
MISSING AWS IAM ROLES:
======================================================================
  ✗ MISSING-ROLE
    ARN: arn:aws:iam::123456789012:role/MISSING-ROLE
    Error: Role does not exist in AWS
    Affected entities: user:jane.smith, group:contractors

Detailed report saved to: aws_role_validation_report.json
Clean mappings (valid only) saved to: clean_aws_mappings.json

⚠️  2 invalid mappings were found.
Review the report (aws_role_validation_report.json) for details.
```

## Getting IDBroker Mappings from CDP

You can get the current IDBroker mappings from an existing CDP environment:

```bash
# Method 1: Save to file first, then validate
cdp environments get-id-broker-mappings \
  --environment-name my-environment \
  > current_mappings.json

python validate_aws_roles.py current_mappings.json

# Method 2: Direct pipe (simple)
cdp environments get-id-broker-mappings --environment-name my-env | \
  python validate_aws_roles.py --stdin

# Method 3: With jq formatting (recommended for production)
ENV_NAME="my-environment"
cdp environments get-id-broker-mappings --environment-name "$ENV_NAME" \
| jq -c --arg env "$ENV_NAME" '{
    environmentName: $env,
    dataAccessRole: .dataAccessRole,
    rangerAuditRole: .rangerAuditRole,
    baselineRole: .baselineRole,
    mappings: (.mappings // []),
    setEmptyMappings: false
  } + (if .rangerCloudAccessAuthorizerRole then
        {rangerCloudAccessAuthorizerRole: .rangerCloudAccessAuthorizerRole}
      else {} end)' \
| python validate_aws_roles.py --stdin --report "${ENV_NAME}_validation_report.json"
```

## Common Use Cases

### 1. Pre-flight Check Before Environment Creation

```bash
# Validate your mappings before creating the environment
python validate_aws_roles.py proposed_mappings.json --report preflight_report.json

# If validation passes, use the clean mappings
cdp environments set-id-broker-mappings \
  --environment-name my-env \
  --data-access-role "arn:aws:iam::123456789012:role/CDP-DATALAKE-ADMIN-ROLE" \
  --mappings file://clean_aws_mappings.json
```

### 2. Audit Existing Environment Mappings

```bash
# Export current mappings and validate
cdp environments get-id-broker-mappings --environment-name prod-env > prod_mappings.json
python validate_aws_roles.py prod_mappings.json --report prod_audit_report.json
```

### 3. Multi-Account Validation

```bash
# Validate against different AWS accounts
python validate_aws_roles.py dev_mappings.json --aws-profile dev-account
python validate_aws_roles.py prod_mappings.json --aws-profile prod-account
```

### 4. Identify Missing Roles for Creation

```bash
# Run validation and review the report
python validate_aws_roles.py mappings.json

# Extract missing role names from the report
jq -r '.missing_roles[].role_name' aws_role_validation_report.json

# Create the missing roles in AWS
# ... (your role creation process)

# Re-validate
python validate_aws_roles.py mappings.json
```

### 5. Complete Workflow with jq Formatting

```bash
#!/bin/bash
# Complete validation workflow with proper data formatting

ENV_NAME="production-env"
AWS_PROFILE="production"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "Validating IDBroker mappings for environment: $ENV_NAME"

# Get mappings from CDP, format with jq, and validate
cdp environments get-id-broker-mappings --environment-name "$ENV_NAME" \
| jq -c --arg env "$ENV_NAME" '{
    environmentName: $env,
    dataAccessRole: .dataAccessRole,
    rangerAuditRole: .rangerAuditRole,
    baselineRole: .baselineRole,
    mappings: (.mappings // []),
    setEmptyMappings: false
  } + (if .rangerCloudAccessAuthorizerRole then
        {rangerCloudAccessAuthorizerRole: .rangerCloudAccessAuthorizerRole}
      else {} end)' \
| python validate_aws_roles.py --stdin \
    --aws-profile "$AWS_PROFILE" \
    --output "validated_mappings_${ENV_NAME}_${TIMESTAMP}.json" \
    --report "validation_report_${ENV_NAME}_${TIMESTAMP}.json"

# Check exit code
if [ $? -eq 0 ]; then
    echo "✓ All mappings validated successfully"
    echo "Clean mappings saved with timestamp: ${TIMESTAMP}"
else
    echo "✗ Validation failed - review report for details"
    echo "Report: validation_report_${ENV_NAME}_${TIMESTAMP}.json"
    exit 1
fi
```

## Exit Codes

- `0`: All mappings are valid
- `1`: One or more invalid mappings found, or CLI error occurred
- `130`: Validation interrupted by user (Ctrl+C)

## Troubleshooting

### AWS CLI Not Configured

```
Error: AWS CLI command failed: Unable to locate credentials
```

**Solution:** Configure AWS CLI with `aws configure` or set environment variables:

```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-west-2
```

### Permission Denied

```
Error: AWS CLI command failed: AccessDenied
```

**Solution:** Ensure your AWS user/role has `iam:GetRole` permission:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iam:GetRole",
      "Resource": "*"
    }
  ]
}
```

### Invalid JSON Input

```
Error: Invalid JSON in file: Expecting value: line 1 column 1 (char 0)
```

**Solution:** Verify your JSON file is valid:

```bash
cat mappings.json | jq .
```

## Comparison with validates_mappings.py

| Feature       | validate_aws_roles.py           | validates_mappings.py       |
| ------------- | ------------------------------- | --------------------------- |
| **Validates** | AWS IAM Roles                   | CDP Users/Groups            |
| **Uses**      | AWS CLI                         | CDP CLI                     |
| **Checks**    | Role existence in AWS           | User/Group existence in CDP |
| **Purpose**   | Pre-validate AWS infrastructure | Pre-validate CDP identities |
| **Output**    | Missing roles report            | Missing users/groups report |

## Best Practices

1. **Always validate before creating/updating IDBroker mappings**
2. **Use the validation report to identify infrastructure gaps**
3. **Keep a copy of validation reports for audit purposes**
4. **Re-validate after creating missing roles in AWS**
5. **Use specific AWS profiles for different environments**
6. **Integrate into CI/CD pipelines for automated validation**

## Integration Example

### Option 1: File-based validation

```bash
#!/bin/bash
# Example deployment script with validation

MAPPINGS_FILE="idbroker_mappings.json"
AWS_PROFILE="production"

echo "Validating IDBroker mappings..."
python validate_aws_roles.py "$MAPPINGS_FILE" --aws-profile "$AWS_PROFILE"

if [ $? -eq 0 ]; then
    echo "✓ All roles validated successfully"
    echo "Applying IDBroker mappings..."
    cdp environments set-id-broker-mappings \
        --environment-name prod-env \
        --mappings file://clean_aws_mappings.json
else
    echo "✗ Validation failed. Check aws_role_validation_report.json"
    exit 1
fi
```

### Option 2: Direct from CDP with jq formatting

```bash
#!/bin/bash
# Validate directly from CDP environment

ENV_NAME="production-env"
AWS_PROFILE="production"

echo "Fetching and validating IDBroker mappings from $ENV_NAME..."

# Get, format, and validate in one pipeline
cdp environments get-id-broker-mappings --environment-name "$ENV_NAME" \
| jq -c --arg env "$ENV_NAME" '{
    environmentName: $env,
    dataAccessRole: .dataAccessRole,
    rangerAuditRole: .rangerAuditRole,
    baselineRole: .baselineRole,
    mappings: (.mappings // []),
    setEmptyMappings: false
  } + (if .rangerCloudAccessAuthorizerRole then
        {rangerCloudAccessAuthorizerRole: .rangerCloudAccessAuthorizerRole}
      else {} end)' \
| python validate_aws_roles.py --stdin --aws-profile "$AWS_PROFILE"

if [ $? -eq 0 ]; then
    echo "✓ All AWS IAM roles validated successfully"
    echo "Mappings are ready for use"
else
    echo "✗ Validation failed - some roles are missing in AWS"
    echo "Review aws_role_validation_report.json for details"
    exit 1
fi
```
