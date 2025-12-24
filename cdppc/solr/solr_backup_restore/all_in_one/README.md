# Solr All-in-One Management Script

A comprehensive bash script for managing Solr collections with backup, delete, and restore operations using keytab-based Kerberos authentication and HDFS for backup storage.

## Overview

This all-in-one script provides a unified interface for managing Solr collections with four main operations:

- **Backup**: Backs up Solr collections to HDFS using keytab-based authentication
- **Delete**: Deletes Solr collections with safety checks and confirmations
- **Restore**: Restores Solr collections from HDFS backup locations using solrctl
- **List**: Lists all available Solr collections

## Features

- ✅ **Keytab-Based Authentication**: Uses Kerberos keytabs (no password required)
- ✅ **HDFS Integration**: All backups stored in HDFS with automatic timestamp organization
- ✅ **Four Operations**: Backup, delete, restore, and list in one script
- ✅ **Configuration Backup**: Save collection configurations and metadata for recovery (`--save-configs`)
- ✅ **Empty Collection Creation**: Create empty collections with saved configurations (`--create-empty`)
- ✅ **solrctl Integration**: Uses solrctl for restore operations with progress monitoring
- ✅ **Safety Features**: Dry-run mode, confirmation prompts, comprehensive error handling
- ✅ **Comprehensive Logging**: Color-coded output with optional file logging
- ✅ **Selective Operations**: Operate on specific collections or all collections
- ✅ **Automatic Validation**: Validates Solr service is running before operations
- ✅ **Flexible Backup Names**: Support for custom backup name patterns
- ✅ **Verbose Mode**: Detailed output for debugging
- ✅ **Debug Mode**: Enhanced debugging with curl verbose output (`--debug`)

## Prerequisites

- **Bash**: Version 4.0 or higher
- **curl**: For making HTTP requests to Solr API
- **jq**: For JSON parsing (required)
- **solrctl**: Solr command-line tool (for restore operations)
- **HDFS Client**: HDFS command-line tools installed and configured
- **Kerberos**: Keytab files available in `/var/run/cloudera-scm-agent/process/`
- **Solr Service**: Script must be run on a node where Solr is running
- **Network Access**: Access to Solr endpoint and HDFS
- **Permissions**: Appropriate Kerberos and HDFS permissions

## Installation

1. **Download the script**:

   ```bash
   cd /path/to/solr/solr_backup_restore/all_in_one
   ```

2. **Make it executable**:

   ```bash
   chmod +x solr_all_in_one.sh
   ```

3. **Verify prerequisites**:

   ```bash
   # Check curl
   curl --version

   # Check jq
   jq --version

   # Check HDFS
   hdfs version

   # Check kinit
   kinit -V
   ```

## Usage

### Basic Syntax

```bash
./solr_all_in_one.sh <command> [OPTIONS]
```

### Commands

- `backup`: Backup Solr collections to HDFS
- `delete`: Delete Solr collections
- `restore`: Restore Solr collections from HDFS backup using solrctl
- `list`: List all available Solr collections

### Common Options (All Commands)

| Option    | Long Form         | Description                                      |
| --------- | ----------------- | ------------------------------------------------ |
| `-h`      | `--help`          | Show help message and exit                       |
| `-d`      | `--dry-run`       | Preview operations without executing             |
| `-f`      | `--force`         | Skip confirmation prompts (use with caution)     |
| `-c NAME` | `--collection`    | Operate on specific collection (multiple times)  |
| `-v`      | `--verbose`       | Enable verbose output                            |
| `--debug` |                   | Enable debug mode (curl --verbose for API calls) |
| `-l FILE` | `--log`           | Write log to specified file                      |
|           | `--host HOSTNAME` | Specify Solr hostname (auto-detected)            |

### Backup Options

| Option       | Long Form       | Description                                         |
| ------------ | --------------- | --------------------------------------------------- |
| `-b PATH`    | `--backup-base` | HDFS base path (default: /user/solr/backup)         |
| `-t`         | `--timestamp`   | Add timestamp subdirectory (default: enabled)       |
| `-n PATTERN` | `--name`        | Backup name pattern (default: {collection}\_backup) |

### Delete Options

| Option    | Long Form      | Description                                      |
| --------- | -------------- | ------------------------------------------------ |
| `-c NAME` | `--collection` | Delete specific collection(s) (from common opts) |
| (none)    |                | Delete all collections (default if no -c)        |

**Note**: The `-c` option from common options allows selective deletion. Without `-c`, all collections will be deleted.

### Restore Options

