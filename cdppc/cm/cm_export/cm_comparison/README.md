# Configuration Comparison Tool

This Python script compares two Cloudera Manager configuration directories and generates a CSV report showing the differences that need to be applied to make the second configuration match the first.

## 🎯 Purpose

The tool helps identify configuration drift between environments and provides the exact PUT commands needed to synchronize configurations. It's particularly useful for:

- **Environment synchronization**: Making test/staging environments match production
- **Configuration drift detection**: Identifying unauthorized changes
- **Migration planning**: Planning configuration updates during upgrades

## 🚀 Features

- **Smart property filtering**: Ignores properties that are expected to change (SSL, passwords, timestamps, etc.)
- **Automatic PUT command generation**: Creates ready-to-use curl commands for each difference
- **Comprehensive comparison**: Handles both Cluster Services and MGMT Services
- **CSV output**: Generates detailed reports for analysis and execution
- **Flexible matching**: Works with the organized directory structure from the main export script
- **Named arguments**: Clean command-line interface with `--source`, `--target`, and `--output-dir` options
- **Automatic timestamping**: Creates organized output directories with timestamps
- **Standardized CSV naming**: Consistent filename format `cluster_config_differences-YYYYMMDD_HHMMSS.csv`
- **Clean output**: Reduced verbosity with summary statistics instead of individual file messages

## 📋 Prerequisites

- Python 3.6 or higher
- Access to two configuration directories to compare
- The directories should contain JSON files from the `cm_export_all_service_configs.sh` script

## 🛠️ Installation

1. Ensure the script is executable:

   ```bash
   chmod +x compare_configs.py
   ```

2. The script uses only Python standard library modules, so no additional packages are required.

## 📖 Usage

### Command-Line Interface

The tool uses a modern command-line interface with named arguments for clarity and ease of use:

```bash
python3 compare_configs.py --source <source_config_dir> --target <target_config_dir> --output-dir <output_dir>
```

### Short Form Usage

For convenience, short form arguments are also supported:

```bash
python3 compare_configs.py -s <source_config_dir> -t <target_config_dir> -o <output_dir>
```

### Examples

```bash
# Compare two configuration exports
python3 compare_configs.py --source /tmp/prod_configs --target /tmp/staging_configs --output-dir /tmp/comparison_results

# Using short form arguments
python3 compare_configs.py -s /tmp/prod_configs -t /tmp/staging_configs -o /tmp/comparison_results

# Compare configurations from different time periods
python3 compare_configs.py --source /tmp/old_export --target /tmp/new_export --output-dir /tmp/config_changes
```

### Required Arguments

- `--source` / `-s`: Source configuration directory (baseline configuration)
- `--target` / `-t`: Target configuration directory (to be updated)
- `--output-dir` / `-o`: Output directory for comparison results (will be created with timestamp)

### Help and Usage Information

To see the full help information:

```bash
python3 compare_configs.py --help
```

## 🔍 How It Works

### 1. Directory Structure Analysis

The script expects directories with the structure created by `cm_export_all_service_configs.sh`:

```
ServiceConfigs/
├── ClusterServices/          # Cluster service configs
└── MGMT_Services/           # MGMT service configs

roleConfigGroups/
├── ClusterServices/          # Cluster role config groups
└── MGMT_Services/           # MGMT role config groups
```

### 2. Property Filtering

The script automatically ignores properties that are expected to change:

**Exact matches:**

- `ssl_enabled`
- `keystore`
- `truststore`
- `password`
- `canary`

**Pattern matches (case-insensitive):**

- Any property containing `ssl`, `keystore`, `truststore`, `password`, `canary`
- Properties with `{{CM_AUTO_TLS}}` (auto-generated values)
- Properties with `timestamp`, `date`, `host`, `fqdn`

### 3. Difference Detection

For each configuration file, the script identifies:

- **Missing properties**: Properties present in source but not in target
- **Value differences**: Properties with different values between source and target

### 4. PUT Command Generation

Based on the file location and type, the script generates appropriate PUT commands:

- **Cluster Services**: `/api/{api_version}}/clusters/{cluster}/services/{service}/config`
- **Cluster Roles**: `/api/{api_version}}/clusters/{cluster}/services/{service}/roleConfigGroups/{role}/config`
- **MGMT Services**: `/api/{api_version}}/cm/service/config`
- **MGMT Roles**: `/api/{api_version}}/cm/service/roleConfigGroups/{group}/config`

