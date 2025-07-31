# DataHub Instance Group Metadata Validator

A Python script for validating and exporting DataHub cluster instance group metadata and volume information from CDP (Cloudera Data Platform) environments.

## Overview

This script retrieves detailed information about DataHub clusters, their instance groups, and associated volume metadata. It supports both AWS and other cloud platforms, providing comprehensive validation and export capabilities for cluster infrastructure analysis.

## Features

- **Multi-cluster processing**: Process all DataHub clusters in an environment or specific clusters
- **Cloud platform support**: Native AWS volume details with fallback for other platforms
- **Comprehensive output**: JSON and CSV exports with detailed volume information
- **Progress tracking**: Optional progress bars for large cluster processing
- **Debug logging**: Detailed logging for troubleshooting
- **Flexible output**: Configurable output directory with timestamped folders

## Prerequisites

### Required Tools

- **CDP CLI**: Must be installed and configured with appropriate profile
- **AWS CLI**: Required for AWS volume details (if processing AWS clusters)
- **Python 3.6+**: For script execution

### Python Dependencies

```bash
pip install tqdm
```

The `tqdm` package is optional but recommended for progress tracking. The script will work without it but won't show progress bars.

### CDP CLI Setup

#### Installation

**Linux (Recommended with Virtual Environment):**

To avoid conflicts with older versions of Python or other packages, Cloudera recommends installing the CDP CLI in a virtual environment:

```bash
# Create and activate virtual environment
mkdir ~/cdpclienv
virtualenv ~/cdpclienv
source ~/cdpclienv/bin/activate

# Install CDP CLI
~/cdpclienv/bin/pip install cdpcli

# Verify installation
cdp --version
```

**Upgrade CDP CLI:**

```bash
~/cdpclienv/bin/pip install --upgrade cdpcli
```

**Alternative Installation (without virtual environment):**

```bash
pip3 install cdpcli
```

#### Configuration

1. **Generate API Access Key:**

   - Log into the Cloudera Management Console
   - Navigate to User Management → Access Keys
   - Generate a new access key pair (Access Key ID and Private Key)

2. **Configure CDP CLI:**

   ```bash
   cdp configure
   ```

   Enter the following information when prompted:

   - **Cloudera Access key**: Copy and paste the access key ID from the Management Console
   - **Cloudera Private key**: Copy and paste the private key from the Management Console

3. **Verify Configuration:**

   ```bash
   cdp iam get-user
   ```

   This command should display your Cloudera client credentials.

4. **Configure Control Plane Region (Optional):**

   Edit the `~/.cdp/config` file and add:

   ```
   cdp_region = <CONTROL_PLANE_REGION>
   ```

   Example:

   ```
   cdp_region = eu-1
   ```

   **Region Priority Order:**

   1. `--cdp-region` argument from command line
   2. `cdp_region` from `~/.cdp/config` file
   3. Default: `us-west-1`

#### CLI Autocomplete (Optional)

Configure command completion for better usability:

1. **Locate the CLI completer:**

   ```bash
   which cdp_completer
   ```

2. **Add to your shell profile:**

   For bash, add to `~/.bash_profile`:

   ```bash
   complete -C /usr/local/bin/cdp_completer cdp
   ```

   Replace `/usr/local/bin/cdp_completer` with the actual location from step 1.

3. **Reload profile:**

   ```bash
   source ~/.bash_profile
   ```

4. **Test autocomplete:**
   ```bash
   cdp <TAB>
   ```

#### Beta CDP CLI (Optional)

If you need access to preview features, install the beta version:

```bash
# Install beta CLI (use separate virtual environment)
pip3 install cdpcli-beta

# Upgrade beta CLI
pip3 install cdpcli-beta --upgrade --user
```

**⚠️ Important:** Do not install both standard and beta CLIs in the same Python environment as they conflict. Use separate virtual environments or uninstall the standard CLI first.

## Usage

### Basic Usage

Process all DataHub clusters in an environment:

```bash
python datahub_instance_group_metadata_validator.py --environment-name "my-cdp-env"
```

Process specific clusters:

```bash
python datahub_instance_group_metadata_validator.py --cluster-name "cluster-1" --cluster-name "cluster-2"
```

### Command Line Options