| Option       | Long Form           | Description                                                   |
| ------------ | ------------------- | ------------------------------------------------------------- |
| `-a`         | `--all`             | Restore all collections from backup                           |
| `-b PATH`    | `--backup-location` | HDFS path to backup location (required)                       |
| `-n PATTERN` | `--name`            | Backup name pattern (default: {collection}\_backup)           |
|              | `--create-empty`    | Create empty collections with saved configs (no data restore) |

## Examples

### Backup Operations

#### Example 1: Backup All Collections

```bash
./solr_all_in_one.sh backup
```

This will:

1. Validate Solr is running
2. Authenticate using Solr keytab
3. List all collections
4. Create timestamped HDFS backup directory
5. Backup all collections
6. Verify backup location

#### Example 2: Backup Specific Collections

```bash
./solr_all_in_one.sh backup -c vertex_index -c edge_index
```

Only the specified collections will be backed up.

#### Example 3: Backup with Custom Base Path

```bash
./solr_all_in_one.sh backup -b /solr/backups
```

Backups will be stored in `/solr/backups/TIMESTAMP/`.

#### Example 4: Dry Run Backup

```bash
./solr_all_in_one.sh backup -d
```

Preview what would be backed up without actually backing up.

#### Example 5: Backup with Custom Name Pattern

```bash
./solr_all_in_one.sh backup -n '{collection}_backup_20231223'
```

Uses custom backup name pattern.

#### Example 6: Backup with Configuration Saving

```bash
./solr_all_in_one.sh backup --save-configs
```

Saves collection configurations and metadata for recovery. This allows you to recreate collections with the same settings (shards, replication factor, configs) even without data.

### Delete Operations

#### Example 1: Delete All Collections

```bash
./solr_all_in_one.sh delete
```

⚠️ **Warning**: This will delete ALL collections. Use with caution.

**Note**: The script will prompt for confirmation before deleting. Use `-f` to skip confirmation.

#### Example 2: Delete Specific Collections

```bash
./solr_all_in_one.sh delete -c collection1 -c collection2
```

Only the specified collections will be deleted. You can specify multiple collections using multiple `-c` options.

#### Example 3: Delete Single Collection

```bash
./solr_all_in_one.sh delete -c vertex_index
```

Deletes only the `vertex_index` collection.

#### Example 4: Dry Run Delete

```bash
./solr_all_in_one.sh delete -d
```

Preview what would be deleted without actually deleting.

#### Example 5: Dry Run Delete for Specific Collections

```bash
./solr_all_in_one.sh delete -d -c collection1 -c collection2
```

Preview what would be deleted for specific collections.

#### Example 6: Force Delete (Skip Confirmation)

```bash
./solr_all_in_one.sh delete -f -c old_collection
```

⚠️ **Warning**: This skips the confirmation prompt. Use with extreme caution.

### Restore Operations

#### Example 1: Restore All Collections from Backup

```bash
./solr_all_in_one.sh restore -a -b /user/solr/backup/20231223_153000
```

Restores all collections found in the specified backup location.

#### Example 2: Restore Specific Collections

```bash
./solr_all_in_one.sh restore -c vertex_index -c edge_index \
  -b /user/solr/backup/20231223_153000
```

Restores only the specified collections.

#### Example 3: Dry Run Restore

```bash
./solr_all_in_one.sh restore -a -d -b /user/solr/backup/20231223_153000
```

Preview what would be restored.

#### Example 4: Restore with Custom Backup Name Pattern

```bash
./solr_all_in_one.sh restore -c vertex_index \
  -b /user/solr/backup/20231223_153000 \
  -n 'vertex_index_backup_20231223'
```

Uses custom backup name pattern.

#### Example 5: Create Empty Collections from Saved Configs

```bash
./solr_all_in_one.sh restore --create-empty -b /user/solr/backup/20231223_153000
```

Creates empty collections using saved configurations and metadata. This is useful for recreating collection structure without restoring data.

#### Example 6: List Collections

```bash
./solr_all_in_one.sh list
```

Lists all available Solr collections.

### Advanced Examples

#### Example 1: Complete Backup and Restore Workflow

```bash
#!/bin/bash

# Step 1: Backup all collections
echo "Creating backup..."
./solr_all_in_one.sh backup -v -l /tmp/backup.log

# Step 2: Find latest backup (from log or HDFS)
BACKUP_LOCATION="/user/solr/backup/$(date +%Y%m%d%H%M%S)"

# Step 3: Restore from backup
echo "Restoring from backup..."
./solr_all_in_one.sh restore -a -b "$BACKUP_LOCATION" -v -l /tmp/restore.log
```

