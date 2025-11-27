#!/usr/bin/env python3
"""
Hue Database Cleanup Validation Script

This script validates the Hue database to determine if cleanup is needed.
It does NOT perform any cleanup operations - only queries and reports.

Usage:
    python3 validate_hue_cleanup.py --kubeconfig <path> --namespace <namespace> [--output <report_file>]

Example:
    python3 validate_hue_cleanup.py --kubeconfig ~/k8s/config.yml --namespace impala-1764198109-s6vr
"""

import argparse
import subprocess
import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional


class Colors:
    """ANSI color codes for terminal output."""
    INFO = '\033[94m'
    SUCCESS = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def log_info(message: str):
    """Print info message with blue color."""
    print(f"{Colors.INFO}[INFO]{Colors.RESET} {message}")


def log_success(message: str):
    """Print success message with green color."""
    print(f"{Colors.SUCCESS}[SUCCESS]{Colors.RESET} {message}")


def log_warning(message: str):
    """Print warning message with yellow color."""
    print(f"{Colors.WARNING}[WARNING]{Colors.RESET} {message}")


def log_error(message: str):
    """Print error message with red color."""
    print(f"{Colors.ERROR}[ERROR]{Colors.RESET} {message}")

def expand_path(path: str) -> str:
    """
    Expand ~ and environment variables in path.
    
    Args:
        path: Path string that may contain ~ or environment variables
        
    Returns:
        Expanded path string
    """
    return os.path.expanduser(os.path.expandvars(path))

def find_kubectl() -> str:
    """
    Find kubectl binary path.
    
    Checks common installation locations and falls back to PATH lookup.
    Returns the full path to kubectl or 'kubectl' if found in PATH.
    """
    common_paths = [
        os.path.expanduser("~/bin/kubectl"),
        "/usr/local/bin/kubectl",
        "/usr/bin/kubectl",
        "kubectl"
    ]
    
    for path in common_paths:
        if path == "kubectl":
            result = subprocess.run(["which", "kubectl"], capture_output=True)
            if result.returncode == 0:
                return result.stdout.decode().strip()
        elif os.path.exists(path) and os.access(path, os.X_OK):
            return path
    
    return "kubectl"