### 5. Output Directory Management

The script automatically creates timestamped output directories:

- **Base Directory**: The directory you specify as `<output_dir>`
- **Timestamp Suffix**: Automatically adds `_YYYYMMDD_HHMMSS` format
- **Example**: `/tmp/comparison_results` becomes `/tmp/comparison_results_20241201_143022`
- **Organization**: Each comparison run gets its own timestamped directory
- **CSV Location**: The CSV file is placed inside the timestamped directory

## 📊 Output Format

The CSV report contains the following columns:

| Column          | Description                                        |
| --------------- | -------------------------------------------------- |
| `filename`      | Name of the configuration file                     |
| `property_name` | Name of the configuration property                 |
| `source_value`  | Value from the source (baseline) configuration     |
| `target_value`  | Value from the target configuration (or "MISSING") |
| `action`        | Required action: "ADD" or "UPDATE"                 |
| `put_command`   | Complete curl command to apply the change          |
| `source_file`   | Full path to the source file                       |
| `target_file`   | Full path to the target file                       |

## 🔧 Customization

### Adding More Ignored Properties

Edit the `IGNORED_PROPERTIES` set in the script:

```python
IGNORED_PROPERTIES = {
    'ssl_enabled',
    'keystore',
    'truststore',
    'password',
    'canary',
    'your_custom_property'  # Add new properties here
}
```

### Adding More Ignored Patterns

Edit the `IGNORED_PATTERNS` list in the script:

```python
IGNORED_PATTERNS = [
    r'.*ssl.*',
    r'.*keystore.*',
    # ... existing patterns ...
    r'.*your_pattern.*'  # Add new patterns here
]
```

## 📝 Example Output

```
Comparing configurations:
  Source (baseline): /tmp/prod_configs
  Target (to update): /tmp/staging_configs
  Output directory: /tmp/comparison_results_20241201_143022
  CSV file: cluster_config_differences-20241201_143022.csv

Found 15 config files in source directory
Found 15 config files in target directory
Processed 12 files with configurations
Skipped 3 empty configuration files
Skipped 0 files not found in target directory

CSV report generated: /tmp/comparison_results_20241201_143022/cluster_config_differences-20241201_143022.csv
Total differences found: 8

Summary by action type:
  ADD: 3 properties
  UPDATE: 5 properties

Comparison completed successfully!
Results saved to: /tmp/comparison_results_20241201_143022
```

## ⚠️ Important Notes

1. **Source as Baseline**: The source directory is treated as the "correct" configuration that the target should match.

2. **Required Arguments**: All three arguments (`--source`, `--target`, `--output-dir`) are required and must be specified.

3. **Output Directory**: The output directory will automatically have a timestamp suffix added (e.g., `/tmp/results` becomes `/tmp/results_20241201_143022`).

4. **CSV Filename**: The CSV file is automatically named `cluster_config_differences-YYYYMMDD_HHMMSS.csv` and placed in the timestamped output directory.

5. **PUT Commands**: Generated commands use placeholder variables (`${WORKLOAD_USER}`, `${CM_SERVER}`, etc.) that need to be set in your environment.

6. **Property Values**: Multi-line properties and special characters are properly handled in the generated PUT commands.

7. **File Matching**: Files are matched by their base name (without extension), so ensure consistent naming between directories.

8. **Verbose Output**: The tool provides clean, concise output with summary statistics instead of verbose individual file messages.

## 🚨 Troubleshooting

### Common Issues

1. **"No differences found"**: This usually means configurations are identical or all differences are in ignored properties.

2. **"Could not parse file"**: Check that JSON files are valid and accessible.

3. **Missing files**: Ensure both directories contain the same set of configuration files.

### Debug Mode

For troubleshooting, you can modify the script to print more detailed information by adding debug prints in the comparison methods.

## 🔗 Integration

This tool works seamlessly with the output from `cm_export_all_service_configs.sh` and can be used in:

- **CI/CD pipelines**: Automated configuration validation
- **Change management**: Pre/post change validation
- **Disaster recovery**: Configuration restoration procedures
- **Compliance monitoring**: Regular configuration audits