#### Example 2: Scheduled Backup with Logging

```bash
#!/bin/bash
# Cron job for daily backups

LOG_DIR="/var/log/solr_backup"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/solr_backup_${TIMESTAMP}.log"

./solr_all_in_one.sh backup \
  -v \
  -f \
  -l "$LOG_FILE"

if [ $? -eq 0 ]; then
  echo "✓ Backup completed successfully"
else
  echo "✗ Backup failed - check log: $LOG_FILE"
  exit 1
fi
```

#### Example 3: Selective Backup and Delete

```bash
#!/bin/bash

COLLECTIONS=("old_collection1" "old_collection2")

# Backup before deletion
echo "Backing up collections before deletion..."
./solr_all_in_one.sh backup -c "${COLLECTIONS[@]}" -v

# Delete after backup
echo "Deleting collections..."
./solr_all_in_one.sh delete -c "${COLLECTIONS[@]}" -v
```

## Output

### Console Output

The script provides color-coded output:

- 🔵 **Blue**: Informational messages
- 🟢 **Green**: Success messages
- 🟡 **Yellow**: Warnings
- 🔴 **Red**: Errors
- 🔷 **Cyan**: Verbose/debug messages

### Example Output (Backup)

```
╔══════════════════════════════════════════════════════════════╗
║      Solr All-in-One Management Script v2.0      ║
╚══════════════════════════════════════════════════════════════╝

[2023-12-23 15:30:00] INFO: Starting backup operation...
[2023-12-23 15:30:00] INFO: Validating that Solr is running on this node...
[2023-12-23 15:30:00] SUCCESS: Solr service detected: /var/run/cloudera-scm-agent/process/123-solr-SOLR_SERVER
[2023-12-23 15:30:00] INFO: Authenticating as solr/solr.example.com@EXAMPLE.COM
[2023-12-23 15:30:00] SUCCESS: Authentication successful
[2023-12-23 15:30:01] INFO: Fetching collection list from https://solr.example.com:8985
[2023-12-23 15:30:01] INFO: Found 4 collection(s) to backup
[2023-12-23 15:30:01] INFO: Preparing HDFS backup location: /user/solr/backup/20231223153001
[2023-12-23 15:30:01] SUCCESS: HDFS backup location prepared

WARNING: This will backup 4 collection(s)
  Backup location: /user/solr/backup/20231223153001
  Solr endpoint: https://solr.example.com:8985

ALL collections will be processed

Are you sure you want to continue? (yes/no): yes

[2023-12-23 15:30:05] INFO: Starting backup process...

[2023-12-23 15:30:05] INFO: Processing collection: vertex_index
[2023-12-23 15:30:06] SUCCESS: Collection 'vertex_index' backup initiated successfully (HTTP 200)

[2023-12-23 15:30:06] INFO: Processing collection: edge_index
[2023-12-23 15:30:07] SUCCESS: Collection 'edge_index' backup initiated successfully (HTTP 200)

[2023-12-23 15:30:07] INFO: Processing collection: fulltext_index
[2023-12-23 15:30:08] SUCCESS: Collection 'fulltext_index' backup initiated successfully (HTTP 200)

[2023-12-23 15:30:08] INFO: Processing collection: ranger_audits
[2023-12-23 15:30:09] SUCCESS: Collection 'ranger_audits' backup initiated successfully (HTTP 200)

[2023-12-23 15:30:09] INFO: Verifying HDFS backup location: /user/solr/backup/20231223153001
[2023-12-23 15:30:10] SUCCESS: HDFS backup location exists and is accessible

═══════════════════════════════════════════════════════════════
OPERATION SUMMARY: BACKUP
═══════════════════════════════════════════════════════════════
Collections found:    4
Collections processed: 4
Collections failed:  0
Backup location:      /user/solr/backup/20231223153001
═══════════════════════════════════════════════════════════════
```

## Authentication

The script uses **keytab-based Kerberos authentication**, which means:

- **No passwords required**: Authentication is handled automatically via keytabs
- **Secure**: Uses Kerberos tickets for authentication
- **Automatic**: Keytabs are discovered from Cloudera Manager process directories
- **Service-specific**: Uses appropriate keytabs for HDFS and Solr operations

### Keytab Discovery

The script automatically discovers keytabs from:

- **HDFS**: `/var/run/cloudera-scm-agent/process/*hdfs-DATANODE/hdfs.keytab`
- **Solr**: `/var/run/cloudera-scm-agent/process/*solr-SOLR_SERVER/solr.keytab`

### Authentication Flow

