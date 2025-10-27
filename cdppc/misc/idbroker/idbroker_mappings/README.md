# IDBroker Mappings Validator

A Python tool that validates IDBroker mappings by checking if users and groups exist in CDP before creating a new mapping list. This helps prevent "NOT_FOUND" errors during datalake creation.

## Overview

When creating datalakes in CDP, IDBroker mappings must reference valid users and groups. Invalid references cause failures with errors like:

```
Datalake creation failed. Unable to get mappings: Error during IDBMMS operation:
NOT_FOUND: Actor or group crn:altus:iam:us-west-1:a7b3c9d2-4f5e-4a8b-9c3d-2e1f6a8b5c9d:user:b8c4d1e3-6a7f-4c9b-8d2e-3f4a7b9c6d1e not found
```

This tool validates all mappings against your CDP environment and creates a clean mapping list with only valid entries.

## Features

- **User Validation**: Checks if user CRNs exist in CDP
- **Group Validation**: Verifies group existence and membership
- **Clean Output**: Generates validated mapping lists ready for use
- **Detailed Reporting**: Shows which mappings are valid/invalid and why
- **Flexible Input**: Supports file input or stdin
- **Error Handling**: Comprehensive error handling and reporting

## Prerequisites

- Python 3.6 or higher
- CDP CLI installed and configured
- `jq` command-line JSON processor
- Valid CDP credentials with appropriate permissions

### Required CDP Permissions

Your CDP user needs the following permissions:

- `iam:ListUsers` - List users in the account
- `iam:ListGroups` - List groups in the account
- `iam:ListGroupMembers` - List members of specific groups

### CDP CLI Setup

1. Install CDP CLI:

   ```bash
   pip install cdpcli
   ```

2. Install jq (if not already installed):

   ```bash
   # On macOS
   brew install jq

   # On Ubuntu/Debian
   sudo apt-get install jq

   # On RHEL/CentOS
   sudo yum install jq

   # Or download from: https://stedolan.github.io/jq/download/
   ```

3. Configure CDP credentials:

   ```bash
   cdp configure
   ```

4. Test connectivity:
   ```bash
   cdp iam list-users --max-items 1
   ```

### Extract Current IDBroker Mappings (Required First Step)

Before validating mappings, you need to extract the current IDBroker mappings from your CDP environment. You can either pipe the output directly to the validator or save it to a file first.

#### Option 1: Save to File First (Recommended)

```bash
# Set your environment name
ENV_NAME="cldr-cdp-env"

# Extract current mappings and save to timestamped backup file
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
      else {} end)' | jq . | tee /tmp/${ENV_NAME}_idbroker_mappings-$(date +"%Y%m%d%H%M%S").json
```

This creates a backup file at `/tmp/cldr-cdp-env_idbroker_mappings-YYYYMMDDHHMMSS.json`

#### Option 2: Pipe Directly to Validator

```bash
# Extract and validate in one command
ENV_NAME="cldr-cdp-env"

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
| python3 validates_mappings.py --stdin --output clean_${ENV_NAME}_mappings.json
```

**Note**: Option 1 is recommended as it creates a backup of your current mappings before validation.

## Installation

1. Clone or download the script:

   ```bash
   mkdir -p /tmp/idbroker_mappings
   # Copy validates_mappings.py to the directory
   ```

2. Make executable:
   ```bash
   chmod +x validates_mappings.py
   ```

## Usage

### Basic Usage

```bash
# Validate mappings from a file
python3 validates_mappings.py input_mappings.json

# Read from stdin
cat input_mappings.json | python3 validates_mappings.py --stdin

# Specify custom output file
python3 validates_mappings.py input_mappings.json --output clean_mappings.json
```

### Command Line Options

- `input_file`: Path to JSON file containing mappings (optional if using --stdin)
- `--stdin`: Read input from standard input
- `--output`, `-o`: Output file for clean mappings (default: clean_mappings.json)

### Example Workflow

1. **Extract current IDBroker mappings from CDP**:

   ```bash
   # Set your environment name
   ENV_NAME="my-datalake"

   # Extract and save current mappings to a timestamped backup file
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
         else {} end)' | jq . | tee /tmp/${ENV_NAME}_idbroker_mappings-$(date +"%Y%m%d%H%M%S").json
   ```

2. **Validate the extracted mappings**:

   ```bash
   # Use the most recent backup file
   MAPPING_FILE=$(ls -t /tmp/${ENV_NAME}_idbroker_mappings-*.json | head -1)
   python3 validates_mappings.py "$MAPPING_FILE" --output /tmp/clean_${ENV_NAME}_mappings.json
   ```

3. **Use the clean output**:

   ```bash
   # The script creates clean_mappings.json with only valid mappings
   # Use this file for your datalake operations or updates

   # For example, to update IDBroker mappings:
   # cdp environments set-id-broker-mappings --cli-input-json file:///tmp/clean_${ENV_NAME}_mappings.json
   ```

## Input Format

The script expects JSON data with the following structure:

```json
{
  "environmentName": "string",
  "dataAccessRole": "arn:aws:iam::account:role/role-name",
  "rangerAuditRole": "arn:aws:iam::account:role/role-name",
  "baselineRole": "arn:aws:iam::account:role/role-name",
  "mappings": [
    {
      "accessorCrn": "crn:altus:iam:region:account:user:user-id",
      "role": "arn:aws:iam::account:role/role-name"
    },
    {
      "accessorCrn": "crn:altus:iam:region:account:group:group-name/group-id",
      "role": "arn:aws:iam::account:role/role-name"
    }
  ],
  "setEmptyMappings": false
}
```

### CRN Format

Accessor CRNs must follow the CDP format:

