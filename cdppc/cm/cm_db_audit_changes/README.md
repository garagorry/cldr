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

- **Selective Source Querying**: Choose which audit sources to query using the `--sources` option (default: all sources)

- **Multiple Output Formats**: Supports JSON, CSV, and human-readable text formats

- **Flexible Time Filtering**: Filter by date range or number of days

- **Progress Indicators**: Visual progress bars for long-running queries to show real-time status

- **Timestamped Output Directories**: Automatically creates timestamped subdirectories for organized output

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
- `psycopg2-binary` library (install with: `pip install psycopg2-binary`)
- `tqdm` library for progress bars (install with: `pip install tqdm`)
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
# Install required Python packages (as root)
pip install psycopg2-binary tqdm

# Or if using a virtual environment (recommended)
python3.11 -m venv ~/py3
source ~/py3/bin/activate
pip install --upgrade pip
pip install psycopg2-binary tqdm

# Or install from requirements.txt
pip install -r requirements.txt
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
# Export all history to JSON (default format, creates timestamped directory in /tmp)
python3.11 cm_comprehensive_audit_history.py

# Export to specific format with custom output directory
python3 cm_comprehensive_audit_history.py --format json --dir /var/tmp/cm_reports
python3 cm_comprehensive_audit_history.py --format csv --dir /tmp
python3 cm_comprehensive_audit_history.py --format text --dir /tmp

# Export all formats at once
python3 cm_comprehensive_audit_history.py --format all --dir /tmp
```

### Time Filtering

```bash
# Export last 7 days (creates timestamped directory in /tmp)
python3 cm_comprehensive_audit_history.py --days 7 --dir /tmp

# Export specific date range (ISO format)
python3 cm_comprehensive_audit_history.py \
  --start "2025-12-01T00:00:00" \
  --end "2025-12-15T23:59:59" \
  --dir /tmp

# Export using Unix timestamps
python3 cm_comprehensive_audit_history.py \
  --start "1733011200000" \
  --end "1734134399000" \
  --dir /tmp
```

### Custom Database Properties File

```bash
python3 cm_comprehensive_audit_history.py \
  --db-properties /path/to/custom/db.properties \
  --dir /tmp
```

### Exclude Specific Users

```bash
python3.11 cm_comprehensive_audit_history.py \
  --exclude-users cloudbreak cmmgmt system_user \
  --dir /tmp
```

### Select Specific Audit Sources

By default, the script queries all audit sources. You can use the `--sources` option to specify which audit sources to include in the report.

**Available Audit Sources:**

- `configs` - Configuration changes (`configs_aud`) - Tracks all configuration property changes (ADD/MODIFY/DELETE) with attribute names, values, and context (service, role, host, cluster)
- `commands` - Command executions (`commands`) - Records all commands executed in the system with state, success status, duration, and associated entities
- `audits` - Audit logs (`audits`) - Comprehensive audit log of all system actions including user activities, access attempts, and security events
- `services` - Service changes (`services_aud`) - Tracks service lifecycle events (creation, modification, deletion) with service type and cluster association
- `clusters` - Cluster changes (`clusters_aud`) - Tracks cluster lifecycle events and configuration changes including CDH version upgrades
- `roles` - Role changes (`roles_aud`) - Tracks role lifecycle events (creation, modification, deletion) for service roles with host and service association
- `all` - All sources (default) - Queries all six audit sources listed above

```bash
# Query only configuration changes and command executions
python3.11 cm_comprehensive_audit_history.py \
  --sources configs commands \
  --dir /tmp

# Query only configuration changes and audit logs for last 7 days
python3.11 cm_comprehensive_audit_history.py \
  --sources configs audits \
  --days 7 \
  --dir /tmp

# Query only service and cluster changes
python3.11 cm_comprehensive_audit_history.py \
  --sources services clusters \
  --dir /tmp

# Query all sources (explicit, same as default)
python3.11 cm_comprehensive_audit_history.py \
  --sources all \
  --dir /tmp
```

### Export Only Configuration Changes

The `--changes` option filters results to show only configuration changes (CONFIG_CHANGE events) from the `configs_aud` table. **Note:** If you use `--sources` to limit which sources are queried, only the specified sources will be queried. If `--sources` is not specified (default: all), the script queries all audit sources, then filters the final results to only include CONFIG_CHANGE events.

When using `--changes`, the script filters the combined results to only show events where `event_type == 'CONFIG_CHANGE'`, which come from the `configs_aud` table.

```bash
# Export only CONFIG_CHANGE events (automatically creates JSON and CSV)
# Queries all sources by default, then filters to CONFIG_CHANGE
# Output will be in a timestamped directory: /tmp/cm_audit_YYYYMMDDHHMMSS/
python3.11 cm_comprehensive_audit_history.py --changes --dir /tmp