1. **Backup Operation**:

   - Authenticate with HDFS keytab (for HDFS operations)
   - Authenticate with Solr keytab (for Solr API calls)

2. **Delete Operation**:

   - Authenticate with Solr keytab (for Solr API calls)

3. **Restore Operation**:

   - Authenticate with HDFS keytab (to verify backup location)
   - Authenticate with Solr keytab (for solrctl restore operations)
   - Monitor restore progress using solrctl collection --request-status

4. **List Operation**:
   - Authenticate with Solr keytab (for Solr API calls)

## HDFS Backup Structure

### Default Structure

```
/user/solr/backup/
├── 20231223153001/
│   ├── vertex_index_backup/
│   ├── edge_index_backup/
│   ├── fulltext_index_backup/
│   ├── ranger_audits_backup/
│   └── configs/
│       ├── atlas_configs_config/
│       ├── ranger_audits_config/
│       ├── vertex_index_metadata.json
│       ├── vertex_index_recreate.sh
│       └── cluster-state.json
├── 20231223160000/
│   └── ...
└── ...
```

### With --save-configs Option

When using `--save-configs`, the backup includes:

- **configs/**: Directory containing collection configurations
  - `{config_name}_config/`: Configuration files for each unique config
  - `{collection}_metadata.json`: Collection metadata from cluster state
  - `{collection}_recreate.sh`: Script to recreate the collection
  - `cluster-state.json`: Full cluster state snapshot

#### Example: Create All Empty Collections from Saved Configs

You can use the saved recreation scripts to create all empty collections at once:

```bash
# Create all empty collections from recreation scripts
BACKUP_LOCATION="/user/solr/backup/20251224003042"
for script in $(hdfs dfs -ls "${BACKUP_LOCATION}/configs/" | awk '/\.sh$/ {print $NF}'); do
    echo "Executing: $script"
    hdfs dfs -cat "$script" | bash
done
```

Or as a one-liner:

```bash
for i in $(hdfs dfs -ls /user/solr/backup/20251224003042/configs/ | awk '/\.sh$/ {print $NF}'); do
    echo "Creating collection from: $i"
    hdfs dfs -cat "$i" | bash
done
```

This will:

1. Find all `.sh` recreation scripts in the configs directory
2. Download and execute each script to create empty collections
3. Each collection will be created with the exact settings from the backup (shards, replication factor, configs, etc.)

### Custom Base Path

If using `-b /solr/backups`:

```
/solr/backups/
├── 20231223153001/
│   └── ...
└── ...
```

## Error Handling

The script includes comprehensive error handling:

### Authentication Errors

```
[2023-12-23 15:30:00] ERROR: No process directory found for solr-SOLR_SERVER
```

**Solutions**:

- Verify Solr service is running on the node
- Check Cloudera Manager process directories exist
- Ensure script is run on a Solr node

### HDFS Access Errors

```
[2023-12-23 15:30:00] ERROR: HDFS backup location does not exist or is not accessible
```

**Solutions**:

- Verify HDFS service is running
- Check HDFS permissions
- Verify keytab has appropriate permissions
- Test HDFS access manually: `hdfs dfs -ls /user/solr/backup`

### Solr API Errors

```
[2023-12-23 15:30:00] ERROR: Failed to connect to Solr endpoint
```

**Solutions**:

- Verify Solr service is running
- Check network connectivity
- Verify endpoint URL is correct
- Check Kerberos authentication

### Collection Not Found

```
[2023-12-23 15:30:00] WARNING: Collection 'collection_name' not found, skipping
```

**Solutions**:

- Verify collection name is correct
- List collections to see available names
- Check collection exists in Solr

## Exit Codes

- `0`: Success - All operations completed successfully
- `1`: Error - One or more operations failed

## Troubleshooting

### Issue: "No process directory found for solr-SOLR_SERVER"

**Solution**: Ensure script is run on a node where Solr is running:

```bash
# Check if Solr is running
ps aux | grep solr

# Check process directories
ls -la /var/run/cloudera-scm-agent/process/ | grep solr
```

### Issue: "Missing required tools: jq"

**Solution**: Install jq:

```bash
# On RHEL/CentOS
sudo yum install jq

# On Ubuntu/Debian
sudo apt-get install jq

# On macOS
brew install jq
```

### Issue: "Failed to authenticate with keytab"

**Solution**: Verify keytab exists and is readable:

```bash
# Check keytab exists
ls -la /var/run/cloudera-scm-agent/process/*solr-SOLR_SERVER/solr.keytab

# Test keytab manually
kinit -kt /path/to/solr.keytab $(klist -kt /path/to/solr.keytab | tail -1 | awk '{print $4}')
```

### Issue: "HDFS backup location does not exist"

**Solution**: Verify HDFS access and permissions:

```bash
# Test HDFS access
hdfs dfs -ls /user/solr/backup

# Create directory manually if needed
hdfs dfs -mkdir -p /user/solr/backup
hdfs dfs -chown solr:solr /user/solr/backup
```

### Issue: "No collections found"

**Solution**: Verify Solr endpoint and collections exist:

```bash
# Test Solr endpoint
curl --negotiate -u : "https://$(hostname -f):8985/solr/admin/collections?action=LIST&wt=json" | jq '.collections'
```

## Best Practices

1. **Always Use Dry-Run First**

   ```bash
   ./solr_all_in_one.sh backup -d
   ```

2. **Enable Logging for Audit Trail**

   ```bash
   ./solr_all_in_one.sh backup -l /var/log/solr_backup.log
   ```

3. **Backup Before Delete**

   ```bash
   # Always backup before deleting
   ./solr_all_in_one.sh backup -c collection_to_delete
   ./solr_all_in_one.sh delete -c collection_to_delete
   ```

4. **Use Timestamped Backups**

   Timestamps are enabled by default, ensuring backups don't overwrite each other.

5. **Verify Backups After Creation**

   ```bash
   # After backup, verify HDFS location
   hdfs dfs -ls /user/solr/backup/
   ```

6. **Test Restore Capability**

   Periodically test restore operations to ensure backups are valid.

7. **Use Verbose Mode for Troubleshooting**

   ```bash
   ./solr_all_in_one.sh backup -v
   ```

## Workflow Examples

### Complete Backup and Restore Cycle

```bash
#!/bin/bash

# Step 1: Backup all collections
echo "Step 1: Creating backup..."
./solr_all_in_one.sh backup -v -l /tmp/backup.log

# Step 2: Get latest backup location (from HDFS)
LATEST_BACKUP=$(hdfs dfs -ls /user/solr/backup | tail -1 | awk '{print $NF}')
echo "Latest backup: $LATEST_BACKUP"

# Step 3: Test restore (dry-run)
echo "Step 2: Testing restore..."
./solr_all_in_one.sh restore -a -d -b "$LATEST_BACKUP" -v

# Step 4: Actual restore (if needed)
# ./solr_all_in_one.sh restore -a -b "$LATEST_BACKUP" -v -l /tmp/restore.log
```

### Scheduled Backups

```bash
#!/bin/bash
# Cron: 0 2 * * * /path/to/backup_script.sh

LOG_DIR="/var/log/solr_backup"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/backup_${TIMESTAMP}.log"

./solr_all_in_one.sh backup \
  -f \
  -v \
  -l "$LOG_FILE"

# Cleanup old backups (keep last 7 days)
hdfs dfs -ls /user/solr/backup | \
  awk '{print $NF}' | \
  while read dir; do
    dir_date=$(basename "$dir" | cut -d'_' -f1)
    if [[ $(date -d "$dir_date" +%s) -lt $(date -d "7 days ago" +%s) ]]; then
      hdfs dfs -rm -r "$dir"
    fi
  done
```

## Security Considerations

1. **Keytab Permissions**: Ensure keytabs have appropriate permissions (typically 400)
2. **HDFS Permissions**: Verify HDFS backup locations have correct ownership
3. **Log Files**: Secure log files containing operation details
4. **Dry-Run First**: Always test with dry-run before actual operations
5. **Backup Verification**: Regularly verify backup integrity

## Restore Operation Details

### Using solrctl

The restore operation uses `solrctl collection --restore` which provides:

- **Asynchronous Operations**: Restore requests are submitted and monitored
- **Progress Tracking**: Real-time status checking using `solrctl collection --request-status`
- **Request IDs**: Each restore gets a unique request ID for tracking
- **Final Verification**: Comprehensive status check at completion

### Restore Monitoring

The script automatically monitors restore progress:

1. Submits restore request for each collection
2. Polls restore status every 10 seconds
3. Displays progress for each collection
4. Provides final verification summary

### Restore Status States

- **completed**: Restore finished successfully
- **failed**: Restore encountered an error
- **running**: Restore still in progress

## Limitations

- Must be run on a node where Solr is running
- Requires keytab files in Cloudera Manager process directories
- HDFS must be accessible and properly configured
- Collections are processed sequentially (not in parallel)
- No automatic retry for failed operations
- Restore operations are asynchronous - script monitors until completion
- solrctl must be available in PATH or standard locations
