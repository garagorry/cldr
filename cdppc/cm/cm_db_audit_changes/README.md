# Cloudera Manager Comprehensive Audit History Script

## Overview

`cm_comprehensive_audit_history.py` is a Python script that creates a comprehensive history of commands and configuration changes in a Cloudera Manager deployment. It extends the functionality of `cm_audit_user_config_changes.sh` by querying multiple audit and history tables in the PostgreSQL database.

## Features

- **Multi-Source History Collection**: Queries multiple audit tables:

  - Configuration changes (`configs_aud`)
  - Command executions (`commands`)
  - Audit logs (`audits`)
  - Service changes (`services_aud`)
  - Cluster changes (`clusters_aud`)
  - Role changes (`roles_aud`)

- **Unified Chronological View**: Combines all history sources into a single, chronologically sorted timeline

- **Multiple Output Formats**: Supports JSON, CSV, and human-readable text formats

- **Flexible Time Filtering**: Filter by date range or number of days

- **Comprehensive Documentation**: Full docstrings and type hints

- **Error Handling**: Robust error handling and logging

## Prerequisites

### Execution Environment

**This script is designed to be executed on the Cloudera Manager node in a Cloudera on Cloud (CDP) environment.**

- **Target System**: Cloudera Manager server node in CDP
- **User Access**: Requires root user privileges
- **Initial Access**: Connect via SSH using the cloudbreak user's private key
- **Elevation**: Use `sudo -i` to switch to root user before execution

### Requirements

- Python 3.6+ (typically Python 3.11 on CDP CM nodes)
- `psycopg2` library (install with: `pip install psycopg2-binary`)
- Access to Cloudera Manager database properties file: `/etc/cloudera-scm-server/db.properties`
- PostgreSQL database access credentials (read from properties file)
- SSH access to the Cloudera Manager node with cloudbreak user's private key
- Root user privileges (obtained via `sudo -i`)

## Installation

### Step 1: Connect to Cloudera Manager Node

```bash
# Connect to the CM node using cloudbreak user's SSH private key
ssh -i /path/to/cloudbreak_private_key cloudbreak@<cm-node-hostname-or-ip>
```

### Step 2: Switch to Root User

```bash
# Switch to root user
sudo -i
```

### Step 3: Install Python Dependencies

```bash
# Install required Python package (as root)
pip install psycopg2-binary

# Or if using a virtual environment (recommended)
python3.11 -m venv ~/py3
source ~/py3/bin/activate
pip install --upgrade pip
pip install psycopg2-binary
```

### Step 4: Transfer Script to CM Node (if needed)

If the script is not already on the CM node, transfer it:

```bash
# From your local machine
scp -i /path/to/cloudbreak_private_key \
    cm_comprehensive_audit_history.py \
    cloudbreak@<cm-node-hostname-or-ip>:~/

# Then on the CM node (after sudo -i)
mv ~cloudbreak/cm_comprehensive_audit_history.py /root/
chmod +x /root/cm_comprehensive_audit_history.py
```

### Step 5: Verify Database Properties File

```bash
# Verify the database properties file exists and is readable
ls -l /etc/cloudera-scm-server/db.properties
cat /etc/cloudera-scm-server/db.properties
```

## Usage

### Execution Workflow

1. **Connect to CM Node**:

   ```bash
   ssh -i /path/to/cloudbreak_private_key cloudbreak@<cm-node-hostname-or-ip>
   ```

2. **Switch to Root**:

   ```bash
   sudo -i
   ```

3. **Activate Virtual Environment** (if using one):

   ```bash
   source ~/py3/bin/activate
   ```

4. **Run the Script**:
   ```bash
   python3.11 /root/cm_comprehensive_audit_history.py [options]
   ```

### Basic Usage

```bash
# Export all history to JSON (default format)
python3.11 cm_comprehensive_audit_history.py

# Export to specific format
python3 cm_comprehensive_audit_history.py --format json -o history.json
python3 cm_comprehensive_audit_history.py --format csv -o history.csv
python3 cm_comprehensive_audit_history.py --format text -o history.txt

# Export all formats at once
python3 cm_comprehensive_audit_history.py --format all -o history
```