- **Users**: `crn:altus:iam:region:account:user:user-name/user-id`
- **Groups**: `crn:altus:iam:region:account:group:group-name/group-id`

## Output

### Console Output

The script provides detailed console output:

```
Loading existing users...
Loaded 150 users
Loading existing groups...
Loaded 25 groups

Validating 10 mappings...
Loading group members...
Loaded 5 members for group my-group

✓ Valid user: john.doe (crn:altus:iam:us-west-1:account:user:john.doe/user-id)
✗ Invalid user: jane.doe (crn:altus:iam:us-west-1:account:user:jane.doe/invalid-id)
✓ Valid group: my-group (crn:altus:iam:us-west-1:account:group:my-group/group-id)

============================================================
VALIDATION SUMMARY
============================================================
Total mappings processed: 10
Valid mappings: 8
Invalid mappings: 2

INVALID MAPPINGS (will be excluded):
  - jane.doe (crn:altus:iam:us-west-1:account:user:jane.doe/invalid-id)
  - old-group (crn:altus:iam:us-west-1:account:group:old-group/old-id)

Clean mappings saved to: clean_mappings.json
```

### Output File

The script generates a clean JSON file containing only valid mappings:

```json
{
  "environmentName": "my-datalake",
  "dataAccessRole": "arn:aws:iam::123456789012:role/datalake-admin",
  "rangerAuditRole": "arn:aws:iam::123456789012:role/ranger-audit",
  "baselineRole": "arn:aws:iam::123456789012:role/baseline",
  "mappings": [
    {
      "accessorCrn": "crn:altus:iam:us-west-1:account:user:john.doe/user-id",
      "role": "arn:aws:iam::123456789012:role/user-role"
    }
  ],
  "setEmptyMappings": false
}
```

## Exit Codes

- `0`: All mappings are valid
- `1`: Some mappings are invalid (check output for details)
- `2`: Script error (invalid input, CDP CLI issues, etc.)

## How It Works

### Validation Process

1. **Load CDP Data**:

   - Fetches all users using `cdp iam list-users`
   - Fetches all groups using `cdp iam list-groups`
   - Loads group members using `cdp iam list-group-members`

2. **Parse Mappings**:

   - Extracts entity information from CRNs
   - Determines if each mapping is a user or group
   - Identifies entity names and IDs

3. **Validate Entries**:

   - **Users**: Checks if user CRN exists in CDP
   - **Groups**: Verifies group exists and has members

4. **Generate Output**:
   - Creates clean mapping list with only valid entries
   - Provides detailed validation report
   - Saves results to output file

### Performance Considerations

- **Batch Loading**: Loads all users/groups upfront for efficient validation
- **On-Demand Group Members**: Only loads group members for groups in mappings
- **Memory Efficient**: Uses sets for fast lookups
- **Large Datasets**: Handles up to 10,000 users/groups per account

## Troubleshooting

### Common Issues

#### CDP CLI Not Found

```
Error: CDP CLI command failed: cdp: command not found
```

**Solution**: Install CDP CLI with `pip install cdpcli`

#### Authentication Errors

```
Error: CDP CLI command failed: Authentication failed
```

**Solution**: Run `cdp configure` to set up credentials

#### Permission Denied

```
Error: CDP CLI command failed: Access denied
```

**Solution**: Ensure your user has required IAM permissions

#### Invalid JSON Input

```
Error: Invalid JSON input: Expecting ',' delimiter: line 5 column 10
```

**Solution**: Validate your JSON input file format

### Debug Mode

For detailed debugging, you can modify the script to add more verbose output:

```python
# Add this to see CDP CLI commands being executed
print(f"Executing: {' '.join(command)}")
```

### Performance Issues

For large environments:

- Run during off-peak hours
- Consider increasing CDP CLI timeout settings
- Monitor memory usage with very large datasets

## Examples

### Example 1: Basic Validation with Real Data

```bash
# Step 1: Extract current mappings from CDP environment
ENV_NAME="test-dl"
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
      else {} end)' | jq . > /tmp/${ENV_NAME}_mappings.json

# Step 2: Validate the extracted mappings
python3 validates_mappings.py /tmp/${ENV_NAME}_mappings.json

# Step 3: Review and use the cleaned mappings
cat clean_mappings.json
```

### Example 2: Pipeline Integration

```bash
# In a CI/CD pipeline - Extract, validate, and update

ENV_NAME="production-dl"

# Extract current mappings
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
      else {} end)' | jq . > /tmp/${ENV_NAME}_mappings.json

# Validate mappings
python3 validates_mappings.py /tmp/${ENV_NAME}_mappings.json --output /tmp/validated_${ENV_NAME}_mappings.json

# Check exit code
if [ $? -eq 0 ]; then
    echo "All mappings valid, proceeding with update"
    # Use validated_mappings.json to update IDBroker mappings
    # cdp environments set-id-broker-mappings --cli-input-json file:///tmp/validated_${ENV_NAME}_mappings.json
else
    echo "Invalid mappings found, review and fix"
    exit 1
fi
```

### Example 3: Batch Processing Multiple Environments

```bash
# Process multiple environments
ENVIRONMENTS=("dev-dl" "staging-dl" "prod-dl")

for ENV_NAME in "${ENVIRONMENTS[@]}"; do
    echo "Processing environment: $ENV_NAME"

    # Extract mappings
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
          else {} end)' | jq . > /tmp/${ENV_NAME}_mappings.json

    # Validate
    python3 validates_mappings.py /tmp/${ENV_NAME}_mappings.json --output /tmp/validated_${ENV_NAME}_mappings.json

    if [ $? -eq 0 ]; then
        echo "✓ $ENV_NAME: All mappings valid"
    else
        echo "✗ $ENV_NAME: Invalid mappings found"
    fi
done
```
