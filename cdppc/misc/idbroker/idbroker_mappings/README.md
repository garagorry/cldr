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
- **CDP CRN Parsing**: Extracts entity names and IDs from CDP CRNs
- **Batch Loading**: Efficiently loads all users and groups upfront
- **On-Demand Group Members**: Only loads group members for groups in mappings

## Prerequisites

- Python 3.9.6 or higher
- CDP CLI installed and configured
- `jq` command-line JSON processor (optional, for formatting)
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

   # On RHEL
   sudo yum install jq

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
   mkdir -p ~/idbroker_mappings
   # Copy validates_mappings.py to the directory
   cd ~/idbroker_mappings
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

# With timestamped directory structure (auto-detects env_name from input)
cdp environments get-id-broker-mappings --environment-name "$ENV_NAME" \
| jq -c --arg env "$ENV_NAME" '{...}' \
| python3 validates_mappings.py --stdin --output clean_mappings.json

# With explicit environment name and timestamp
python3 validates_mappings.py input_mappings.json \
  --env-name "$ENV_NAME" \
  --output clean_mappings.json
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

   # Example: Update IDBroker mappings using the clean mappings file
   ENV_NAME="jdga-sbx-01-cdp-env"
   CLEAN_MAPPINGS_FILE="/tmp/clean_${ENV_NAME}_mappings.json"

   # Verify the clean mappings file exists and review its contents
   cat "$CLEAN_MAPPINGS_FILE" | jq .

   # Apply the clean mappings to the environment
   # Note: Use 'file://' prefix for local file paths
   cdp environments set-id-broker-mappings \
     --cli-input-json "file://${CLEAN_MAPPINGS_FILE}"

   # Alternative: If the file is in the current directory
   cdp environments set-id-broker-mappings \
     --cli-input-json "file://$(pwd)/clean_${ENV_NAME}_mappings.json"

   # Example with absolute path
   cdp environments set-id-broker-mappings \
     --cli-input-json "file:///home/user/projects/idbroker_mappings/clean_jdga-sbx-01-cdp-env_mappings.json"
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

Clean mappings saved to: jdga-sbx-01-cdp-env_mappings_20231223_152759/clean_jdga-sbx-01-cdp-env_mappings_20231223_152759.json
Original mappings backup saved to: jdga-sbx-01-cdp-env_mappings_20231223_152759/jdga-sbx-01-cdp-env_mappings_20231223_152759_original.json

======================================================================
VALIDATION COMPLETE - FILE LOCATIONS
======================================================================
Backup directory: ./jdga-sbx-01-cdp-env_mappings_20231223_152759
Original backup:  ./jdga-sbx-01-cdp-env_mappings_20231223_152759/jdga-sbx-01-cdp-env_mappings_20231223_152759_original.json
Clean mappings:    ./jdga-sbx-01-cdp-env_mappings_20231223_152759/clean_jdga-sbx-01-cdp-env_mappings_20231223_152759.json

======================================================================
TO APPLY THE CLEAN MAPPINGS TO YOUR CDP ENVIRONMENT
======================================================================
Use the following command:

cdp environments set-id-broker-mappings \
  --cli-input-json "file:///path/to/jdga-sbx-01-cdp-env_mappings_20231223_152759/clean_jdga-sbx-01-cdp-env_mappings_20231223_152759.json"

# Or with environment name variable:
ENV_NAME="jdga-sbx-01-cdp-env"
CLEAN_FILE="/path/to/jdga-sbx-01-cdp-env_mappings_20231223_152759/clean_jdga-sbx-01-cdp-env_mappings_20231223_152759.json"
cdp environments set-id-broker-mappings \
  --cli-input-json "file://${CLEAN_FILE}"

======================================================================
```

### Output File Structure

When the script detects an environment name (from input data or `--env-name` option), it automatically creates a timestamped directory structure:

```
${ENV_NAME}_mappings_${TIMESTAMP}/
├── ${ENV_NAME}_mappings_${TIMESTAMP}_original.json  (backup of original)
└── clean_${ENV_NAME}_mappings_${TIMESTAMP}.json      (clean validated mappings)
```

**Example:**

```
jdga-sbx-01-cdp-env_mappings_20231223_152759/
├── jdga-sbx-01-cdp-env_mappings_20231223_152759_original.json
└── clean_jdga-sbx-01-cdp-env_mappings_20231223_152759.json
```

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

## Applying Clean Mappings to CDP Environment

After validation, you can apply the clean mappings to your CDP environment using the `cdp environments set-id-broker-mappings` command.

### Basic Usage

```bash
# Apply clean mappings using the --cli-input-json option
# Note: Use 'file://' prefix for local file paths

cdp environments set-id-broker-mappings \
  --cli-input-json "file://clean_mappings.json"
```

### Examples with Different File Paths

```bash
# Example 1: File in current directory
cdp environments set-id-broker-mappings \
  --cli-input-json "file://$(pwd)/clean_jdga-sbx-01-cdp-env_mappings.json"

# Example 2: File with absolute path
cdp environments set-id-broker-mappings \
  --cli-input-json "file:///tmp/clean_jdga-sbx-01-cdp-env_mappings.json"

