# Hue Database Cleanup Validation Script

## Overview

The `validate_hue_cleanup.py` script validates the Hue database to determine if cleanup is needed. This script performs **read-only operations** and does NOT modify any data. It generates a comprehensive report with recommendations.

## Features

- ✅ **Read-only validation** - No data modification
- ✅ **Automatic pod discovery** - Finds Hue backend pods automatically
- ✅ **Comprehensive reporting** - Detailed markdown report with recommendations
- ✅ **Portable** - Works with any kubeconfig and namespace
- ✅ **Informative logging** - Clear INFO messages during execution
- ✅ **Error handling** - Graceful error handling with helpful messages

## Prerequisites

- Python 3.6 or higher
- `kubectl` installed and in PATH
- Access to Kubernetes cluster
- Read access to Hue backend pods
- Database connectivity from pods

## Installation

No installation required. The script is standalone and only requires Python standard library.

```bash
# Make script executable (optional)
chmod +x validate_hue_cleanup.py
```

## Usage

### Basic Usage

```bash
python3 validate_hue_cleanup.py \
  --kubeconfig ~/k8s/config.yml \
  --namespace impala-1764198109-s6vr
```

### With Custom Output File

```bash
python3 validate_hue_cleanup.py \
  --kubeconfig ~/k8s/config.yml \
  --namespace impala-1764198109-s6vr \
  --output my_validation_report.md
```

### Using Environment Variable

```bash
export KUBECONFIG=~/k8s/config.yml
python3 validate_hue_cleanup.py --namespace impala-1764198109-s6vr
```

### Specify Pod Manually

```bash
python3 validate_hue_cleanup.py \
  --kubeconfig ~/k8s/config.yml \
  --namespace impala-1764198109-s6vr \
  --pod huebackend-0
```

## Command Line Options

| Option         | Required | Description                                         |
| -------------- | -------- | --------------------------------------------------- |
| `--kubeconfig` | No\*     | Path to kubeconfig file (or set KUBECONFIG env var) |
| `--namespace`  | Yes      | Kubernetes namespace where Hue backend pods run     |
| `--output`     | No       | Output file for report (default: auto-generated)    |
| `--pod`        | No       | Specific pod name (auto-discovered if not provided) |
| `--help`       | No       | Show help message                                   |

\*Required if KUBECONFIG environment variable is not set

## What the Script Does

1. **Discovers Hue Backend Pods**: Automatically finds running Hue backend pods
2. **Retrieves Database Configuration**: Reads database settings from pod
3. **Queries Table Counts**: Gets row counts for target cleanup tables:
   - `desktop_document`
   - `desktop_document2`
   - `beeswax_session`
   - `beeswax_savedquery`
   - `beeswax_queryhistory`
4. **Queries Table Sizes**: Gets disk usage for each table
5. **Checks Database Size**: Gets total database size
6. **Validates Cleanup Command**: Verifies cleanup command availability
7. **Generates Report**: Creates comprehensive markdown report

## Output

The script generates a detailed markdown report that includes:

- **Executive Summary**: Current status and key findings
- **Database State**: Current row counts and table sizes
- **Cleanup Recommendations**: Whether cleanup is needed
- **Cleanup Process**: Step-by-step instructions (when needed)
- **Monitoring Recommendations**: How to monitor going forward
- **Troubleshooting Guide**: Common issues and solutions

### Report Location

- If `--output` is specified: Uses that file
- Otherwise: Auto-generates filename like `hue_cleanup_validation_<namespace>_<timestamp>.md`

## Example Output

```
[INFO] Using kubeconfig: /Users/user/k8s/config.yml
[INFO] Target namespace: impala-1764198109-s6vr
[INFO] Discovering Hue backend pods...
[SUCCESS] Found 2 Hue backend pod(s): huebackend-0, huebackend-1
[INFO] Retrieving database configuration from pod huebackend-0...
[SUCCESS] Database configuration retrieved
[INFO] Retrieving database password...
[SUCCESS] Database password retrieved
[INFO] Querying table row counts...
[INFO]   desktop_document: 0 rows
[INFO]   desktop_document2: 0 rows
[INFO]   beeswax_session: 0 rows
[INFO]   beeswax_savedquery: 0 rows
[INFO]   beeswax_queryhistory: 0 rows
[INFO] Querying table sizes...
[INFO] Querying database size...
[INFO] Checking if cleanup command is available...
[SUCCESS] Cleanup command is available
[INFO] Generating validation report...
[SUCCESS] Report written to: hue_cleanup_validation_impala-1764198109-s6vr_20251127_192530.md

======================================================================
[SUCCESS] Database is empty - no cleanup needed
======================================================================

[INFO] Validation complete. See report for detailed information.
```

## Cleanup Threshold

The script uses the following thresholds:

- **Optimal**: Less than 30,000 rows per table
- **Warning**: 20,000-30,000 rows (plan cleanup)
- **Critical**: Over 30,000 rows (cleanup recommended)

## What Gets Cleaned (When Cleanup is Run)

⚠️ **Important**: The cleanup process only removes **UNSAVED documents**:

- Temporary/autosave documents
- Old query sessions
- Stale query history

✅ **What is Preserved**:

- Saved queries
- User preferences
- User settings
- Explicitly saved documents

## Troubleshooting

### Error: kubectl not found

**Solution**: Ensure kubectl is installed and in your PATH

### Error: No Hue backend pods found

**Solution**:

- Verify namespace is correct
- Check if pods are running: `kubectl get pods -n <namespace>`
- Use `--pod` option to specify pod manually

### Error: Could not retrieve database password

**Solution**:

- Verify pod has `/etc/hue/conf/altscript.sh` script
- Check pod permissions
- Verify database configuration

### Error: Query failed

**Solution**:

- Verify database connectivity from pod
- Check database service is accessible
- Verify database credentials

### Warning: Cleanup command not found

**Solution**:

- Verify Hue installation in pod
- Check path: `/opt/hive/build/env/bin/hue`
- May indicate incomplete Hue installation

## Best Practices

1. **Run Regularly**: Schedule monthly or quarterly validation
2. **Monitor Trends**: Track table growth over time
3. **Plan Ahead**: Cleanup before reaching 30,000 rows
4. **Backup First**: Always backup before cleanup (when needed)
5. **Test in Non-Prod**: Test cleanup process in non-production first

## Scheduling Regular Validation

### Using Cron

```bash
# Add to crontab (runs monthly on 1st at 2 AM)
0 2 1 * * /usr/bin/python3 /path/to/validate_hue_cleanup.py \
  --kubeconfig ~/k8s/config.yml \
  --namespace my-namespace \
  --output /path/to/reports/validation_$(date +\%Y\%m).md
```

## Integration with Cleanup Process

This validation script is designed to be run **before** performing cleanup:

1. **Run Validation**: `validate_hue_cleanup.py` (this script)
2. **Review Report**: Check recommendations
3. **Backup Database**: Create backup if cleanup needed
4. **Run Cleanup**: Follow steps in report (manual process)
5. **Re-run Validation**: Verify cleanup results

## Security Considerations

- Script only performs **read-only** operations
- Database password is retrieved from pod (not stored)
- No credentials are logged or saved
- All operations are auditable via kubectl

## Support

For issues or questions:

1. Check the troubleshooting section
2. Review the generated report for details
3. Verify kubectl and database connectivity
4. Check pod logs for additional information

## License

This script is provided as-is for validation purposes only.

## Version

Current version: 1.0.0

---

**Remember**: This script only **validates** and **reports**. It does NOT perform any cleanup operations.