# Export configuration changes for last 30 days
python3.11 cm_comprehensive_audit_history.py --changes --days 30 --dir /tmp

# Query only configs source and filter to changes (more efficient)
python3.11 cm_comprehensive_audit_history.py \
  --changes \
  --sources configs \
  --days 7 \
  --dir /tmp

# Export configuration changes to custom directory
python3.11 cm_comprehensive_audit_history.py --changes --days 7 --dir /var/tmp/audit_reports
```

## Command Line Options

```
--db-properties PATH    Path to database properties file
                       (default: /etc/cloudera-scm-server/db.properties)

--dir DIRECTORY        Output directory for reports
                       (default: /tmp)
                       A timestamped subdirectory will be created:
                       {dir}/cm_audit_YYYYMMDDHHMMSS/

-o, --output PATH      Output file base name
                       (default: auto-generated with timestamp)
                       Files will be created in the timestamped directory

--format FORMAT        Output format: json, csv, text, or all
                       (default: json)

--start TIMESTAMP      Start timestamp (ISO format or Unix timestamp)

--end TIMESTAMP        End timestamp (ISO format or Unix timestamp)

--days N               Number of days to look back from now

--exclude-users USERS  User names to exclude (space-separated)
                       (default: cloudbreak cmmgmt)

--sources SOURCES       Audit sources to include in the report.
                       Can specify multiple sources separated by spaces.
                       Valid values: configs, commands, audits, services,
                       clusters, roles, all
                       (default: all)

                       Examples:
                       --sources configs commands
                       --sources configs audits services
                       --sources all

--changes              Filter to show only configuration changes
                       (CONFIG_CHANGE events). When used, automatically
                       exports to both JSON and CSV formats.

                       If --sources is specified, only those sources
                       are queried before filtering. If --sources is
                       not specified (default: all), all sources are
                       queried, then results are filtered to only
                       include CONFIG_CHANGE events from configs_aud.