def run_kubectl_cmd(kubeconfig: str, namespace: str, cmd: List[str], capture_output: bool = True) -> Tuple[int, str, str]:
    """
    Run kubectl command and return result.
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Kubernetes namespace
        cmd: List of kubectl command arguments
        capture_output: Whether to capture stdout/stderr
        
    Returns:
        Tuple of (returncode, stdout, stderr)
    """
    kubectl_path = find_kubectl()
    full_cmd = [kubectl_path, "--kubeconfig", expand_path(kubeconfig), "-n", namespace] + cmd
    try:
        result = subprocess.run(
            full_cmd,
            capture_output=capture_output,
            text=True,
            check=False
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        log_error(f"kubectl not found. Please ensure kubectl is installed and in PATH.")
        sys.exit(1)
    except Exception as e:
        log_error(f"Error running kubectl command: {e}")
        return 1, "", str(e)

def get_hue_backend_pods(kubeconfig: str, namespace: str) -> List[str]:
    """
    Get list of running Hue backend pods.
    
    Attempts to find pods using label selector, falls back to listing all pods
    and filtering by name if label selector fails.
    
    Returns:
        List of pod names that are in Running state
    """
    log_info("Discovering Hue backend pods...")
    returncode, stdout, stderr = run_kubectl_cmd(
        kubeconfig, namespace,
        ["get", "pods", "-o", "json", "-l", "app=huebackend"]
    )
    
    if returncode != 0:
        returncode, stdout, stderr = run_kubectl_cmd(
            kubeconfig, namespace,
            ["get", "pods", "-o", "json"]
        )
        if returncode != 0:
            log_error(f"Failed to get pods: {stderr}")
            return []
    
    try:
        data = json.loads(stdout)
        pods = []
        for item in data.get("items", []):
            name = item["metadata"]["name"]
            if "huebackend" in name.lower() or "hue-backend" in name.lower():
                status = item["status"].get("phase", "Unknown")
                if status == "Running":
                    pods.append(name)
        
        if pods:
            log_success(f"Found {len(pods)} Hue backend pod(s): {', '.join(pods)}")
        else:
            log_warning("No running Hue backend pods found")
        
        return pods
    except json.JSONDecodeError:
        log_error("Failed to parse pod list")
        return []

def get_database_config(kubeconfig: str, namespace: str, pod: str) -> Dict[str, str]:
    """
    Get database configuration from Hue pod.
    
    Reads configuration from zhue.ini or hue.ini and parses the [[database]] section.
    
    Returns:
        Dictionary of database configuration keys and values
    """
    log_info(f"Retrieving database configuration from pod {pod}...")
    
    cmd = ["cat", "/etc/hue/conf/zhue.ini"]
    returncode, stdout, stderr = run_kubectl_cmd(
        kubeconfig, namespace,
        ["exec", pod, "--"] + cmd
    )
    
    if returncode != 0:
        log_warning(f"Could not read zhue.ini, trying alternative location...")
        cmd = ["cat", "/etc/hue/conf/hue.ini"]
        returncode, stdout, stderr = run_kubectl_cmd(
            kubeconfig, namespace,
            ["exec", pod, "--"] + cmd
        )
    
    config = {}
    if returncode == 0:
        in_database_section = False
        for line in stdout.split('\n'):
            if '[[database]]' in line:
                in_database_section = True
                continue
            if in_database_section:
                if line.strip().startswith('[['):
                    break
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    config[key] = value
        
        if config:
            log_success("Database configuration retrieved")
        else:
            log_warning("Could not parse database configuration")
    else:
        log_warning(f"Could not read configuration file: {stderr}")
    
    return config

def get_database_password(kubeconfig: str, namespace: str, pod: str) -> Optional[str]:
    """
    Get database password from pod using altscript.sh.
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Kubernetes namespace
        pod: Pod name
        
    Returns:
        Database password string, or None if retrieval fails
    """
    log_info("Retrieving database password...")
    
    cmd = ["/etc/hue/conf/altscript.sh", "hue_database_password"]
    returncode, stdout, stderr = run_kubectl_cmd(
        kubeconfig, namespace,
        ["exec", pod, "--"] + cmd
    )
    
    if returncode == 0 and stdout.strip():
        log_success("Database password retrieved")
        return stdout.strip()
    else:
        log_warning("Could not retrieve database password")
        return None

def execute_sql_query(kubeconfig: str, namespace: str, pod: str, 
                      db_config: Dict[str, str], password: Optional[str], 
                      query: str) -> Optional[str]:
    """
    Execute SQL query via psql in the pod.
    
    Uses bash -c to set PGPASSWORD environment variable and properly escape
    special characters in password and query. Falls back to passwordless
    connection if password is not available.
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Kubernetes namespace
        pod: Pod name to execute command in
        db_config: Database configuration dictionary
        password: Database password (optional)
        query: SQL query to execute
        
    Returns:
        Query result as string, or None on failure
    """
    host = db_config.get("host", "postgres-service").strip('"').strip("'")
    port = db_config.get("port", "5432").strip('"').strip("'")
    user = db_config.get("user", "hive").strip('"').strip("'")
    database = db_config.get("name", "").strip('"').strip("'")
    
    if not database:
        log_error("Database name not found in configuration")
        return None
    
    kubectl_path = find_kubectl()
    
    if password:
        escaped_password = password.replace("'", "'\"'\"'")
        escaped_query = query.replace("'", "'\"'\"'")
        bash_cmd = f"PGPASSWORD='{escaped_password}' psql -h {host} -p {port} -U {user} -d {database} -t -A -c '{escaped_query}'"
    else:
        escaped_query = query.replace("'", "'\"'\"'")
        bash_cmd = f"psql -h {host} -p {port} -U {user} -d {database} -t -A -c '{escaped_query}'"
    
    full_cmd = [kubectl_path, "--kubeconfig", expand_path(kubeconfig), 
                "-n", namespace, "exec", pod, "--", "bash", "-c", bash_cmd]
    
    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            stderr = result.stderr
            if "Password for user" in stderr or "no password supplied" in stderr:
                log_warning(f"Query failed: Authentication issue - password may not be set correctly")
            else:
                error_msg = stderr[:200] if len(stderr) > 200 else stderr
                log_warning(f"Query failed: {error_msg}")
            return None
    except Exception as e:
        log_error(f"Error executing query: {e}")
        return None

def get_table_counts(kubeconfig: str, namespace: str, pod: str,
                     db_config: Dict[str, str], password: Optional[str]) -> Dict[str, int]:
    """
    Get row counts for target cleanup tables.
    
    Queries the following tables:
    - desktop_document
    - desktop_document2
    - beeswax_session
    - beeswax_savedquery
    - beeswax_queryhistory
    
    Returns:
        Dictionary mapping table names to row counts (-1 indicates query failure)
    """
    log_info("Querying table row counts...")
    
    tables = [
        "desktop_document",
        "desktop_document2",
        "beeswax_session",
        "beeswax_savedquery",
        "beeswax_queryhistory"
    ]
    
    counts = {}
    for table in tables:
        query = f"SELECT COUNT(*) FROM {table};"
        result = execute_sql_query(kubeconfig, namespace, pod, db_config, password, query)
        if result:
            try:
                count = int(result.strip())
                counts[table] = count
                log_info(f"  {table}: {count:,} rows")
            except ValueError:
                log_warning(f"  {table}: Could not parse count")
                counts[table] = -1
        else:
            log_warning(f"  {table}: Query failed")
            counts[table] = -1
    
    return counts

def get_table_sizes(kubeconfig: str, namespace: str, pod: str,
                   db_config: Dict[str, str], password: Optional[str]) -> Dict[str, str]:
    """
    Get disk sizes for desktop and beeswax tables.
    
    Returns:
        Dictionary mapping table names to human-readable size strings
    """
    log_info("Querying table sizes...")
    
    query = """
    SELECT 
        table_name,
        pg_size_pretty(pg_total_relation_size(quote_ident(table_name)::text)) as size
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND (table_name LIKE '%desktop%' OR table_name LIKE '%beeswax%')
    ORDER BY pg_total_relation_size(quote_ident(table_name)::text) DESC;
    """
    
    result = execute_sql_query(kubeconfig, namespace, pod, db_config, password, query)
    sizes = {}
    
    if result:
        for line in result.split('\n'):
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 2:
                    table = parts[0].strip()
                    size = parts[1].strip()
                    sizes[table] = size
    
    return sizes

def get_database_size(kubeconfig: str, namespace: str, pod: str,
                     db_config: Dict[str, str], password: Optional[str]) -> Optional[str]:
    """
    Get total database size in human-readable format.
    
    Returns:
        Database size string (e.g., "1.2 GB"), or None on failure
    """
    log_info("Querying database size...")
    
    database = db_config.get("name", "").strip('"').strip("'")
    query = f"SELECT pg_size_pretty(pg_database_size('{database}')) as database_size;"
    
    result = execute_sql_query(kubeconfig, namespace, pod, db_config, password, query)
    if result:
        return result.strip()
    return None

def check_cleanup_command(kubeconfig: str, namespace: str, pod: str) -> bool:
    """
    Check if Hue cleanup command is available in the pod.
    
    Verifies that the desktop_document_cleanup command exists and is accessible.
    
    Returns:
        True if cleanup command is available, False otherwise
    """
    log_info("Checking if cleanup command is available...")
    
    cmd = ["/opt/hive/build/env/bin/hue", "desktop_document_cleanup", "--help"]
    returncode, stdout, stderr = run_kubectl_cmd(
        kubeconfig, namespace,
        ["exec", pod, "--"] + cmd
    )
    
    if returncode == 0 and "keep-days" in stdout:
        log_success("Cleanup command is available")
        return True
    else:
        log_warning("Cleanup command not found or not accessible")
        return False

def generate_report(kubeconfig: str, namespace: str, pod: str,
                   db_config: Dict[str, str], counts: Dict[str, int],
                   sizes: Dict[str, str], db_size: Optional[str],
                   cleanup_available: bool, output_file: Optional[str]) -> str:
    """
    Generate comprehensive validation report in markdown format.
    
    Determines if cleanup is needed based on row counts and generates
    a detailed report with recommendations and cleanup instructions.
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Kubernetes namespace
        pod: Pod name used for validation
        db_config: Database configuration dictionary
        counts: Dictionary of table row counts
        sizes: Dictionary of table sizes
        db_size: Total database size
        cleanup_available: Whether cleanup command is available
        output_file: Optional output file path
        
    Returns:
        Report content as string
    """
    log_info("Generating validation report...")
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    total_rows = sum(v for v in counts.values() if v >= 0)
    needs_cleanup = any(count >= 30000 for count in counts.values() if count >= 0)
    has_data = total_rows > 0
    
    report = f"""# Hue Database Cleanup Validation Report

## Executive Summary

**Date**: {timestamp}  
**Namespace**: `{namespace}`  
**Backend Pod**: `{pod}`  
**Database**: `{db_config.get('name', 'Unknown')}`  
**Status**: {"⚠️ **Cleanup Recommended**" if needs_cleanup else "✅ **No Cleanup Required**" if has_data else "✅ **Database Empty - No Cleanup Needed**"}

### Key Findings
- Total rows across target tables: **{total_rows:,}**
- Cleanup threshold (30,000 rows per table): {"**EXCEEDED**" if needs_cleanup else "**Not Reached**"}
- Cleanup command available: {"✅ Yes" if cleanup_available else "❌ No"}
- Database size: {db_size if db_size else "Unknown"}

---

## 1. Current Database State

### 1.1 Database Configuration
- **Host**: `{db_config.get('host', 'Unknown')}`
- **Port**: `{db_config.get('port', 'Unknown')}`
- **User**: `{db_config.get('user', 'Unknown')}`
- **Database**: `{db_config.get('name', 'Unknown')}`
- **Engine**: `{db_config.get('engine', 'Unknown')}`

### 1.2 Target Cleanup Tables - Current Row Counts

| Table Name | Row Count | Table Size | Status | Recommendation |
|------------|-----------|------------|--------|----------------|
"""
    
    for table in ["desktop_document", "desktop_document2", "beeswax_session", 
                  "beeswax_savedquery", "beeswax_queryhistory"]:
        count = counts.get(table, -1)
        size = sizes.get(table, "Unknown")
        
        if count == -1:
            status = "❌ Query Failed"
            recommendation = "Check database connectivity"
        elif count == 0:
            status = "✅ Empty"
            recommendation = "No action needed"
        elif count < 30000:
            status = "✅ Normal"
            recommendation = "Monitor regularly"
        else:
            status = "⚠️ **Exceeds Threshold**"
            recommendation = "**Cleanup Recommended**"
        
        report += f"| `{table}` | {count:,} | {size} | {status} | {recommendation} |\n"
    
    report += f"""
### 1.3 Summary Statistics
- **Total Rows**: {total_rows:,}
- **Tables Exceeding Threshold**: {sum(1 for v in counts.values() if v >= 30000)}
- **Empty Tables**: {sum(1 for v in counts.values() if v == 0)}
- **Database Size**: {db_size if db_size else "Unknown"}

---

## 2. Cleanup Recommendations

"""
    
    if needs_cleanup:
        report += """### ⚠️ Cleanup is Recommended

**Reason**: One or more tables exceed the recommended threshold of 30,000 rows.

**Impact if not cleaned**:
- Slower query performance
- Increased login times
- Potential upgrade timeouts
- Risk of application crashes when accessing saved documents

**Recommended Action**: Proceed with cleanup following the steps in Section 3.

"""
    elif has_data:
        report += """### ✅ No Cleanup Required (Currently)

**Status**: Tables contain data but are below the 30,000 row threshold.

**Recommendation**: 
- Continue monitoring table sizes monthly
- Plan cleanup when tables approach 30,000 rows
- Current data levels are acceptable

"""
    else:
        report += """### ✅ No Cleanup Required

**Status**: All target tables are empty.

**Recommendation**: 
- No action needed at this time
- Continue monitoring as data accumulates
- Database is in optimal condition

"""
    
    report += f"""
---

## 3. Cleanup Process (When Needed)

### 3.1 Prerequisites
- ✅ Database backup created
- ✅ Current state documented (this report)
- ✅ Cleanup command available: {"✅ Yes" if cleanup_available else "❌ No"}

### 3.2 Cleanup Steps

**Important**: The cleanup process only removes **UNSAVED documents**. Saved queries and user data are preserved.

1. **Backup Database** (CRITICAL):
   ```bash
   # Create database backup before cleanup
   kubectl exec -it {pod} -n {namespace} -- bash -c \\
     "PGPASSWORD=$(/etc/hue/conf/altscript.sh hue_database_password) \\
      pg_dump -h {db_config.get('host', 'postgres-service')} \\
              -p {db_config.get('port', '5432')} \\
              -U {db_config.get('user', 'hive')} \\
              -d {db_config.get('name', '')} > backup_$(date +%Y%m%d).sql"
   ```

2. **Access Hue Backend Pod**:
   ```bash
   kubectl exec -it {pod} -n {namespace} -- /bin/bash
   ```

3. **Navigate to Hue Bin Directory**:
   ```bash
   cd /opt/hive/build/env/bin
   ```

4. **Run Cleanup Command** (Example: Keep 30 days):
   ```bash
   ./hue desktop_document_cleanup --keep-days 30
   ```
   
   **Parameters**:
   - `--keep-days <x>`: Number of days of history to keep (required)
   - Recommended: 30-90 days based on business requirements

5. **Verify Cleanup Results**:
   ```bash
   /opt/hive/build/env/bin/hue dbshell
   ```
   
   Then run:
   ```sql
   SELECT COUNT(*) FROM desktop_document;
   SELECT COUNT(*) FROM desktop_document2;
   SELECT COUNT(*) FROM beeswax_session;
   SELECT COUNT(*) FROM beeswax_savedquery;
   SELECT COUNT(*) FROM beeswax_queryhistory;
   ```

6. **Restart Virtual Warehouse** (if needed):
   ```bash
   kubectl delete pod {pod} -n {namespace}
   # Wait for pod to restart
   kubectl get pods -n {namespace} | grep huebackend
   ```

### 3.3 Cleanup Command Options

"""
    
    if cleanup_available:
        report += """The cleanup command supports the following options:
- `--keep-days <x>`: Number of days of history data to keep (required)
- `--verbosity {0,1,2,3}`: Verbosity level (optional)
- `--help`: Show help message

**Example**:
```bash
# Keep 30 days of data
./hue desktop_document_cleanup --keep-days 30

# Keep 90 days of data with verbose output
./hue desktop_document_cleanup --keep-days 90 --verbosity 2
```
"""
    else:
        report += """⚠️ **Cleanup command not available** in the current pod.

Please verify:
- Pod has access to `/opt/hive/build/env/bin/hue`
- Hue installation is complete
- User has appropriate permissions
"""
    
    report += f"""
---

## 4. Monitoring Recommendations

### 4.1 Regular Monitoring Schedule

**Frequency**: Monthly or quarterly

**Monitoring Queries**:
```sql
SELECT COUNT(*) FROM desktop_document;
SELECT COUNT(*) FROM desktop_document2;
SELECT COUNT(*) FROM beeswax_session;
SELECT COUNT(*) FROM beeswax_savedquery;
SELECT COUNT(*) FROM beeswax_queryhistory;
```

### 4.2 Cleanup Threshold

- **Optimal**: Less than 30,000 rows per table
- **Warning**: 20,000-30,000 rows (plan cleanup)
- **Critical**: Over 30,000 rows (cleanup recommended)

### 4.3 Automated Monitoring Script

You can re-run this validation script periodically:
```bash
python3 validate_hue_cleanup.py \\
  --kubeconfig {kubeconfig} \\
  --namespace {namespace} \\
  --output validation_report_YYYYMMDD.md
```

---

## 5. Troubleshooting

### 5.1 Common Issues

**Issue**: Cannot connect to database
- **Solution**: Verify database service and credentials
- **Check**: Database configuration in `/etc/hue/conf/zhue.ini`

**Issue**: Cleanup command not found
- **Solution**: Verify path `/opt/hive/build/env/bin/hue desktop_document_cleanup`
- **Check**: Pod has correct Hue installation

**Issue**: Permission denied
- **Solution**: Ensure running with appropriate user permissions
- **Check**: Pod security context and user permissions

### 5.2 Validation Queries

**Check for documents older than X days**:
```sql
SELECT COUNT(*) 
FROM desktop_document 
WHERE last_modified < NOW() - INTERVAL '30 days';
```

**Check document distribution**:
```sql
SELECT 
    DATE_TRUNC('month', last_modified) as month,
    COUNT(*) as count
FROM desktop_document
GROUP BY DATE_TRUNC('month', last_modified)
ORDER BY month DESC;
```

---

## 6. Important Notes

⚠️ **Critical Warnings**:
1. **Always backup the database** before running cleanup
2. **Cleanup only removes UNSAVED documents** - saved data is preserved
3. **Test cleanup in non-production** environment first if possible
4. **Document current state** before cleanup (this report serves that purpose)

✅ **What Gets Cleaned**:
- Unsaved/temporary documents
- Old query sessions
- Stale query history

✅ **What is Preserved**:
- Saved queries
- User preferences
- User settings
- Explicitly saved documents

---

## 7. Conclusion

"""
    
    if needs_cleanup:
        report += """### ⚠️ Action Required

**Cleanup is recommended** due to tables exceeding the 30,000 row threshold.

**Next Steps**:
1. Review this report
2. Create database backup
3. Schedule cleanup during maintenance window
4. Execute cleanup following steps in Section 3
5. Verify results and monitor

"""
    elif has_data:
        report += """### ✅ Monitoring Recommended

**Current Status**: Database contains data but is within acceptable limits.

**Next Steps**:
1. Continue regular monitoring
2. Plan cleanup when approaching thresholds
3. Document any performance issues

"""
    else:
        report += """### ✅ No Action Required

**Current Status**: Database is empty and in optimal condition.

**Next Steps**:
1. Continue monitoring as data accumulates
2. Re-run validation periodically
3. Plan cleanup process for when data grows

"""
    
    report += f"""
---

**Report Generated**: {timestamp}  
**Validation Script**: validate_hue_cleanup.py  
**Namespace**: {namespace}  
**Pod**: {pod}

---

*This report was generated by the Hue Database Cleanup Validation Script.  
The script performs read-only operations and does NOT modify any data.*
"""
    
    if output_file:
        output_path = expand_path(output_file)
        with open(output_path, 'w') as f:
            f.write(report)
        log_success(f"Report written to: {output_path}")
    else:
        timestamp_file = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"hue_cleanup_validation_{namespace}_{timestamp_file}.md"
        with open(output_path, 'w') as f:
            f.write(report)
        log_success(f"Report written to: {output_path}")
    
    return report

def main():
    """
    Main entry point for the validation script.
    
    Parses command line arguments, discovers pods, retrieves database information,
    and generates a comprehensive validation report.
    """
    parser = argparse.ArgumentParser(
        description="Validate Hue database cleanup requirements",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python3 validate_hue_cleanup.py --kubeconfig ~/k8s/config.yml --namespace my-namespace
  
  # With custom output file
  python3 validate_hue_cleanup.py --kubeconfig ~/k8s/config.yml --namespace my-namespace --output report.md
  
  # Using environment variable for kubeconfig
  export KUBECONFIG=~/k8s/config.yml
  python3 validate_hue_cleanup.py --namespace my-namespace
        """
    )
    
    parser.add_argument(
        "--kubeconfig",
        type=str,
        help="Path to kubeconfig file (required if KUBECONFIG env var not set)"
    )
    
    parser.add_argument(
        "--namespace",
        type=str,
        required=True,
        help="Kubernetes namespace where Hue backend pods are running"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for the report (default: auto-generated filename)"
    )
    
    parser.add_argument(
        "--pod",
        type=str,
        help="Specific Hue backend pod name (auto-discovered if not provided)"
    )
    
    args = parser.parse_args()
    
    kubeconfig = args.kubeconfig or os.environ.get("KUBECONFIG")
    if not kubeconfig:
        log_error("kubeconfig not provided. Use --kubeconfig or set KUBECONFIG environment variable.")
        sys.exit(1)
    
    kubeconfig = expand_path(kubeconfig)
    if not os.path.exists(kubeconfig):
        log_error(f"Kubeconfig file not found: {kubeconfig}")
        sys.exit(1)
    
    log_info(f"Using kubeconfig: {kubeconfig}")
    log_info(f"Target namespace: {args.namespace}")
    
    if args.pod:
        pod = args.pod
        log_info(f"Using specified pod: {pod}")
    else:
        pods = get_hue_backend_pods(kubeconfig, args.namespace)
        if not pods:
            log_error("No Hue backend pods found. Please specify pod with --pod option.")
            sys.exit(1)
        pod = pods[0]
        if len(pods) > 1:
            log_warning(f"Multiple pods found, using: {pod}")
    
    db_config = get_database_config(kubeconfig, args.namespace, pod)
    if not db_config.get("name"):
        log_error("Could not determine database name. Please check pod configuration.")
        sys.exit(1)
    
    password = get_database_password(kubeconfig, args.namespace, pod)
    counts = get_table_counts(kubeconfig, args.namespace, pod, db_config, password)
    sizes = get_table_sizes(kubeconfig, args.namespace, pod, db_config, password)
    db_size = get_database_size(kubeconfig, args.namespace, pod, db_config, password)
    cleanup_available = check_cleanup_command(kubeconfig, args.namespace, pod)
    
    report = generate_report(
        kubeconfig, args.namespace, pod,
        db_config, counts, sizes, db_size,
        cleanup_available, args.output
    )
    
    print("\n" + "="*70)
    total_rows = sum(v for v in counts.values() if v >= 0)
    needs_cleanup = any(count >= 30000 for count in counts.values() if count >= 0)
    
    if needs_cleanup:
        log_warning("CLEANUP RECOMMENDED: One or more tables exceed 30,000 rows")
    elif total_rows > 0:
        log_success(f"Database contains {total_rows:,} rows - within acceptable limits")
    else:
        log_success("Database is empty - no cleanup needed")
    
    print("="*70 + "\n")
    
    log_info("Validation complete. See report for detailed information.")

if __name__ == "__main__":
    main()