| Option               | Description                                                     | Required | Default                    |
| -------------------- | --------------------------------------------------------------- | -------- | -------------------------- |
| `--environment-name` | CDP environment name to process all DataHub clusters            | No\*     | None                       |
| `--cluster-name`     | Specific DataHub cluster name (can be specified multiple times) | No\*     | None                       |
| `--profile`          | CDP CLI profile to use                                          | No       | "default"                  |
| `--output-folder`    | Output directory path                                           | No       | "/tmp/datahub_validations" |
| `--debug`            | Enable debug output                                             | No       | False                      |

\*Either `--environment-name` or at least one `--cluster-name` must be provided.

### Examples

#### Process all clusters in an environment with custom output location:

```bash
python datahub_instance_group_metadata_validator.py \
  --environment-name "production-env" \
  --output-folder "/home/user/cluster-exports" \
  --debug
```

#### Process specific clusters with custom profile:

```bash
python datahub_instance_group_metadata_validator.py \
  --cluster-name "datahub-cluster-1" \
  --cluster-name "datahub-cluster-2" \
  --profile "prod-profile"
```

## Output Structure

The script creates a timestamped output directory with the following structure:

```
output_folder-YYYYMMDD_HHMMSS/
├── cluster_name_1/
│   ├── describe-cluster.json          # Full cluster details
│   ├── instance_groups.json           # Instance group information
│   ├── instance_groups.csv            # Flattened instance group data
│   └── cluster_name_1_YYYYMMDD_HHMMSS_volumes.csv  # Detailed volume information
├── cluster_name_2/
│   ├── describe-cluster.json
│   ├── instance_groups.json
│   ├── instance_groups.csv
│   └── cluster_name_2_YYYYMMDD_HHMMSS_volumes.csv
└── ...
```

### Output Files Description

#### `describe-cluster.json`

Complete cluster information as returned by the CDP CLI `describe-cluster` command.

#### `instance_groups.json`

Structured instance group data including:

- Instance group names and types
- Instance details (ID, state, IP addresses, instance type)
- Attached volumes information

#### `instance_groups.csv`

Flattened CSV format of instance group data with columns:

- `hostgroup`: Instance group name
- `instance_group_type`: Type of instance group
- `group_state`: State of the instance group
- `instance_id`: EC2 instance ID
- `instance_state`: Instance state
- `private_ip`: Private IP address
- `public_ip`: Public IP address
- `instance_type`: EC2 instance type
- `attached_volume_X_field`: Volume fields (dynamically generated)

#### `*_volumes.csv`

Detailed volume information with columns:

- `hostgroup`: Instance group name
- `instance_id`: EC2 instance ID
- `instance_state`: Instance state
- `private_ip`: Private IP address
- `public_ip`: Public IP address
- `volume_id`: Volume ID
- `device_name`: Device name (e.g., /dev/sda1)
- `volume_size_gib`: Volume size in GiB
- `volume_state`: Volume state
- `attachment_status`: Volume attachment status
- `attachment_time`: Volume attachment timestamp
- `encrypted`: Whether volume is encrypted
- `kms_key_id`: KMS key ID (if encrypted)
- `delete_on_termination`: Whether volume is deleted on instance termination
- `is_root_disk`: Whether this is the root disk

## Cloud Platform Support

### AWS

- Full volume details including encryption, KMS keys, and attachment information
- Root device identification
- Volume state and attachment status

### Other Platforms

- Basic volume information from CDP cluster response
- Limited volume details compared to AWS

## Error Handling

The script includes comprehensive error handling:

- CDP profile validation
- Cluster access verification
- Graceful handling of missing volume information
- Detailed logging for troubleshooting

## Troubleshooting

### Common Issues

1. **CDP Profile Validation Failed**

   - Ensure CDP CLI is properly configured
   - Verify profile has necessary permissions
   - Check network connectivity to CDP control plane

2. **No Clusters Found**

   - Verify environment name is correct
   - Ensure environment contains DataHub clusters
   - Check profile permissions for the environment

3. **AWS Volume Details Missing**
   - Ensure AWS CLI is configured
   - Verify AWS credentials have EC2 permissions
   - Check if instances are in AWS (not other cloud platforms)

### Debug Mode

Enable debug output for detailed troubleshooting:

```bash
python datahub_instance_group_metadata_validator.py --environment-name "my-env" --debug
```

## Security Considerations

- The script requires CDP CLI access with appropriate permissions
- AWS volume details require EC2 read permissions
- Output files may contain sensitive information (IP addresses, instance IDs)
- Store output files securely and clean up when no longer needed