### Time Filtering

```bash
# Export last 7 days
python3 cm_comprehensive_audit_history.py --days 7 -o history.json

# Export specific date range (ISO format)
python3 cm_comprehensive_audit_history.py \
  --start "2025-12-01T00:00:00" \
  --end "2025-12-15T23:59:59" \
  -o history.json

# Export using Unix timestamps
python3 cm_comprehensive_audit_history.py \
  --start "1733011200000" \
  --end "1734134399000" \
  -o history.json
```

### Custom Database Properties File

```bash
python3 cm_comprehensive_audit_history.py \
  --db-properties /path/to/custom/db.properties \
  -o history.json
```

### Exclude Specific Users

```bash
python3.11 cm_comprehensive_audit_history.py \
  --exclude-users cloudbreak cmmgmt system_user \
  -o history.json
```

### Export Only Configuration Changes

```bash
# Export only CONFIG_CHANGE events (automatically creates JSON and CSV)
python3.11 cm_comprehensive_audit_history.py --changes -o config_changes

# Export configuration changes for last 30 days
python3.11 cm_comprehensive_audit_history.py --changes --days 30 -o config_changes_last_30_days
```

## Command Line Options

```
--db-properties PATH    Path to database properties file
                       (default: /etc/cloudera-scm-server/db.properties)

-o, --output PATH      Output file path
                       (default: auto-generated with timestamp)

--format FORMAT        Output format: json, csv, text, or all
                       (default: json)

--start TIMESTAMP      Start timestamp (ISO format or Unix timestamp)

--end TIMESTAMP        End timestamp (ISO format or Unix timestamp)

--days N               Number of days to look back from now

--exclude-users USERS  User names to exclude (space-separated)
                       (default: cloudbreak cmmgmt)

--changes              Filter to show only configuration changes
                       (CONFIG_CHANGE events). When used, automatically
                       exports to both JSON and CSV formats.
```

## Output Formats

### JSON Format

Structured JSON with metadata and full record details:

```json
{
  "export_timestamp": "2025-12-15T10:30:00",
  "total_records": 150,
  "history": [
    {
      "event_type": "CONFIG_CHANGE",
      "user_name": "admin",
      "timestamp": 1734262200000,
      "timestamp_iso": "2025-12-15T10:30:00",
      "attr": "hdfs_site/hadoop.security.authentication",
      "value": "kerberos",
      ...
    }
  ]
}
```

### CSV Format

Comma-separated values with all fields as columns. Includes ISO timestamp columns for readability.

### Text Format

Human-readable formatted output with event summaries:

```
================================================================================
Cloudera Manager Comprehensive Audit History
================================================================================
Generated: 2025-12-15 10:30:00
Total Records: 150
================================================================================

--- Record 1 ---
Event Type: CONFIG_CHANGE
Timestamp: 2025-12-15 10:30:00 (1734262200000)
User: admin
Attribute: hdfs_site/hadoop.security.authentication
Value: kerberos
Change Type: MODIFY
Service: HDFS
Cluster: MyCluster
...
```

## Event Types

The script collects the following event types:

1. **CONFIG_CHANGE**: Configuration changes tracked in `configs_aud`

   - Includes service, role, host, and cluster context
   - Shows attribute name, value, and change type (ADD/MODIFY/DELETE)

2. **COMMAND_EXECUTION**: Command executions from `commands` table

   - Includes command name, state, success status, duration
   - Shows associated cluster, service, role, and host

3. **AUDIT_LOG**: Audit log entries from `audits` table

   - Includes audit type, acting user, IP address, allowed status
   - Shows associated entities (cluster, service, role, host)

4. **SERVICE_CHANGE**: Service changes from `services_aud`

   - Tracks service creation, modification, and deletion
   - Includes service type and cluster association

5. **CLUSTER_CHANGE**: Cluster changes from `clusters_aud`

   - Tracks cluster creation, modification, and deletion
   - Includes CDH version and display name