# Example 3: File with relative path
cdp environments set-id-broker-mappings \
  --cli-input-json "file://./clean_jdga-sbx-01-cdp-env_mappings.json"

# Example 4: Using environment variable
ENV_NAME="jdga-sbx-01-cdp-env"
CLEAN_FILE="/tmp/clean_${ENV_NAME}_mappings.json"
cdp environments set-id-broker-mappings \
  --cli-input-json "file://${CLEAN_FILE}"
```

### Complete Workflow Example

```bash
#!/bin/bash
# Complete workflow: Extract, validate, and apply mappings

ENV_NAME="jdga-sbx-01-cdp-env"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/tmp"
CLEAN_FILE="${BACKUP_DIR}/clean_${ENV_NAME}_mappings_${TIMESTAMP}.json"

# Step 1: Extract current mappings
echo "Extracting current IDBroker mappings..."
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
      else {} end)' | jq . > "${BACKUP_DIR}/${ENV_NAME}_mappings_${TIMESTAMP}.json"

# Step 2: Validate mappings
echo "Validating mappings..."
python3 validates_mappings.py "${BACKUP_DIR}/${ENV_NAME}_mappings_${TIMESTAMP}.json" \
  --output "$CLEAN_FILE"

# Step 3: Check validation result and apply if successful
if [ $? -eq 0 ]; then
    echo "✓ All mappings validated successfully"
    echo "Clean mappings saved to: $CLEAN_FILE"

    # Review the clean mappings before applying
    echo ""
    echo "Reviewing clean mappings:"
    cat "$CLEAN_FILE" | jq .

    # Prompt for confirmation (optional)
    read -p "Apply these mappings to environment '$ENV_NAME'? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Applying clean mappings to environment: $ENV_NAME"
        cdp environments set-id-broker-mappings \
          --cli-input-json "file://${CLEAN_FILE}"

        if [ $? -eq 0 ]; then
            echo "✓ IDBroker mappings successfully updated"
        else
            echo "✗ Failed to update IDBroker mappings"
            exit 1
        fi
    else
        echo "Mappings not applied. Clean file saved at: $CLEAN_FILE"
    fi
else
    echo "✗ Validation failed - mappings contain invalid entries"
    echo "Review the validation output above and fix invalid mappings"
    exit 1
fi
```

### Important Notes

- **File Path Format**: Always use the `file://` prefix when specifying local file paths
- **Absolute vs Relative Paths**: Both work, but absolute paths are more reliable
- **File Permissions**: Ensure the file is readable by the user running the CDP CLI command
- **Backup**: The script automatically creates a backup of the original mappings (see `*_original.json` files)
- **Review Before Applying**: Always review the clean mappings file before applying to production environments

#### Exceptions

- **`CDPCLIError`** - Custom exception for CDP CLI command failures

## Exit Codes

- `0`: All mappings are valid
- `1`: One or more invalid mappings found, or general error (CDP CLI issues, invalid input, etc.)

## Comparison with validate_aws_roles.py

| Feature        | validates_mappings.py           | validate_aws_roles.py                    |
| -------------- | ------------------------------- | ---------------------------------------- |
| **Validates**  | CDP Users/Groups                | AWS IAM Roles                            |
| **Uses**       | CDP CLI                         | AWS CLI                                  |
| **Checks**     | User/Group existence in CDP     | Role existence in AWS                    |
| **Purpose**    | Pre-validate CDP identities     | Pre-validate AWS infrastructure          |
| **Output**     | Missing users/groups report     | Missing roles report                     |
| **Pre-flight** | None (relies on CDP CLI errors) | AWS CLI, credentials, permissions checks |

**When to use each:**

- Use `validates_mappings.py` when you want to ensure users/groups exist in CDP before creating mappings
- Use `validate_aws_roles.py` when you want to ensure AWS IAM roles exist before creating mappings
- Use both for comprehensive validation of your IDBroker configuration

## How It Works

### Validation Process

1. **Load CDP Data**:

   - Fetches all users using `cdp iam list-users --max-items 10000`
   - Fetches all groups using `cdp iam list-groups --max-items 10000`
   - Loads group members on-demand using `cdp iam list-group-members` for groups in mappings

2. **Parse Mappings**:

   - Extracts entity information from CRNs using regex pattern matching
   - Determines if each mapping is a user or group by checking CRN structure
   - Identifies entity names and IDs from CRN format

3. **Validate Entries**:

   - **Users**: Checks if user CRN exists in loaded users set
   - **Groups**: Verifies group exists in loaded groups or has members loaded

4. **Generate Output**:
   - Creates clean mapping list with only valid entries
   - Preserves original data structure (environmentName, roles, etc.)
   - Sets `setEmptyMappings` flag appropriately
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

#### Exceptions

- **`CDPCLIError`** - Custom exception for CDP CLI command failures

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

    # Apply the validated mappings to the environment
    CLEAN_FILE="/tmp/validated_${ENV_NAME}_mappings.json"
    echo "Applying clean mappings to environment: $ENV_NAME"
    cdp environments set-id-broker-mappings \
      --cli-input-json "file://${CLEAN_FILE}"

    if [ $? -eq 0 ]; then
        echo "✓ IDBroker mappings successfully updated"
    else
        echo "✗ Failed to update IDBroker mappings"
        exit 1
    fi
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