```

## Output Directory Structure

When you run the script, it automatically creates a timestamped subdirectory in the specified output directory (default: `/tmp`):

```
/tmp/cm_audit_20251224120000/
├── CM_comprehensive_audit_hostname_20251224120000.json
├── CM_comprehensive_audit_hostname_20251224120000.csv
└── CM_comprehensive_audit_hostname_20251224120000.txt
```

The timestamp format is `YYYYMMDDHHMMSS` (year, month, day, hour, minute, second).

## Progress Indicators

The script displays progress bars during execution:

- **Overall progress**: Shows progress through all 6 audit sources being queried
- **Query progress**: For large result sets, shows row-by-row fetching progress
- **Real-time updates**: Displays elapsed time and record counts

This helps you understand that the script is working and not hung, especially for long-running queries.

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

## Event Types and Audit Table Details

The script collects the following event types from their respective audit tables. Each table provides specific information about changes and activities in the Cloudera Manager environment.

### 1. **CONFIG_CHANGE** - Configuration Changes (`configs_aud`)

**Table Structure:**

- Primary Key: `config_id`, `rev` (revision ID)
- Audit Fields: `revtype` (0=ADD, 1=MODIFY, 2=DELETE), `attr` (attribute name), `value` (configuration value)
- Context Fields: `service_id`, `role_id`, `role_config_group_id`, `host_id`, `config_container_id`, `external_account_id`

**What to Expect:**

- **Purpose**: Tracks all configuration property changes across services, roles, hosts, and clusters
- **Change Types**:
  - `ADD` (revtype=0): New configuration property added
  - `MODIFY` (revtype=1): Existing configuration property value changed
  - `DELETE` (revtype=2): Configuration property removed
- **Key Fields in Output**:
  - `attr`: Configuration attribute name (e.g., "hdfs_site/hadoop.security.authentication")
  - `value`: The configuration value that was set
  - `revtype_name`: Human-readable change type (ADD/MODIFY/DELETE)
  - `service_name`, `service_type`: Associated service information
  - `cluster_name`: Associated cluster information
  - `role_name`, `role_type`: Associated role information (if applicable)
  - `host_name`, `host_identifier`: Associated host information (if applicable)
  - `timestamp`: When the change occurred (from `revisions` table)
  - `user_name`, `user_id`: User who made the change (from `revisions` table)
  - `message`: Revision message describing the change

**Use Cases:**

- Track configuration drift over time
- Identify who changed specific configuration properties
- Audit security-related configuration changes
- Review configuration changes before/after upgrades

### 2. **COMMAND_EXECUTION** - Command Executions (`commands`)

**Table Structure:**

- Primary Key: `command_id`
- Execution Fields: `name`, `state`, `start_instant`, `end_instant`, `success`, `result_message`, `arguments`
- Context Fields: `cluster_id`, `service_id`, `role_id`, `host_id`, `parent_id`, `schedule_id`
- Metadata: `creation_instant`, `first_updated_instant`, `audited`, `intent_id`, `stick_with`

**What to Expect:**

- **Purpose**: Records all commands executed in the Cloudera Manager system
- **Command States**: Various states like STARTED, SUCCEEDED, FAILED, ABORTED, etc.
- **Key Fields in Output**:
  - `command_name`: Name of the command executed (e.g., "Start", "Stop", "Restart", "DeployClientConfig")
  - `state`: Current state of the command execution
  - `success`: Boolean indicating if the command succeeded
  - `start_instant`, `end_instant`: Command execution start and end times
  - `duration_ms`: Calculated duration in milliseconds (if both start and end times are available)
  - `result_message`: Result or error message from command execution
  - `arguments`: Command arguments (if any)
  - `cluster_name`, `service_name`, `role_name`, `host_name`: Associated entities
  - `parent_command_name`: Parent command if this is part of a command hierarchy
  - `schedule_name`: Name of the schedule if this was a scheduled command
  - `creation_instant`: When the command was created

**Use Cases:**

- Track service start/stop operations
- Monitor command execution success/failure rates
- Identify failed operations for troubleshooting
- Audit scheduled command executions
- Review command execution history for specific services or clusters

### 3. **AUDIT_LOG** - Audit Log Entries (`audits`)

**Table Structure:**

- Primary Key: `audit_id`
- Audit Fields: `audit_type`, `message`, `created_instant`, `allowed`, `ip_address`
- User Fields: `acting_user_id` (user performing action), `user_id` (target user, if applicable)
- Context Fields: `cluster_id`, `service_id`, `role_id`, `host_id`, `command_id`, `config_container_id`, `host_template_id`, `external_account_id`

**What to Expect:**

- **Purpose**: Comprehensive audit log of all actions performed in the system
- **Audit Types**: Various types like LOGIN, LOGOUT, CONFIG_CHANGE, COMMAND_EXECUTION, etc.
- **Key Fields in Output**:
  - `audit_type`: Type of audit event (e.g., "LOGIN", "LOGOUT", "CONFIG_CHANGE", "COMMAND_EXECUTION")
  - `message`: Descriptive message about the audit event
  - `created_instant`: When the audit event occurred
  - `allowed`: Boolean indicating if the action was allowed
  - `ip_address`: IP address from which the action originated
  - `acting_user_name`: User who performed the action
  - `target_user_name`: Target user (if the action was user-related)
  - `cluster_name`, `service_name`, `role_name`, `host_name`: Associated entities
  - `command_id`: Associated command (if applicable)

**Use Cases:**

- Security auditing and compliance
- Track user login/logout activities
- Monitor access attempts (allowed/denied)
- Investigate suspicious activities
- Compliance reporting

### 4. **SERVICE_CHANGE** - Service Changes (`services_aud`)

**Table Structure:**

- Primary Key: `service_id`, `rev` (revision ID)
- Audit Fields: `revtype` (0=ADD, 1=MODIFY, 2=DELETE), `name`, `service_type`, `display_name`
- Context Fields: `cluster_id`

**What to Expect:**

- **Purpose**: Tracks service lifecycle events (creation, modification, deletion)
- **Change Types**:
  - `ADD` (revtype=0): New service created
  - `MODIFY` (revtype=1): Service properties modified
  - `DELETE` (revtype=2): Service deleted
- **Key Fields in Output**:
  - `name`: Service name
  - `service_type`: Type of service (e.g., "HDFS", "YARN", "HIVE", "HBASE")
  - `display_name`: Human-readable service display name
  - `cluster_name`, `cluster_display_name`: Associated cluster
  - `revtype_name`: Human-readable change type (ADD/MODIFY/DELETE)
  - `timestamp`: When the change occurred (from `revisions` table)
  - `user_name`, `user_id`: User who made the change (from `revisions` table)
  - `message`: Revision message describing the change

**Use Cases:**

- Track service additions and removals
- Monitor service configuration changes
- Audit service lifecycle management
- Review service changes during cluster operations

### 5. **CLUSTER_CHANGE** - Cluster Changes (`clusters_aud`)

**Table Structure:**

- Primary Key: `cluster_id`, `rev` (revision ID)
- Audit Fields: `revtype` (0=ADD, 1=MODIFY, 2=DELETE), `name`, `cdh_version`, `display_name`

**What to Expect:**

- **Purpose**: Tracks cluster lifecycle events and configuration changes
- **Change Types**:
  - `ADD` (revtype=0): New cluster created
  - `MODIFY` (revtype=1): Cluster properties modified (e.g., CDH version upgrade, name change)
  - `DELETE` (revtype=2): Cluster deleted
- **Key Fields in Output**:
  - `name`: Cluster name
  - `cdh_version`: CDH version associated with the cluster
  - `display_name`: Human-readable cluster display name
  - `revtype_name`: Human-readable change type (ADD/MODIFY/DELETE)
  - `timestamp`: When the change occurred (from `revisions` table)
  - `user_name`, `user_id`: User who made the change (from `revisions` table)
  - `message`: Revision message describing the change

**Use Cases:**

- Track cluster creation and deletion
- Monitor CDH version upgrades
- Audit cluster configuration changes
- Review cluster lifecycle events

### 6. **ROLE_CHANGE** - Role Changes (`roles_aud`)

**Table Structure:**

- Primary Key: `role_id`, `rev` (revision ID)
- Audit Fields: `revtype` (0=ADD, 1=MODIFY, 2=DELETE), `name`, `role_type`
- Context Fields: `host_id`, `service_id`, `role_config_group_id`

**What to Expect:**

- **Purpose**: Tracks role lifecycle events (creation, modification, deletion) for service roles
- **Change Types**:
  - `ADD` (revtype=0): New role created (e.g., adding a DataNode role to a host)
  - `MODIFY` (revtype=1): Role properties modified
  - `DELETE` (revtype=2): Role deleted (e.g., removing a role from a host)
- **Key Fields in Output**:
  - `name`: Role name (e.g., "DATANODE", "NAMENODE", "RESOURCEMANAGER")
  - `role_type`: Type of role
  - `host_name`, `host_identifier`: Associated host
  - `service_name`, `service_type`: Associated service
  - `cluster_name`, `cluster_display_name`: Associated cluster (via service)
  - `revtype_name`: Human-readable change type (ADD/MODIFY/DELETE)
  - `timestamp`: When the change occurred (from `revisions` table)
  - `user_name`, `user_id`: User who made the change (from `revisions` table)
  - `message`: Revision message describing the change

**Use Cases:**

- Track role additions and removals from hosts
- Monitor role configuration changes
- Audit role lifecycle management
- Review role changes during service operations
- Track role migrations between hosts

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
# Output will be in: /tmp/cm_audit_YYYYMMDDHHMMSS/
python3.11 /root/cm_comprehensive_audit_history.py \
  --days 30 \
  --format json \
  --dir /tmp
```