6. **ROLE_CHANGE**: Role changes from `roles_aud`
   - Tracks role creation, modification, and deletion
   - Includes role type, service, and host association

## Database Schema

The script queries the following Cloudera Manager database tables:

- `users` - User accounts
- `revisions` - Revision history
- `configs_aud` - Configuration audit trail
- `commands` - Command executions
- `audits` - Audit logs
- `services_aud` - Service change audit
- `clusters_aud` - Cluster change audit
- `roles_aud` - Role change audit
- `services` - Service definitions
- `clusters` - Cluster definitions
- `roles` - Role definitions
- `hosts` - Host definitions

## Examples

### Example 1: Complete Workflow - Export Last 30 Days

```bash
# Step 1: Connect to CM node
ssh -i ~/.ssh/cloudbreak_key cloudbreak@cm-node.example.com

# Step 2: Switch to root
sudo -i

# Step 3: Activate virtual environment (if using one)
source ~/py3/bin/activate

# Step 4: Run the script
python3.11 /root/cm_comprehensive_audit_history.py \
  --days 30 \
  --format json \
  -o /tmp/cm_audit_last_30_days.json
```

### Example 2: Export Specific Month to All Formats

```bash
python3.11 cm_comprehensive_audit_history.py \
  --start "2025-11-01T00:00:00" \
  --end "2025-11-30T23:59:59" \
  --format all \
  -o /tmp/cm_audit_november_2025
```

### Example 3: Export Configuration Changes Only

```bash
# Export only configuration changes (creates both JSON and CSV)
python3.11 cm_comprehensive_audit_history.py \
  --changes \
  --days 7 \
  -o /tmp/config_changes_week
```

### Example 4: Export Today's Activity to CSV

```bash
python3.11 cm_comprehensive_audit_history.py \
  --days 1 \
  --format csv \
  -o /tmp/cm_audit_today.csv
```

## Troubleshooting

### SSH Connection Issues

If you cannot connect to the CM node:

1. Verify you have the correct cloudbreak user private key
2. Check that the key has correct permissions: `chmod 600 /path/to/cloudbreak_private_key`
3. Verify the CM node hostname/IP is correct
4. Ensure network connectivity to the CM node
5. Check that cloudbreak user exists and SSH access is enabled

### Root Access Issues

If `sudo -i` fails:

1. Verify you're connected as the cloudbreak user
2. Check that cloudbreak user has sudo privileges
3. Some CDP environments may require different elevation methods

### Connection Errors

If you encounter database connection errors:

1. Verify the database properties file exists and is readable: `ls -l /etc/cloudera-scm-server/db.properties`
2. Check that database credentials are correct (review properties file)
3. Ensure network connectivity to the database host from the CM node
4. Verify PostgreSQL is running and accessible
5. Test database connection manually: `psql -h <db-host> -U <db-user> -d <db-name>`

### Missing Records

If expected records are missing:

1. Check time range filters (use `--days` or `--start`/`--end`)
2. Verify excluded users list (default excludes 'cloudbreak' and 'cmmgmt')
3. Check database table permissions
4. Review logs for query errors

### Performance Issues

For large time ranges:

1. Use specific date ranges instead of very large `--days` values
2. Export to CSV format (faster than JSON for large datasets)
3. Consider running during off-peak hours
4. Monitor system resources on the CM node during execution

### Python Environment Issues

If Python or psycopg2 is not found:

1. Verify Python version: `python3.11 --version`
2. Check if virtual environment is activated: `which python3.11`
3. Reinstall psycopg2: `pip install --upgrade psycopg2-binary`
4. If using system Python, ensure you have root privileges

## Logging

The script logs to stdout with timestamps. Log levels:

- **INFO**: Normal operation messages
- **WARNING**: Non-critical issues
- **ERROR**: Critical errors that may affect execution

## Security Considerations

- The script reads database credentials from the properties file
- Output files may contain sensitive configuration data
- Ensure proper file permissions on output files
- Consider encrypting output files for sensitive environments