### Example 2: Export Specific Month to All Formats

```bash
# Output will be in: /tmp/cm_audit_YYYYMMDDHHMMSS/
python3.11 cm_comprehensive_audit_history.py \
  --start "2025-11-01T00:00:00" \
  --end "2025-11-30T23:59:59" \
  --format all \
  --dir /tmp
```

### Example 3: Export Configuration Changes Only

```bash
# Export only configuration changes (creates both JSON and CSV)
# Output will be in: /tmp/cm_audit_YYYYMMDDHHMMSS/
python3.11 cm_comprehensive_audit_history.py \
  --changes \
  --days 7 \
  --dir /tmp
```

### Example 4: Export Today's Activity to CSV

```bash
# Output will be in: /tmp/cm_audit_YYYYMMDDHHMMSS/
python3.11 cm_comprehensive_audit_history.py \
  --days 1 \
  --format csv \
  --dir /tmp
```

### Example 5: Export to Custom Directory

```bash
# Export to a custom directory with timestamped subdirectory
# Output will be in: /var/tmp/cm_reports/cm_audit_YYYYMMDDHHMMSS/
python3.11 cm_comprehensive_audit_history.py \
  --format all \
  --dir /var/tmp/cm_reports
```

### Example 6: Query Specific Audit Sources

```bash
# Query only configuration changes and command executions
python3.11 cm_comprehensive_audit_history.py \
  --sources configs commands \
  --days 7 \
  --dir /tmp

# Query only audit logs and service changes
python3.11 cm_comprehensive_audit_history.py \
  --sources audits services \
  --format json \
  --dir /tmp

# Query only configuration changes (more efficient than --changes with all sources)
python3.11 cm_comprehensive_audit_history.py \
  --sources configs \
  --changes \
  --days 30 \
  --dir /tmp
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

If Python or required packages are not found:

1. Verify Python version: `python3.11 --version`
2. Check if virtual environment is activated: `which python3.11`
3. Install required packages: `pip install psycopg2-binary tqdm`
4. Or install from requirements.txt: `pip install -r requirements.txt`
5. If using system Python, ensure you have root privileges

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
