#!/bin/bash

################################################################################
# Solr All-in-One Management Script
#
# This script provides backup, delete, and restore operations for Solr collections
# using keytab-based Kerberos authentication and HDFS for backup storage.
#
# Usage:
#   ./solr_all_in_one.sh <command> [OPTIONS]
#
# Commands:
#   backup    Backup Solr collections to HDFS
#   delete    Delete Solr collections
#   restore   Restore Solr collections from HDFS backup
#
# Examples:
#   ./solr_all_in_one.sh backup
#   ./solr_all_in_one.sh backup -c vertex_index -c edge_index
#   ./solr_all_in_one.sh delete -d
#   ./solr_all_in_one.sh restore -a
#
################################################################################

set -euo pipefail

# Script configuration
SCRIPT_NAME=$(basename "$0")
SCRIPT_VERSION="2.0"
COMMAND=""
DRY_RUN=false
FORCE=false
VERBOSE=false
DEBUG=false
LOG_FILE=""
SPECIFIC_COLLECTIONS=()
ADD_TIMESTAMP=true
BACKUP_NAME_PATTERN=""
RESTORE_ALL=false
CREATE_EMPTY_COLLECTIONS=false
SAVE_CONFIGS=false
HDFS_BACKUP_BASE="/user/solr/backup"
HDFS_BACKUP_LOCATION=""
SOLR_HOST=""
SOLR_ENDPOINT=""
SERVICE_NAME="solr-SOLR_SERVER"
SOLRCTL_CMD="solrctl"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Statistics
COLLECTIONS_FOUND=0
COLLECTIONS_PROCESSED=0
COLLECTIONS_FAILED=0
FAILED_COLLECTIONS=()
RESTORE_REQUEST_IDS=()
declare -A RESTORE_COLLECTION_MAP
declare -A RESTORE_STATUS_DETAILS

# Python command
PYTHON_CMD=""

################################################################################
# Logging Functions
################################################################################

log_message() {
    # Log a message with timestamp and color coding.
    #
    # Args:
    #   level: Log level (INFO, SUCCESS, WARNING, ERROR, VERBOSE)
    #   message: Message to log (remaining arguments)
    #
    # Output:
    #   Writes to stderr and optionally to LOG_FILE if set.
local level="$1"
shift
local message="$*"
local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

case "$level" in
    "INFO")
        echo -e "${BLUE}[${timestamp}] INFO:${NC} ${message}" >&2
        ;;
    "SUCCESS")
        echo -e "${GREEN}[${timestamp}] SUCCESS:${NC} ${message}" >&2
        ;;
    "WARNING")
        echo -e "${YELLOW}[${timestamp}] WARNING:${NC} ${message}" >&2
        ;;
    "ERROR")
        echo -e "${RED}[${timestamp}] ERROR:${NC} ${message}" >&2
        ;;
    "VERBOSE")
        if [[ "$VERBOSE" == true ]]; then
            echo -e "${CYAN}[${timestamp}] VERBOSE:${NC} ${message}" >&2
        fi
        ;;
esac

if [[ -n "$LOG_FILE" ]]; then
    echo "[${timestamp}] ${level}: ${message}" >> "$LOG_FILE"
fi
}

log_error() {
    # Log an error message.
    log_message "ERROR" "$@"
}

log_success() {
    # Log a success message.
    log_message "SUCCESS" "$@"
}

log_info() {
    # Log an info message.
    log_message "INFO" "$@"
}

log_warning() {
    # Log a warning message.
    log_message "WARNING" "$@"
}

log_verbose() {
    # Log a verbose message (only if VERBOSE=true).
    log_message "VERBOSE" "$@"
}

################################################################################
# Utility Functions
################################################################################

show_help() {
cat << EOF
${SCRIPT_NAME} v${SCRIPT_VERSION}

All-in-one Solr collection management script with keytab-based authentication.

USAGE:
${SCRIPT_NAME} <command> [OPTIONS]

COMMANDS:
backup              Backup Solr collections to HDFS
delete              Delete Solr collections
restore             Restore Solr collections from HDFS backup
list                List all Solr collections

OPTIONS (Common to all commands):
-h, --help              Show this help message and exit
-d, --dry-run           Preview operations without executing
-f, --force             Skip confirmation prompts (use with caution)
-c, --collection NAME   Operate on specific collection (can be used multiple times)
-v, --verbose           Enable verbose output
--debug                 Enable debug mode (curl --verbose for API calls)
-l, --log FILE          Write log to specified file
--host HOSTNAME         Specify Solr hostname (auto-detected if not provided)

BACKUP OPTIONS:
-b, --backup-base PATH  HDFS base path for backups (default: /user/solr/backup)
-t, --timestamp         Add timestamp subdirectory (default: enabled)
-n, --name PATTERN      Backup name pattern (default: {collection}_backup)
--save-configs          Save collection configurations for recovery (uses solrctl)

DELETE OPTIONS:
(No additional options)

RESTORE OPTIONS:
-a, --all               Restore all collections found in backup location
-b, --backup-location   HDFS path to backup location (required for restore)
-n, --name PATTERN      Backup name pattern (default: {collection}_backup)
--create-empty          Create empty collections with saved configs (no data restore)

EXAMPLES:
# List all collections
${SCRIPT_NAME} list

# Backup all collections
${SCRIPT_NAME} backup

# Backup specific collections
${SCRIPT_NAME} backup -c vertex_index -c edge_index

# Dry run delete
${SCRIPT_NAME} delete -d

# Delete specific collections
${SCRIPT_NAME} delete -c collection1 -c collection2

# Restore all collections from latest backup
${SCRIPT_NAME} restore -a

# Restore specific collections from backup
${SCRIPT_NAME} restore -c vertex_index -c edge_index -b /user/solr/backup/20231223_153000


# Verbose backup with logging
${SCRIPT_NAME} backup -v -l /tmp/solr_backup.log

# Debug mode (shows curl verbose output)
${SCRIPT_NAME} backup --debug

NOTES:
- This script uses keytab-based Kerberos authentication
- Must be run on a node where Solr is running
- HDFS operations require appropriate permissions (for backup/restore)
- Use dry-run mode (-d) to preview operations
- Timestamp subdirectories are enabled by default for backups
- List command does not require HDFS access
- Debug mode (--debug) enables curl --verbose for detailed API debugging

EOF
}

show_banner() {
    # Display script banner with version information.
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║      Solr All-in-One Management Script v${SCRIPT_VERSION}      ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo
}

validate_prerequisites() {
    # Validate that all required tools are available.
    #
    # Checks for: curl, jq, hdfs, kinit
    # Also determines Python command for optional JSON parsing fallback.
    #
    # Exits with error code 1 if any required tools are missing.
local missing_tools=()

if ! command -v curl &> /dev/null; then
    missing_tools+=("curl")
fi

if ! command -v jq &> /dev/null; then
    missing_tools+=("jq")
fi

if ! command -v hdfs &> /dev/null; then
    missing_tools+=("hdfs")
fi

if ! command -v kinit &> /dev/null; then
    missing_tools+=("kinit")
fi

if [[ ${#missing_tools[@]} -gt 0 ]]; then
    log_error "Missing required tools: ${missing_tools[*]}"
    log_error "Please install the missing tools and try again"
    exit 1
fi

if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
fi

log_verbose "Prerequisites validated"
}

validate_solr_running() {
    # Validate that Solr service is running on this node.
    #
    # Sets PROCESS_DIR to the Solr process directory if found.
    # Exits with error code 1 if Solr is not running.
log_info "Validating that Solr is running on this node..."
PROCESS_DIR=$(ls -d /var/run/cloudera-scm-agent/process/*${SERVICE_NAME} 2>/dev/null | tail -n1 || true)

if [[ -z "$PROCESS_DIR" ]]; then
    log_error "This node does not appear to be running ${SERVICE_NAME}"
    log_error "Please run this script on a node where Solr is running"
    exit 1
fi

log_success "Solr service detected: $PROCESS_DIR"
}

get_latest_keytab() {
    # Get the path to the latest keytab file for a service.
    #
    # Args:
    #   service: Service name to find keytab for
    #   keytab_name: Name of the keytab file
    #
    # Returns:
    #   Full path to the keytab file
    #
    # Exits with error code 1 if no process directory is found.
local service="$1"
local keytab_name="$2"
local keytab_dir
keytab_dir=$(ls -1rdth /var/run/cloudera-scm-agent/process/*${service} 2>/dev/null | tail -n 1 || true)

if [[ -z "$keytab_dir" ]]; then
    log_error "No process directory found for $service"
    exit 1
fi

echo "${keytab_dir}/${keytab_name}"
}

kinit_with_keytab() {
    # Authenticate using a Kerberos keytab file.
    #
    # Args:
    #   keytab: Path to the keytab file
    #
    # Extracts the principal from the keytab and authenticates.
    # Exits with error code 1 if principal extraction or authentication fails.
local keytab="$1"
local principal
principal=$(klist -kt "$keytab" | tail -n 1 | awk '{print $4}')

if [[ -z "$principal" ]]; then
    log_error "No principal found in $keytab"
    exit 1
fi

log_info "Authenticating as $principal"
kinit -kt "$keytab" "$principal"

if [[ $? -ne 0 ]]; then
    log_error "Failed to authenticate with keytab"
    exit 1
fi

log_success "Authentication successful"
}


restore_collection_solrctl() {
    # Restore a Solr collection using solrctl.
    #
    # Args:
    #   collection: Name of the collection to restore
    #   backup_name: Name of the backup to restore from
    #   hdfs_location: HDFS path to the backup location
    #   request_id: Optional request ID (generated if not provided)
    #
    # Returns:
    #   Echoes request_id to stdout, returns 0 on success, 1 on failure.
    #   Handles "collection exists" as a non-fatal success case.
local collection="$1"
local backup_name="$2"
local hdfs_location="$3"
local request_id="${4:-}"

if [[ -n "$PROCESS_DIR" ]] && [[ -f "${PROCESS_DIR}/solr-env.sh" ]]; then
    source "${PROCESS_DIR}/solr-env.sh" 2>/dev/null || true
fi

local solrctl_path="$SOLRCTL_CMD"
if ! command -v "$SOLRCTL_CMD" &> /dev/null; then
    if [[ -f "/usr/bin/solrctl" ]]; then
        solrctl_path="/usr/bin/solrctl"
    elif [[ -f "/opt/cloudera/parcels/CDH/bin/solrctl" ]]; then
        solrctl_path="/opt/cloudera/parcels/CDH/bin/solrctl"
    elif [[ -n "$PROCESS_DIR" ]] && [[ -f "${PROCESS_DIR}/../../bin/solrctl" ]]; then
        solrctl_path="${PROCESS_DIR}/../../bin/solrctl"
    else
        log_error "solrctl not found in PATH or common locations"
        return 1
    fi
fi

if [[ -z "$request_id" ]]; then
    request_id="restore_${collection}_$(date +%s)"
fi

log_verbose "Restoring collection: $collection"
log_verbose "Backup name: $backup_name"
log_verbose "HDFS location: $hdfs_location"
log_verbose "Request ID: $request_id"
log_verbose "solrctl path: $solrctl_path"

if [[ "$DRY_RUN" == true ]]; then
    log_info "[DRY RUN] Would restore collection: $collection"
    log_info "[DRY RUN]   Backup name: $backup_name"
    log_info "[DRY RUN]   HDFS location: $hdfs_location"
    log_info "[DRY RUN]   Request ID: $request_id"
    log_info "[DRY RUN]   Command: $solrctl_path collection --restore $collection -b $backup_name -l $hdfs_location -i $request_id"
    echo "$request_id"
    return 0
fi

if ! klist 2>/dev/null | grep -q "solr/"; then
    kdestroy || true
    local solr_keytab
    solr_keytab=$(get_latest_keytab "$SERVICE_NAME" "solr.keytab")
    kinit_with_keytab "$solr_keytab"
fi

log_info "Executing: solrctl collection --restore $collection -b $backup_name -l $hdfs_location -i $request_id"
local solrctl_output
local solrctl_exit_code
solrctl_output=$("$solrctl_path" collection --restore "$collection" -b "$backup_name" -l "$hdfs_location" -i "$request_id" 2>&1)
solrctl_exit_code=$?

echo "$solrctl_output" >&2

if echo "$solrctl_output" | grep -q "Collection.*exists"; then
    log_warning "Collection '$collection' already exists. Skipping restore." >&2
    echo "$request_id" >&1
    return 0
elif [[ $solrctl_exit_code -eq 0 ]]; then
    log_success "Restore request submitted successfully (Request ID: $request_id)" >&2
    echo "$request_id" >&1
    return 0
else
    log_error "Failed to submit restore request (exit code: $solrctl_exit_code)" >&2
    echo "$request_id" >&1
    return 1
fi
}

check_restore_status() {
    # Check the status of a restore operation using solrctl.
    #
    # Args:
    #   request_id: The restore request ID to check
    #   silent: If true, suppress log messages (default: false)
    #
    # Returns:
    #   0: Restore completed successfully
    #   1: Restore failed
    #   2: Restore still running or status unknown
    #
    # Notes:
    #   - Parses JSON from solrctl output even if exit code is non-zero
    #   - Handles "request not found" as normal (assumes running)
    #   - Stores status JSON in RESTORE_STATUS_DETAILS for final verification
local request_id="$1"
local silent="${2:-false}"

if [[ -n "$PROCESS_DIR" ]] && [[ -f "${PROCESS_DIR}/solr-env.sh" ]]; then
    source "${PROCESS_DIR}/solr-env.sh" 2>/dev/null || true
fi

if ! klist 2>/dev/null | grep -q "solr/"; then
    if [[ -n "$PROCESS_DIR" ]]; then
        local solr_keytab
        solr_keytab=$(get_latest_keytab "solr")
        if [[ -n "$solr_keytab" ]] && [[ -f "$solr_keytab" ]]; then
            kinit_with_keytab "solr" "$solr_keytab" >/dev/null 2>&1 || true
        fi
    fi
fi

local solrctl_path="$SOLRCTL_CMD"
if ! command -v "$SOLRCTL_CMD" &> /dev/null; then
    if [[ -f "/usr/bin/solrctl" ]]; then
        solrctl_path="/usr/bin/solrctl"
    elif [[ -f "/opt/cloudera/parcels/CDH/bin/solrctl" ]]; then
        solrctl_path="/opt/cloudera/parcels/CDH/bin/solrctl"
    elif [[ -n "$PROCESS_DIR" ]] && [[ -f "${PROCESS_DIR}/../../bin/solrctl" ]]; then
        solrctl_path="${PROCESS_DIR}/../../bin/solrctl"
    else
        [[ "$silent" != "true" ]] && log_warning "solrctl not found, cannot check status"
        return 1
    fi
fi

local status_output
status_output=$("$solrctl_path" collection --request-status "$request_id" 2>&1)
local exit_code=$?

local status_json=""

if command -v grep &> /dev/null; then
    status_json=$(echo "$status_output" | grep -oP '\{.*\}' 2>/dev/null || echo "")
    
    if [[ -n "$status_json" ]] && ! echo "$status_json" | jq . >/dev/null 2>&1; then
        status_json=""
    fi
fi

if [[ -z "$status_json" ]] || ! echo "$status_json" | jq . >/dev/null 2>&1; then
    local raw_json=$(echo "$status_output" | sed -n '/^{/,$p' || echo "")
    if [[ -n "$raw_json" ]]; then
        status_json=$(echo "$raw_json" | jq -c . 2>/dev/null || echo "")
    fi
fi

if [[ -n "$status_json" ]] && echo "$status_json" | jq . >/dev/null 2>&1; then
    RESTORE_STATUS_DETAILS["$request_id"]="$status_json"
    
    local state
    local msg
    
    state=$(echo "$status_json" | jq -r '.status.state // empty' 2>/dev/null || echo "")
    msg=$(echo "$status_json" | jq -r '.status.msg // empty' 2>/dev/null || echo "")
    
    if [[ "$DEBUG" == true ]]; then
        log_verbose "Status for $request_id: state='$state', msg='$msg' (solrctl exit code: $exit_code)"
        if [[ -z "$state" ]]; then
            log_verbose "WARNING: State is empty but JSON is valid. JSON length: ${#status_json}"
        fi
    fi
    
    if [[ "$state" == "completed" ]]; then
        [[ "$silent" != "true" ]] && log_success "Restore completed: $msg"
        return 0
    elif [[ "$state" == "failed" ]]; then
        [[ "$silent" != "true" ]] && log_error "Restore failed: $msg"
        return 1
    elif [[ "$state" == "running" ]]; then
        [[ "$silent" != "true" ]] && log_info "Restore in progress: $msg"
        return 2
    elif [[ -z "$state" ]]; then
        [[ "$silent" != "true" ]] && log_verbose "Status state empty, assuming running"
        return 2
    else
        [[ "$silent" != "true" ]] && log_verbose "Unknown state '$state', assuming running"
        return 2
    fi
else
    if [[ $exit_code -ne 0 ]]; then
        if echo "$status_output" | grep -qi "not found\|does not exist\|unknown\|not available"; then
            if [[ "$DEBUG" == true ]]; then
                log_verbose "Request $request_id not found yet (normal right after submission), assuming running"
            fi
            return 2
        else
            if [[ "$DEBUG" == true ]]; then
                log_verbose "solrctl failed for $request_id (exit code: $exit_code)"
                log_verbose "Error output: $(echo "$status_output" | head -c 500)"
            elif [[ "$silent" != "true" ]]; then
                log_warning "Failed to check restore status (exit code: $exit_code)"
            fi
            return 2
        fi
    else
        if [[ "$DEBUG" == true ]]; then
            log_verbose "Could not parse JSON for $request_id, assuming running"
            log_verbose "Status output (first 500 chars): $(echo "$status_output" | head -c 500)"
            log_verbose "Extracted JSON (first 200 chars): $(echo "$status_json" | head -c 200)"
        elif [[ "$silent" != "true" ]]; then
            log_verbose "Could not parse JSON, assuming running"
        fi
        return 2
    fi
fi
}


get_solr_endpoint() {
    # Get or determine the Solr endpoint URL.
    #
    # Sets SOLR_ENDPOINT to https://${SOLR_HOST}:8985
    # Uses hostname -f if SOLR_HOST is not set.
    # Exits with error code 1 if hostname cannot be determined.
if [[ -z "$SOLR_HOST" ]]; then
    SOLR_HOST=$(hostname -f 2>/dev/null || hostname)
fi

if [[ -z "$SOLR_HOST" ]]; then
    log_error "Unable to determine hostname. Please specify with --host option"
    exit 1
fi

SOLR_ENDPOINT="https://${SOLR_HOST}:8985"
log_verbose "Using Solr endpoint: $SOLR_ENDPOINT"
}


get_cluster_state_once() {
    # Get Solr cluster state using solrctl and save to output file.
    #
    # Args:
    #   output_file: Path to write the cluster state JSON
    #
    # Returns:
    #   0 on success, 1 on failure
    #
    # Notes:
    #   - Uses timestamped temp file to avoid conflicts
    #   - Extracts JSON from output (may include HTTP headers)
    #   - Validates JSON before returning
local output_file="$1"

if [[ -n "$PROCESS_DIR" ]] && [[ -f "${PROCESS_DIR}/solr-env.sh" ]]; then
    source "${PROCESS_DIR}/solr-env.sh" 2>/dev/null || true
fi

local solrctl_path="$SOLRCTL_CMD"
if ! command -v "$SOLRCTL_CMD" &> /dev/null; then
    if [[ -f "/usr/bin/solrctl" ]]; then
        solrctl_path="/usr/bin/solrctl"
    elif [[ -f "/opt/cloudera/parcels/CDH/bin/solrctl" ]]; then
        solrctl_path="/opt/cloudera/parcels/CDH/bin/solrctl"
    elif [[ -n "$PROCESS_DIR" ]] && [[ -f "${PROCESS_DIR}/../../bin/solrctl" ]]; then
        solrctl_path="${PROCESS_DIR}/../../bin/solrctl"
    else
        log_warning "solrctl not found in PATH or common locations, cannot get cluster state"
        return 1
    fi
fi

if ! klist 2>/dev/null | grep -q "solr/"; then
    kdestroy || true
    local solr_keytab
    solr_keytab=$(get_latest_keytab "$SERVICE_NAME" "solr.keytab")
    kinit_with_keytab "$solr_keytab"
fi

local hostname_fqdn
hostname_fqdn=$(hostname -f 2>/dev/null || hostname)
local raw_output
raw_output="/tmp/solr_clusterstate_${hostname_fqdn}_$(date +%Y%m%d%H%M%S)_$$.out"

rm -f "$raw_output" 2>/dev/null || true

"$solrctl_path" cluster --get-clusterstate "$raw_output" 2>/dev/null
local exit_code=$?

if [[ $exit_code -ne 0 ]] || [[ ! -s "$raw_output" ]]; then
    log_verbose "Failed to get cluster state via solrctl (exit code: $exit_code)"
    if [[ "$DEBUG" == true ]] && [[ -f "$raw_output" ]]; then
        log_verbose "Debug: First 20 lines of output:"
        head -20 "$raw_output" 2>/dev/null | while IFS= read -r line; do
            log_verbose "  $line"
        done
    fi
    rm -f "$raw_output" 2>/dev/null || true
    return 1
fi

if ! jq -e . "$raw_output" >/dev/null 2>&1; then
    sed -n '/^{/,$p' "$raw_output" | jq -c . > "$output_file" 2>/dev/null
    if [[ $? -ne 0 ]] || [[ ! -s "$output_file" ]]; then
        log_verbose "Failed to extract valid JSON from cluster state output"
        if [[ "$DEBUG" == true ]]; then
            log_verbose "Debug: First 30 lines of raw output:"
            head -30 "$raw_output" | while IFS= read -r line; do
                log_verbose "  $line"
            done
        fi
        rm -f "$raw_output" "$output_file" 2>/dev/null || true
        return 1
    fi
else
    cp "$raw_output" "$output_file"
fi

rm -f "$raw_output" 2>/dev/null || true

if ! jq -e . "$output_file" >/dev/null 2>&1; then
    log_verbose "Output file does not contain valid JSON"
    rm -f "$output_file" 2>/dev/null || true
    return 1
fi

return 0
}

get_collection_metadata() {
    # Get collection metadata from cluster state.
    #
    # Args:
    #   collection: Name of the collection
    #   cluster_state_file: Optional path to cached cluster state file
    #
    # Returns:
    #   Echoes JSON metadata to stdout, returns 0 on success, 1 on failure.
local collection="$1"
local cluster_state_file="${2:-}"

local temp_state_file=""
if [[ -z "$cluster_state_file" ]] || [[ ! -f "$cluster_state_file" ]]; then
    temp_state_file=$(mktemp)
    if ! get_cluster_state_once "$temp_state_file"; then
        rm -f "$temp_state_file" 2>/dev/null || true
        return 1
    fi
    cluster_state_file="$temp_state_file"
fi

local metadata
metadata=$(jq -r --arg coll "$collection" '.cluster.collections[$coll] // empty' "$cluster_state_file" 2>/dev/null)

if [[ -n "$temp_state_file" ]]; then
    rm -f "$temp_state_file" 2>/dev/null || true
fi

if [[ -z "$metadata" ]] || [[ "$metadata" == "null" ]] || [[ "$metadata" == "" ]]; then
    log_verbose "Collection '$collection' not found in cluster state"
    return 1
fi

echo "$metadata"
return 0
}

backup_collection_config() {
    # Backup a Solr collection configuration using solrctl.
    #
    # Args:
    #   collection: Collection name (for logging)
    #   backup_dir: Directory to save the config backup
    #   config_name: Name of the config to backup
    #
    # Returns:
    #   0 on success, 1 on failure
    #
    # Notes:
    #   - Skips if config already backed up (shared configs)
    #   - solrctl creates the target directory, so we remove it first if exists
local collection="$1"
local backup_dir="$2"
local config_name="$3"

if [[ -n "$PROCESS_DIR" ]] && [[ -f "${PROCESS_DIR}/solr-env.sh" ]]; then
    source "${PROCESS_DIR}/solr-env.sh" 2>/dev/null || true
fi

local solrctl_path="$SOLRCTL_CMD"
if ! command -v "$SOLRCTL_CMD" &> /dev/null; then
    if [[ -f "/usr/bin/solrctl" ]]; then
        solrctl_path="/usr/bin/solrctl"
    elif [[ -f "/opt/cloudera/parcels/CDH/bin/solrctl" ]]; then
        solrctl_path="/opt/cloudera/parcels/CDH/bin/solrctl"
    elif [[ -n "$PROCESS_DIR" ]] && [[ -f "${PROCESS_DIR}/../../bin/solrctl" ]]; then
        solrctl_path="${PROCESS_DIR}/../../bin/solrctl"
    else
        log_warning "solrctl not found, skipping config backup for config '$config_name'"
        return 1
    fi
fi

local config_backup_dir="${backup_dir}/${config_name}_config"

log_info "Backing up config: $config_name (used by collection: $collection)"
log_verbose "Config backup directory: $config_backup_dir"

if [[ "$DRY_RUN" == true ]]; then
    log_info "[DRY RUN] Would backup config: $config_name"
    log_info "[DRY RUN]   To: $config_backup_dir"
    return 0
fi

if [[ -d "$config_backup_dir/conf" ]]; then
    log_verbose "Config '$config_name' already backed up, skipping..."
    return 0
fi

mkdir -p "$backup_dir" 2>/dev/null || true

if ! klist 2>/dev/null | grep -q "solr/"; then
    kdestroy || true
    local solr_keytab
    solr_keytab=$(get_latest_keytab "$SERVICE_NAME" "solr.keytab")
    kinit_with_keytab "$solr_keytab"
fi

if [[ -d "$config_backup_dir" ]]; then
    rm -rf "$config_backup_dir" 2>/dev/null || true
fi

local error_output
error_output=$(mktemp)
if "$solrctl_path" instancedir --get "$config_name" "$config_backup_dir" 2>"$error_output"; then
    if [[ -d "$config_backup_dir/conf" ]]; then
        log_success "Config '$config_name' backed up: $config_backup_dir"
        rm -f "$error_output" 2>/dev/null || true
        return 0
    else
        log_warning "solrctl succeeded but conf directory not found: $config_backup_dir/conf"
        if [[ "$DEBUG" == true ]] && [[ -s "$error_output" ]]; then
            log_verbose "Debug: solrctl output:"
            cat "$error_output" | while IFS= read -r line; do
                log_verbose "  $line"
            done
        fi
        rm -f "$error_output" 2>/dev/null || true
        return 1
    fi
else
    local exit_code=$?
    log_warning "Failed to backup config '$config_name' (exit code: $exit_code)"
    if [[ -s "$error_output" ]]; then
        log_verbose "Error output from solrctl:"
        cat "$error_output" | while IFS= read -r line; do
            log_verbose "  $line"
        done
    fi
    rm -rf "$config_backup_dir" 2>/dev/null || true
    rm -f "$error_output" 2>/dev/null || true
    return 1
fi
}

save_collection_metadata() {
    # Save collection metadata and generate recreation script.
    #
    # Args:
    #   collection: Name of the collection
    #   backup_dir: Directory to save metadata files
    #   cluster_state_file: Optional path to cached cluster state file
    #
    # Returns:
    #   0 on success, 1 on failure
    #
    # Creates:
    #   - ${collection}_metadata.json: Full collection metadata
    #   - ${collection}_recreate.sh: Script to recreate the collection
local collection="$1"
local backup_dir="$2"
local cluster_state_file="${3:-}"
local metadata_file="${backup_dir}/${collection}_metadata.json"
local recreate_script="${backup_dir}/${collection}_recreate.sh"

log_verbose "Saving collection metadata for: $collection"

if [[ "$DRY_RUN" == true ]]; then
    log_info "[DRY RUN] Would save metadata for collection: $collection"
    return 0
fi

local metadata
local metadata_exit_code
if [[ -n "$cluster_state_file" ]] && [[ -f "$cluster_state_file" ]]; then
    metadata=$(get_collection_metadata "$collection" "$cluster_state_file" 2>&1)
    metadata_exit_code=$?
else
    metadata=$(get_collection_metadata "$collection" 2>&1)
    metadata_exit_code=$?
fi

if [[ $metadata_exit_code -eq 0 ]] && [[ -n "$metadata" ]] && [[ "$metadata" != "null" ]]; then
    if echo "$metadata" | jq '.' > "$metadata_file" 2>/dev/null; then
        log_success "Collection metadata saved: $metadata_file"
        generate_recreate_script "$collection" "$metadata" "$recreate_script"
        return 0
    else
        log_warning "Failed to save metadata JSON to file for collection '$collection'"
        if [[ "$DEBUG" == true ]]; then
            log_verbose "Debug: Metadata content (first 500 chars):"
            echo "$metadata" | head -c 500
        fi
    fi
else
    log_warning "Failed to retrieve metadata for collection '$collection' (exit code: $metadata_exit_code)"
    if [[ "$DEBUG" == true ]] && [[ -n "$metadata" ]]; then
        log_verbose "Debug: get_collection_metadata output:"
        echo "$metadata" | head -20
    fi
fi

return 1
}

generate_recreate_script() {
    # Generate a shell script to recreate a collection with exact settings.
    #
    # Args:
    #   collection: Name of the collection
    #   metadata: JSON metadata from cluster state
    #   script_file: Path to write the recreation script
    #
    # The generated script can be used to recreate the collection with the same
    # settings (shards, replication factor, config, etc.) but without data.
local collection="$1"
local metadata="$2"
local script_file="$3"

log_verbose "Generating recreation script for: $collection"

local num_shards
num_shards=$(echo "$metadata" | jq -r '.shards | length' 2>/dev/null || echo "")
local replication_factor
replication_factor=$(echo "$metadata" | jq -r '.replicationFactor // .nrtReplicas // "2"' 2>/dev/null || echo "2")
local max_shards_per_node
max_shards_per_node=$(echo "$metadata" | jq -r '.maxShardsPerNode // "1"' 2>/dev/null || echo "1")
local config_name
config_name=$(echo "$metadata" | jq -r '.configName // empty' 2>/dev/null || echo "")
local auto_add_replicas
auto_add_replicas=$(echo "$metadata" | jq -r '.autoAddReplicas // "false"' 2>/dev/null || echo "false")
local router_name
router_name=$(echo "$metadata" | jq -r '.router.name // "compositeId"' 2>/dev/null || echo "compositeId")

if [[ -z "$config_name" ]] || [[ "$config_name" == "null" ]]; then
    case "$collection" in
        ranger_audits)
            config_name="ranger_audits"
            ;;
        vertex_index|edge_index|fulltext_index)
            config_name="atlas_configs"
            ;;
        *)
            config_name="${collection}_configs"
            ;;
    esac
fi
    
    # Generate the recreation script
    cat > "$script_file" <<EOF
#!/bin/bash
# Recreation script for Solr collection: $collection
# Generated from cluster state backup
# 
# This script recreates the collection with the exact settings from the backup.
# Usage: ./${collection}_recreate.sh

set -euo pipefail

COLLECTION_NAME="$collection"
CONFIG_NAME="$config_name"
NUM_SHARDS=${num_shards:-3}
REPLICATION_FACTOR=${replication_factor:-2}
MAX_SHARDS_PER_NODE=${max_shards_per_node:-1}
AUTO_ADD_REPLICAS=${auto_add_replicas:-false}
ROUTER_NAME="$router_name"

# Source solr environment
SERVICE_NAME="solr-SOLR_SERVER"
PROCESS_DIR=\$(ls -d /var/run/cloudera-scm-agent/process/*\${SERVICE_NAME} 2>/dev/null | tail -n1)
if [[ -n "\$PROCESS_DIR" ]] && [[ -f "\${PROCESS_DIR}/solr-env.sh" ]]; then
    source "\${PROCESS_DIR}/solr-env.sh" 2>/dev/null || true
fi

# Authenticate with Solr keytab
KEYTAB="\${PROCESS_DIR}/solr.keytab"
PRINCIPAL=\$(klist -kt "\$KEYTAB" | tail -n 1 | awk '{print \$4}')
kinit -kt "\$KEYTAB" "\$PRINCIPAL" || { echo "❌ kinit failed"; exit 1; }

# Build solrctl command
SOLRCTL_CMD="solrctl collection --create \$COLLECTION_NAME"
SOLRCTL_CMD="\$SOLRCTL_CMD -s \$NUM_SHARDS"
SOLRCTL_CMD="\$SOLRCTL_CMD -r \$REPLICATION_FACTOR"
SOLRCTL_CMD="\$SOLRCTL_CMD -c \$CONFIG_NAME"
SOLRCTL_CMD="\$SOLRCTL_CMD -m \$MAX_SHARDS_PER_NODE"

if [[ "\$AUTO_ADD_REPLICAS" == "true" ]]; then
    SOLRCTL_CMD="\$SOLRCTL_CMD -a"
fi

# Execute creation
echo "Creating collection: \$COLLECTION_NAME"
echo "Command: \$SOLRCTL_CMD"
eval "\$SOLRCTL_CMD"

if [[ \$? -eq 0 ]]; then
    echo "✓ Collection '\$COLLECTION_NAME' created successfully"
    echo ""
    echo "Collection settings:"
    echo "  Shards: \$NUM_SHARDS"
    echo "  Replication Factor: \$REPLICATION_FACTOR"
    echo "  Max Shards Per Node: \$MAX_SHARDS_PER_NODE"
    echo "  Config Name: \$CONFIG_NAME"
    echo "  Router: \$ROUTER_NAME"
    echo "  Auto Add Replicas: \$AUTO_ADD_REPLICAS"
else
    echo "✗ Failed to create collection '\$COLLECTION_NAME'"
    exit 1
fi
EOF
    
    chmod +x "$script_file" 2>/dev/null || true
    log_success "Recreation script generated: $script_file"
}

create_empty_collection() {
    # Create an empty collection using saved configuration and metadata.
    #
    # Args:
    #   collection: Name of the collection to create
    #   backup_location: HDFS path to backup location containing configs/metadata
    #
    # Returns:
    #   0 on success, 1 on failure
    #
    # Notes:
    #   - Downloads configs and metadata from HDFS backup
    #   - Prefers recreation script if available, falls back to solrctl command
    #   - Uploads configs to ZooKeeper before creating collection
local collection="$1"
local backup_location="$2"

if [[ -n "$PROCESS_DIR" ]] && [[ -f "${PROCESS_DIR}/solr-env.sh" ]]; then
    source "${PROCESS_DIR}/solr-env.sh" 2>/dev/null || true
fi

local solrctl_path="$SOLRCTL_CMD"
if ! command -v "$SOLRCTL_CMD" &> /dev/null; then
    if [[ -f "/usr/bin/solrctl" ]]; then
        solrctl_path="/usr/bin/solrctl"
    elif [[ -f "/opt/cloudera/parcels/CDH/bin/solrctl" ]]; then
        solrctl_path="/opt/cloudera/parcels/CDH/bin/solrctl"
    elif [[ -n "$PROCESS_DIR" ]] && [[ -f "${PROCESS_DIR}/../../bin/solrctl" ]]; then
        solrctl_path="${PROCESS_DIR}/../../bin/solrctl"
    else
        log_error "solrctl not found, cannot create empty collection"
        return 1
    fi
fi

log_info "Creating empty collection: $collection"

if [[ -n "$PROCESS_DIR" ]] && [[ -f "${PROCESS_DIR}/solr-env.sh" ]]; then
    source "${PROCESS_DIR}/solr-env.sh" 2>/dev/null || true
fi

local config_backup_dir=""
local metadata_file=""

kdestroy || true
local hdfs_keytab
hdfs_keytab=$(get_latest_keytab "hdfs-DATANODE" "hdfs.keytab")
kinit_with_keytab "$hdfs_keytab"

if hdfs dfs -test -d "${backup_location}/configs/${collection}_config" 2>/dev/null; then
    local local_config_dir
    local_config_dir=$(mktemp -d)
    hdfs dfs -get "${backup_location}/configs/${collection}_config" "$local_config_dir/" 2>/dev/null
    if [[ $? -eq 0 ]]; then
        config_backup_dir="${local_config_dir}/${collection}_config"
        log_info "Found saved config for collection: $collection"
    fi
fi

local recreate_script=""
if hdfs dfs -test -f "${backup_location}/configs/${collection}_metadata.json" 2>/dev/null; then
    local local_metadata_file
    local_metadata_file=$(mktemp)
    hdfs dfs -get "${backup_location}/configs/${collection}_metadata.json" "$local_metadata_file" 2>/dev/null
    if [[ $? -eq 0 ]]; then
        metadata_file="$local_metadata_file"
        log_info "Found saved metadata for collection: $collection"
    fi
fi

if hdfs dfs -test -f "${backup_location}/configs/${collection}_recreate.sh" 2>/dev/null; then
    local local_recreate_script
    local_recreate_script=$(mktemp)
    hdfs dfs -get "${backup_location}/configs/${collection}_recreate.sh" "$local_recreate_script" 2>/dev/null
    if [[ $? -eq 0 ]]; then
        chmod +x "$local_recreate_script" 2>/dev/null || true
        recreate_script="$local_recreate_script"
        log_info "Found recreation script for collection: $collection"
    fi
fi

kdestroy || true
local solr_keytab
solr_keytab=$(get_latest_keytab "$SERVICE_NAME" "solr.keytab")
kinit_with_keytab "$solr_keytab"

local num_shards=""
local replication_factor=""
local max_shards_per_node=""
local config_name=""
local auto_add_replicas="false"
local router_name=""

if [[ -n "$metadata_file" ]] && [[ -f "$metadata_file" ]]; then
    num_shards=$(jq -r '.shards | length' "$metadata_file" 2>/dev/null || echo "")
    replication_factor=$(jq -r '.replicationFactor // .nrtReplicas // "2"' "$metadata_file" 2>/dev/null || echo "2")
    max_shards_per_node=$(jq -r '.maxShardsPerNode // "1"' "$metadata_file" 2>/dev/null || echo "1")
    config_name=$(jq -r '.configName // empty' "$metadata_file" 2>/dev/null || echo "")
    auto_add_replicas=$(jq -r '.autoAddReplicas // "false"' "$metadata_file" 2>/dev/null || echo "false")
    router_name=$(jq -r '.router.name // "compositeId"' "$metadata_file" 2>/dev/null || echo "compositeId")
    
    if [[ -z "$config_name" ]] || [[ "$config_name" == "null" ]]; then
        case "$collection" in
            ranger_audits)
                config_name="ranger_audits"
                ;;
            vertex_index|edge_index|fulltext_index)
                config_name="atlas_configs"
                ;;
            *)
                config_name="${collection}_configs"
                ;;
        esac
    fi
    
    log_verbose "Collection settings from cluster state metadata:"
    log_verbose "  Shards: $num_shards"
    log_verbose "  Replication Factor: $replication_factor"
    log_verbose "  Max Shards Per Node: $max_shards_per_node"
    log_verbose "  Config Name: $config_name"
    log_verbose "  Router: $router_name"
    log_verbose "  Auto Add Replicas: $auto_add_replicas"
fi

local config_name_to_use="${config_name:-atlas_configs}"

if [[ -n "$config_backup_dir" ]] && [[ -d "$config_backup_dir" ]]; then
    log_info "Uploading collection configuration..."
    config_name_to_use="${config_name:-${collection}_configs}"
    
    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would upload config from: $config_backup_dir"
        log_info "[DRY RUN]   Config name: $config_name_to_use"
    else
        if "$solrctl_path" instancedir --update "$config_name_to_use" "$config_backup_dir" >/dev/null 2>&1; then
            log_success "Configuration updated: $config_name_to_use"
        elif "$solrctl_path" instancedir --create "$config_name_to_use" "$config_backup_dir" >/dev/null 2>&1; then
            log_success "Configuration created: $config_name_to_use"
        else
            log_warning "Failed to upload config, will try to use existing: ${config_name:-atlas_configs}"
            config_name_to_use="${config_name:-atlas_configs}"
        fi
    fi
else
    log_warning "No saved config found, will use existing config or default"
    config_name_to_use="${config_name:-atlas_configs}"
fi

if [[ "$DRY_RUN" == true ]]; then
    log_info "[DRY RUN] Would create empty collection: $collection"
    if [[ -n "$recreate_script" ]]; then
        log_info "[DRY RUN]   Using recreation script: $recreate_script"
    else
        log_info "[DRY RUN]   Shards: ${num_shards:-3}"
        log_info "[DRY RUN]   Replication Factor: ${replication_factor:-2}"
        log_info "[DRY RUN]   Config: ${config_name_to_use:-atlas_configs}"
    fi
    return 0
fi

if [[ -n "$recreate_script" ]] && [[ -f "$recreate_script" ]]; then
    log_info "Using recreation script to create collection: $collection"
    log_verbose "Script: $recreate_script"
    
    if bash "$recreate_script" >/dev/null 2>&1; then
        log_success "Empty collection '$collection' created successfully using recreation script"
        rm -rf "$local_config_dir" 2>/dev/null || true
        rm -f "$local_metadata_file" 2>/dev/null || true
        rm -f "$recreate_script" 2>/dev/null || true
        return 0
    else
        log_warning "Recreation script failed, falling back to manual creation..."
    fi
fi

if [[ -z "$num_shards" ]] || [[ -z "$replication_factor" ]]; then
    log_warning "Missing collection settings from metadata, using defaults"
    num_shards="${num_shards:-3}"
    replication_factor="${replication_factor:-2}"
fi

local create_cmd="$solrctl_path collection --create $collection"
create_cmd="$create_cmd -s ${num_shards:-3}"
create_cmd="$create_cmd -r ${replication_factor}"
create_cmd="$create_cmd -c ${config_name_to_use:-atlas_configs}"

if [[ -n "$max_shards_per_node" ]] && [[ "$max_shards_per_node" != "null" ]] && [[ "$max_shards_per_node" != "" ]]; then
    create_cmd="$create_cmd -m $max_shards_per_node"
fi

if [[ "$auto_add_replicas" == "true" ]]; then
    create_cmd="$create_cmd -a"
fi

log_verbose "Executing: $create_cmd"
local create_success=false
if eval "$create_cmd" >/dev/null 2>&1; then
    create_success=true
fi

if [[ "$create_success" == true ]]; then
    log_success "Empty collection '$collection' created successfully"
    rm -rf "$local_config_dir" 2>/dev/null || true
    rm -f "$local_metadata_file" 2>/dev/null || true
    rm -f "$recreate_script" 2>/dev/null || true
    return 0
else
    log_error "Failed to create empty collection '$collection'"
    rm -rf "$local_config_dir" 2>/dev/null || true
    rm -f "$local_metadata_file" 2>/dev/null || true
    rm -f "$recreate_script" 2>/dev/null || true
    return 1
fi
}

get_backup_name() {
    # Get the backup name for a collection.
    #
    # Args:
    #   collection: Name of the collection
    #
    # Returns:
    #   Backup name (uses BACKUP_NAME_PATTERN if set, otherwise {collection}_backup)
local collection="$1"

if [[ -n "$BACKUP_NAME_PATTERN" ]]; then
    echo "$BACKUP_NAME_PATTERN" | sed "s/{collection}/$collection/g"
else
    echo "${collection}_backup"
fi
}

prepare_hdfs_backup_location() {
    # Prepare HDFS backup location with optional timestamp.
    #
    # Sets HDFS_BACKUP_LOCATION to the final backup path.
    # Creates directory and sets ownership to solr:solr if not in dry-run mode.
if [[ "$ADD_TIMESTAMP" == true ]]; then
    local timestamp
    timestamp=$(date +"%Y%m%d%H%M%S")
    HDFS_BACKUP_LOCATION="${HDFS_BACKUP_BASE}/${timestamp}"
else
    HDFS_BACKUP_LOCATION="$HDFS_BACKUP_BASE"
fi

log_verbose "Final backup location: $HDFS_BACKUP_LOCATION"

if [[ "$DRY_RUN" == false ]]; then
    log_info "Preparing HDFS backup location: $HDFS_BACKUP_LOCATION"
    kdestroy || true
    
    local hdfs_keytab
    hdfs_keytab=$(get_latest_keytab "hdfs-DATANODE" "hdfs.keytab")
    kinit_with_keytab "$hdfs_keytab"
    
    hdfs dfs -mkdir -p "${HDFS_BACKUP_LOCATION}" >/dev/null 2>&1
    hdfs dfs -chown solr:solr "${HDFS_BACKUP_LOCATION}" >/dev/null 2>&1
    
    log_success "HDFS backup location prepared"
else
    log_info "[DRY RUN] Would prepare HDFS backup location: $HDFS_BACKUP_LOCATION"
fi
}

confirm_operation() {
    # Prompt user for confirmation before executing operation.
    #
    # Args:
    #   operation: Type of operation (backup, delete, restore)
    #   count: Number of collections affected
    #
    # Returns:
    #   0 if confirmed or FORCE=true, exits with 0 if cancelled
if [[ "$FORCE" == true ]]; then
    return 0
fi

if [[ "$DRY_RUN" == true ]]; then
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "DRY RUN MODE: No operations will be executed"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    return 0
fi

local operation="$1"
local count="$2"

echo
log_warning "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_warning "CONFIRMATION REQUIRED"
log_warning "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_warning "Operation: ${operation^^}"
log_warning "Collections: ${count}"

if [[ "$COMMAND" == "backup" ]]; then
    log_warning "Backup location: $HDFS_BACKUP_LOCATION"
elif [[ "$COMMAND" == "restore" ]]; then
    log_warning "Restore from: $HDFS_BACKUP_LOCATION"
fi

log_warning "Solr endpoint: $SOLR_ENDPOINT"
log_warning "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

read -p "Are you sure you want to continue? (yes/no): " -r
echo

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    log_info "Operation cancelled by user"
    exit 0
fi

log_info "Operation confirmed. Proceeding..."
echo
}

print_summary() {
local operation="$1"
echo
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "OPERATION SUMMARY: ${operation^^}"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "Collections found:    $COLLECTIONS_FOUND"
log_info "Collections processed: $COLLECTIONS_PROCESSED"
log_info "Collections failed:   $COLLECTIONS_FAILED"

if [[ "$COMMAND" == "backup" ]]; then
    log_info "Backup location:      $HDFS_BACKUP_LOCATION"
elif [[ "$COMMAND" == "restore" ]]; then
    log_info "Restore from:         $HDFS_BACKUP_LOCATION"
fi

log_info "Solr endpoint:         $SOLR_ENDPOINT"

if [[ $COLLECTIONS_FAILED -gt 0 ]]; then
    echo
    log_warning "Failed collections:"
    for collection in "${FAILED_COLLECTIONS[@]}"; do
        log_warning "  ✗ $collection"
    done
fi

if [[ $COLLECTIONS_PROCESSED -gt 0 && $COLLECTIONS_FAILED -eq 0 ]]; then
    echo
    log_success "✓ All collections processed successfully!"
elif [[ $COLLECTIONS_PROCESSED -gt 0 ]]; then
    echo
    log_warning "⚠ Some collections failed. Review errors above."
fi

log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

################################################################################
# Solr API Functions
################################################################################

list_collections_kerberos() {
    # List all Solr collections using Kerberos authentication.
    #
    # Args:
    #   endpoint: Solr endpoint URL
    #
    # Returns:
    #   Echoes collection names (one per line) to stdout, returns 0 on success, 1 on failure.
local endpoint="$1"
local url="${endpoint}/solr/admin/collections?action=LIST&wt=json"

log_verbose "Fetching collections from: $url"

local response
local start_time
start_time=$(date +%s)

local curl_opts="--location --negotiate --insecure --user :"
if [[ "$DEBUG" == true ]]; then
    curl_opts="--verbose $curl_opts"
    local debug_temp_file
    debug_temp_file=$(mktemp)
    response=$(curl $curl_opts "$url" 2> >(tee "$debug_temp_file" >&2))
    if [[ -s "$debug_temp_file" ]]; then
        echo
        log_info "DEBUG: Curl verbose output:"
        cat "$debug_temp_file" >&2
        echo
    fi
    rm -f "$debug_temp_file" 2>/dev/null || true
else
    curl_opts="--silent $curl_opts"
    response=$(curl $curl_opts "$url" 2>&1)
fi
local curl_exit_code=$?
local end_time
end_time=$(date +%s)
local duration=$((end_time - start_time))

if [[ $curl_exit_code -ne 0 ]]; then
    log_error "Failed to connect to Solr endpoint: $url"
    log_error "Curl error (exit code: $curl_exit_code): $response"
    return 1
fi

log_verbose "API response received (duration: ${duration}s)"

if echo "$response" | jq -e '.error' >/dev/null 2>&1; then
    log_error "Solr API returned an error:"
    echo "$response" | jq '.error' 2>/dev/null || echo "$response"
    return 1
fi

local collections
collections=$(echo "$response" | jq -r '.collections[]?' 2>/dev/null)

if [[ -z "$collections" ]]; then
    log_warning "No collections found in Solr response"
    log_verbose "Full response: $response"
    return 0
fi

local collection_count
collection_count=$(echo "$collections" | wc -l | tr -d ' ')
log_info "Successfully retrieved $collection_count collection(s) from Solr"

echo "$collections"
return 0
}

backup_collection_kerberos() {
    # Backup a Solr collection using Kerberos authentication via Solr API.
    #
    # Args:
    #   endpoint: Solr endpoint URL
    #   collection: Name of the collection to backup
    #   backup_name: Name for the backup
    #   hdfs_location: HDFS path for the backup
    #
    # Returns:
    #   0 on success, 1 on failure
local endpoint="$1"
local collection="$2"
local backup_name="$3"
local hdfs_location="$4"

local url="${endpoint}/solr/admin/collections"

log_verbose "Backing up collection: $collection"
log_verbose "Backup name: $backup_name"
log_verbose "HDFS location: $hdfs_location"
log_verbose "API URL: $url"

if [[ "$DRY_RUN" == true ]]; then
    log_info "[DRY RUN] Would backup collection: $collection"
    log_info "[DRY RUN]   Backup name: $backup_name"
    log_info "[DRY RUN]   HDFS location: $hdfs_location"
    return 0
fi

log_info "Sending backup request to Solr API..."
local response
local start_time
start_time=$(date +%s)

local curl_opts="--location --negotiate --insecure --user :"
curl_opts="$curl_opts --cookie-jar /dev/null --cookie /dev/null"

if [[ "$DEBUG" == true ]]; then
    curl_opts="--verbose $curl_opts"
    local debug_temp_file
    debug_temp_file=$(mktemp)
    response=$(curl $curl_opts \
        -X POST "$url" \
        --data-urlencode "action=BACKUP" \
        --data-urlencode "collection=${collection}" \
        --data-urlencode "name=${backup_name}" \
        --data-urlencode "location=${hdfs_location}" \
        --data-urlencode "wt=json" \
        -w "\n%{http_code}" 2> >(tee "$debug_temp_file" >&2))
    if [[ -s "$debug_temp_file" ]]; then
        cat "$debug_temp_file" >&2
    fi
    rm -f "$debug_temp_file" 2>/dev/null || true
else
    curl_opts="--silent $curl_opts"
    response=$(curl $curl_opts \
        -X POST "$url" \
        --data-urlencode "action=BACKUP" \
        --data-urlencode "collection=${collection}" \
        --data-urlencode "name=${backup_name}" \
        --data-urlencode "location=${hdfs_location}" \
        --data-urlencode "wt=json" \
        -w "\n%{http_code}" 2>&1)
fi
local curl_exit_code=$?
local end_time
end_time=$(date +%s)
local duration=$((end_time - start_time))

if [[ $curl_exit_code -ne 0 ]]; then
    log_error "Failed to backup collection '$collection': curl error (exit code: $curl_exit_code)"
    log_verbose "Curl error: $response"
    return 1
fi

local http_code
http_code=$(echo "$response" | tail -n 1)
local response_body
response_body=$(echo "$response" | sed '$d')

if echo "$response_body" | jq -e '.error' >/dev/null 2>&1; then
    log_error "Solr API returned an error for collection '$collection':"
    echo "$response_body" | jq '.error' 2>/dev/null || echo "$response_body"
    return 1
fi

if [[ "$http_code" -ge 200 && "$http_code" -lt 300 ]]; then
    log_success "Backup request accepted (HTTP $http_code, duration: ${duration}s)"
    log_verbose "Response: $response_body"
    
    if echo "$response_body" | jq -e '.responseHeader.status' >/dev/null 2>&1; then
        local status
        status=$(echo "$response_body" | jq -r '.responseHeader.status' 2>/dev/null)
        log_info "Backup status: $status"
    fi
    
    return 0
else
    log_error "Backup request failed (HTTP $http_code, duration: ${duration}s)"
    log_verbose "Response: $response_body"
    return 1
fi
}

delete_collection_kerberos() {
    # Delete a Solr collection using Kerberos authentication via Solr API.
    #
    # Args:
    #   endpoint: Solr endpoint URL
    #   collection: Name of the collection to delete
    #
    # Returns:
    #   0 on success, 1 on failure
local endpoint="$1"
local collection="$2"
local url="${endpoint}/solr/admin/collections?action=DELETE&name=${collection}"

log_verbose "Deleting collection: $collection"
log_verbose "URL: $url"

if [[ "$DRY_RUN" == true ]]; then
    log_info "[DRY RUN] Would delete collection: $collection"
    return 0
fi

local curl_opts="--location --negotiate --insecure --user :"
curl_opts="$curl_opts --cookie-jar /dev/null --cookie /dev/null"

if [[ "$DEBUG" == true ]]; then
    curl_opts="--verbose $curl_opts"
    local debug_temp_file
    debug_temp_file=$(mktemp)
    local response
    response=$(curl $curl_opts \
        "$url" \
        -w "\n%{http_code}" 2> >(tee "$debug_temp_file" >&2))
    if [[ -s "$debug_temp_file" ]]; then
        cat "$debug_temp_file" >&2
    fi
    rm -f "$debug_temp_file" 2>/dev/null || true
else
    curl_opts="--silent $curl_opts"
    local response
    response=$(curl $curl_opts \
        "$url" \
        -w "\n%{http_code}" 2>&1)
fi
local curl_exit_code=$?

if [[ $curl_exit_code -ne 0 ]]; then
    log_error "Failed to delete collection '$collection': curl error"
    return 1
fi

local http_code
http_code=$(echo "$response" | tail -n 1)
local response_body
response_body=$(echo "$response" | sed '$d')

if echo "$response_body" | jq -e '.error' >/dev/null 2>&1; then
    log_error "Failed to delete collection '$collection'"
    echo "$response_body" | jq '.'
    return 1
fi

if [[ "$http_code" -ge 200 && "$http_code" -lt 300 ]]; then
    log_success "Collection '$collection' deleted successfully (HTTP $http_code)"
    return 0
else
    log_error "Failed to delete collection '$collection' (HTTP $http_code)"
    log_verbose "Response: $response_body"
    return 1
fi
}

restore_collection_kerberos() {
    # Restore a Solr collection using Kerberos authentication via Solr API.
    #
    # Args:
    #   endpoint: Solr endpoint URL
    #   collection: Name of the collection to restore
    #   backup_name: Name of the backup to restore from
    #   hdfs_location: HDFS path to backup location
    #   solr_host: Solr hostname for HDFS URI construction
    #
    # Returns:
    #   0 on success, 1 on failure
    #
    # Note: This function is deprecated in favor of restore_collection_solrctl.
local endpoint="$1"
local collection="$2"
local backup_name="$3"
local hdfs_location="$4"
local solr_host="$5"

local url="${endpoint}/solr/admin/collections"
local hdfs_path="hdfs://${solr_host}:8020${hdfs_location}"

log_verbose "Restoring collection: $collection"
log_verbose "Backup name: $backup_name"
log_verbose "HDFS location: $hdfs_location"
log_verbose "HDFS path (full URI): $hdfs_path"
log_verbose "API URL: $url"

if [[ "$DRY_RUN" == true ]]; then
    log_info "[DRY RUN] Would restore collection: $collection"
    log_info "[DRY RUN]   Backup name: $backup_name"
    log_info "[DRY RUN]   HDFS location: $hdfs_path"
    return 0
fi

log_info "Sending restore request to Solr API..."

if [[ "$DEBUG" == true ]]; then
    echo
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "DEBUG: Curl Command Details"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "URL: $url"
    log_info "Action: RESTORE"
    log_info "Collection: $collection"
    log_info "Backup Name: $backup_name"
    log_info "Location (HDFS URI): $hdfs_path"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    log_info "DEBUG: Curl verbose output (connection details, headers, etc.):"
    echo
fi

local response
local start_time
start_time=$(date +%s)

local curl_opts="--location --negotiate --insecure --user :"
curl_opts="$curl_opts --cookie-jar /dev/null --cookie /dev/null"

if [[ "$DEBUG" == true ]]; then
    curl_opts="--verbose $curl_opts"
    local debug_temp_file
    debug_temp_file=$(mktemp)
    response=$(curl $curl_opts \
        -X POST "$url" \
        --data-urlencode "action=RESTORE" \
        --data-urlencode "collection=${collection}" \
        --data-urlencode "name=${backup_name}" \
        --data-urlencode "location=${hdfs_path}" \
        --data-urlencode "wt=json" \
        -w "\n%{http_code}" 2> >(tee "$debug_temp_file" >&2))
    if [[ -s "$debug_temp_file" ]]; then
        cat "$debug_temp_file" >&2
    fi
    rm -f "$debug_temp_file" 2>/dev/null || true
else
    curl_opts="--silent $curl_opts"
    response=$(curl $curl_opts \
        -X POST "$url" \
        --data-urlencode "action=RESTORE" \
        --data-urlencode "collection=${collection}" \
        --data-urlencode "name=${backup_name}" \
        --data-urlencode "location=${hdfs_path}" \
        --data-urlencode "wt=json" \
        -w "\n%{http_code}" 2>&1)
fi
local curl_exit_code=$?
local end_time
end_time=$(date +%s)
local duration=$((end_time - start_time))

if [[ $curl_exit_code -ne 0 ]]; then
    log_error "Failed to restore collection '$collection': curl error (exit code: $curl_exit_code)"
    log_verbose "Curl error: $response"
    return 1
fi

local http_code
http_code=$(echo "$response" | tail -n 1)
local response_body
response_body=$(echo "$response" | sed '$d')

if echo "$response_body" | grep -q "<html>" || echo "$response_body" | jq -e '.error' >/dev/null 2>&1; then
    log_error "Solr API returned an error for collection '$collection':"
    if echo "$response_body" | grep -q "<html>"; then
        local error_msg
        error_msg=$(echo "$response_body" | grep -oP '(?<=<h2>)[^<]+' | head -1 || echo "HTTP Error")
        log_error "Error: $error_msg"
        
        if [[ "$DEBUG" == true ]]; then
            log_error "Full HTML response:"
            echo "$response_body" | head -20
        fi
    else
        echo "$response_body" | jq '.error' 2>/dev/null || echo "$response_body"
    fi
    
    if [[ "$DEBUG" == true ]]; then
        echo
        log_error "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log_error "DEBUG: Error Details"
        log_error "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log_error "HTTP Status Code: $http_code"
        log_error "Request URL: $url"
        log_error "HDFS Path: $hdfs_path"
        log_error "Backup Name: $backup_name"
        log_error "Collection: $collection"
        log_error "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo
    fi
    
    if [[ "$http_code" == "403" ]]; then
        log_warning "HTTP 403 Forbidden - Possible causes:"
        log_warning "  1. Collection '$collection' may already exist (delete it first)"
        log_warning "  2. Solr keytab may not have RESTORE permissions"
        log_warning "  3. HDFS backup location may not be accessible from Solr"
        log_warning "  4. Backup name pattern may not match actual backup"
        log_warning ""
        log_warning "Try: ./solr_all_in_one.sh list (to check if collection exists)"
        log_warning "Or:  ./solr_all_in_one.sh delete -c $collection (to delete before restore)"
    fi
    
    return 1
fi

if [[ "$http_code" -ge 200 && "$http_code" -lt 300 ]]; then
    log_success "Restore request accepted (HTTP $http_code, duration: ${duration}s)"
    log_verbose "Response: $response_body"
    
    if echo "$response_body" | jq -e '.responseHeader.status' >/dev/null 2>&1; then
        local status
        status=$(echo "$response_body" | jq -r '.responseHeader.status' 2>/dev/null)
        log_info "Restore status: $status"
    fi
    
    return 0
else
    log_error "Restore request failed (HTTP $http_code, duration: ${duration}s)"
    log_verbose "Response: $response_body"
    return 1
fi
}

discover_backup_collections() {
    # Discover collections available in HDFS backup location.
    #
    # Args:
    #   hdfs_location: HDFS path to backup location
    #
    # Returns:
    #   Echoes collection names (one per line) to stdout.
    #   Falls back to default collections if discovery fails.
local hdfs_location="$1"

log_verbose "Discovering collections in backup location: $hdfs_location"

if [[ "$DRY_RUN" == false ]]; then
    kdestroy || true
    local hdfs_keytab
    hdfs_keytab=$(get_latest_keytab "hdfs-DATANODE" "hdfs.keytab")
    kinit_with_keytab "$hdfs_keytab"
    
    local backups
    backups=$(hdfs dfs -ls "${hdfs_location}" 2>/dev/null | grep "^d" | awk '{print $NF}' | xargs -n1 basename | grep "_backup$" | sed 's/_backup$//' | grep -v "^configs$" || true)
    
    if [[ -n "$backups" ]]; then
        echo "$backups"
        return 0
    fi
fi

local default_collections=("vertex_index" "edge_index" "fulltext_index" "ranger_audits")
for collection in "${default_collections[@]}"; do
    echo "$collection"
done
}

verify_hdfs_backup_location() {
    # Verify that HDFS backup location exists and is accessible.
    #
    # Args:
    #   location: HDFS path to verify
    #
    # Returns:
    #   0 if location exists and is accessible, 1 otherwise
local location="$1"

log_info "Verifying HDFS backup location: $location"

if [[ "$DRY_RUN" == true ]]; then
    log_info "[DRY RUN] Would verify HDFS location: $location"
    return 0
fi

kdestroy || true
local hdfs_keytab
hdfs_keytab=$(get_latest_keytab "hdfs-DATANODE" "hdfs.keytab")
kinit_with_keytab "$hdfs_keytab"

if hdfs dfs -test -d "$location" 2>/dev/null; then
    log_success "HDFS backup location exists and is accessible"
    log_info "Backup directory contents:"
    hdfs dfs -ls "$location" 2>/dev/null || log_warning "Could not list backup directory"
    return 0
else
    log_error "HDFS backup location does not exist or is not accessible: $location"
    return 1
fi
}

################################################################################
# Command Functions
################################################################################

cmd_backup() {
    # Execute backup operation for Solr collections.
    #
    # Backs up collections to HDFS using Solr API or solrctl.
    # Optionally saves collection configurations and metadata for recovery.
    # Creates timestamped backup directories by default.
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "BACKUP OPERATION"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

validate_solr_running
get_solr_endpoint
prepare_hdfs_backup_location

# Authenticate with Solr keytab
kdestroy || true
local solr_keytab
solr_keytab=$(get_latest_keytab "$SERVICE_NAME" "solr.keytab")
kinit_with_keytab "$solr_keytab"

# Get list of collections
log_info "Fetching collection list from ${SOLR_ENDPOINT}"
local all_collections
all_collections=$(list_collections_kerberos "$SOLR_ENDPOINT")

if [[ $? -ne 0 ]]; then
    log_error "Failed to retrieve collections list"
    exit 1
fi

# Determine which collections to backup
local collections_to_backup=()

if [[ ${#SPECIFIC_COLLECTIONS[@]} -gt 0 ]]; then
    # Backup only specified collections
    log_info "Filtering for specified collections..."
    for specified in "${SPECIFIC_COLLECTIONS[@]}"; do
        if echo "$all_collections" | grep -q "^${specified}$"; then
            collections_to_backup+=("$specified")
            log_verbose "Collection '$specified' found and will be backed up"
        else
            log_warning "Collection '$specified' not found in Solr, skipping"
        fi
    done
else
    # Backup all collections
    log_info "Processing all collections..."
    while IFS= read -r collection; do
        if [[ -n "$collection" ]]; then
            collections_to_backup+=("$collection")
            log_verbose "Added collection to backup list: $collection"
        fi
    done <<< "$all_collections"
fi

COLLECTIONS_FOUND=${#collections_to_backup[@]}

if [[ $COLLECTIONS_FOUND -eq 0 ]]; then
    log_info "No collections to backup"
    exit 0
fi

log_info "Found $COLLECTIONS_FOUND collection(s) to backup"

# Always show collections list (not just in verbose mode)
log_info "Collections to backup:"
for idx in "${!collections_to_backup[@]}"; do
    local collection="${collections_to_backup[$idx]}"
    local backup_name
    backup_name=$(get_backup_name "$collection")
    log_info "  [$((idx + 1))/$COLLECTIONS_FOUND] $collection (backup name: $backup_name)"
done

confirm_operation "backup" "$COLLECTIONS_FOUND"

    # Prepare local backup directory for configs if needed
    local local_backup_dir=""
    local backed_up_configs=()  # Track which configs we've already backed up
    local cluster_state_file=""  # Cache cluster state for all collections
    
    if [[ "$SAVE_CONFIGS" == true ]]; then
        local_backup_dir="/tmp/solr_backup_configs_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$local_backup_dir"
        log_info "Local config backup directory: $local_backup_dir"
        
        # Get cluster state once for all collections (more efficient)
        log_info "Fetching cluster state for metadata extraction..."
        cluster_state_file=$(mktemp)
        if get_cluster_state_once "$cluster_state_file"; then
            log_success "Cluster state retrieved successfully"
            # Save cluster state to backup directory for recovery purposes
            if [[ -f "$cluster_state_file" ]] && [[ -d "$local_backup_dir" ]]; then
                cp "$cluster_state_file" "${local_backup_dir}/cluster-state.json" 2>/dev/null || true
                log_success "Cluster state saved to backup: cluster-state.json"
            fi
        else
            log_warning "Failed to retrieve cluster state, metadata saving may fail"
            cluster_state_file=""
        fi
    fi

# Backup collections
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "Starting backup process for $COLLECTIONS_FOUND collection(s)..."
if [[ "$SAVE_CONFIGS" == true ]]; then
    log_info "Collection configs will be saved for recovery"
fi
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

local total_collections=${#collections_to_backup[@]}
log_info "Total collections in array: $total_collections"

for idx in "${!collections_to_backup[@]}"; do
    log_verbose "Loop iteration: idx=$idx, processing collection ${collections_to_backup[$idx]}"
    local collection="${collections_to_backup[$idx]}"
    local backup_name
    backup_name=$(get_backup_name "$collection")
    
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "[$((idx + 1))/$COLLECTIONS_FOUND] Processing collection: $collection"
    log_info "Backup name: $backup_name"
    log_info "HDFS location: $HDFS_BACKUP_LOCATION"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Use explicit error handling to prevent early exit
    if backup_collection_kerberos "$SOLR_ENDPOINT" "$collection" "$backup_name" "$HDFS_BACKUP_LOCATION"; then
        COLLECTIONS_PROCESSED=$((COLLECTIONS_PROCESSED + 1))
        log_success "✓ Collection '$collection' backup completed successfully"
        
        # Save collection configs and metadata if requested
        if [[ "$SAVE_CONFIGS" == true ]] && [[ -n "$local_backup_dir" ]]; then
            echo
            log_info "Saving collection configuration and metadata..."
            # Use explicit error handling to prevent early exit
            # Pass cluster_state_file if available (cached)
            if [[ -n "$cluster_state_file" ]] && [[ -f "$cluster_state_file" ]]; then
                if ! save_collection_metadata "$collection" "$local_backup_dir" "$cluster_state_file"; then
                    log_warning "Failed to save metadata for '$collection', continuing..."
                fi
            else
                if ! save_collection_metadata "$collection" "$local_backup_dir"; then
                    log_warning "Failed to save metadata for '$collection', continuing..."
                fi
            fi
            
            # Get config name to check if we've already backed it up
            local config_name_to_backup=""
            local metadata
            if [[ -n "$cluster_state_file" ]] && [[ -f "$cluster_state_file" ]]; then
                metadata=$(get_collection_metadata "$collection" "$cluster_state_file" 2>/dev/null)
            else
                metadata=$(get_collection_metadata "$collection" 2>/dev/null)
            fi
            if [[ $? -eq 0 ]] && [[ -n "$metadata" ]]; then
                config_name_to_backup=$(echo "$metadata" | jq -r '.configName // empty' 2>/dev/null || echo "")
            fi
            
            # Apply config name mapping if needed
            if [[ -z "$config_name_to_backup" ]] || [[ "$config_name_to_backup" == "null" ]]; then
                case "$collection" in
                    ranger_audits)
                        config_name_to_backup="ranger_audits"
                        ;;
                    vertex_index|edge_index|fulltext_index)
                        config_name_to_backup="atlas_configs"
                        ;;
                    *)
                        config_name_to_backup="${collection}_configs"
                        ;;
                esac
            fi
            
            # Only backup config if we haven't backed it up yet
            local already_backed_up=false
            for backed_config in "${backed_up_configs[@]}"; do
                if [[ "$backed_config" == "$config_name_to_backup" ]]; then
                    already_backed_up=true
                    log_verbose "Config '$config_name_to_backup' already backed up, skipping..."
                    break
                fi
            done
            
            if [[ "$already_backed_up" == false ]]; then
                if backup_collection_config "$collection" "$local_backup_dir" "$config_name_to_backup"; then
                    backed_up_configs+=("$config_name_to_backup")
                else
                    log_warning "Failed to backup config '$config_name_to_backup' for '$collection', continuing..."
                fi
            fi
            echo
        fi
    else
        COLLECTIONS_FAILED=$((COLLECTIONS_FAILED + 1))
        FAILED_COLLECTIONS+=("$collection")
        log_error "✗ Collection '$collection' backup failed"
    fi
    
    log_verbose "Progress: $COLLECTIONS_PROCESSED processed, $COLLECTIONS_FAILED failed out of $COLLECTIONS_FOUND total"
    echo
done

    # Copy configs to HDFS if saved
    if [[ "$SAVE_CONFIGS" == true ]] && [[ -n "$local_backup_dir" ]] && [[ -d "$local_backup_dir" ]]; then
        log_info "Copying collection configs to HDFS backup location..."
        kdestroy || true
        local hdfs_keytab
        hdfs_keytab=$(get_latest_keytab "hdfs-DATANODE" "hdfs.keytab")
        kinit_with_keytab "$hdfs_keytab"
        
        if hdfs dfs -put "$local_backup_dir" "${HDFS_BACKUP_LOCATION}/configs" 2>/dev/null; then
            log_success "Collection configs saved to HDFS: ${HDFS_BACKUP_LOCATION}/configs"
        else
            log_warning "Failed to copy configs to HDFS, but local backup exists: $local_backup_dir"
        fi
        
        log_info "Local config backup preserved at: $local_backup_dir"
    fi
    
    # Clean up cluster state file if we created it
    if [[ -n "$cluster_state_file" ]] && [[ -f "$cluster_state_file" ]]; then
        rm -f "$cluster_state_file" 2>/dev/null || true
    fi

log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "Backup process completed. Processed: $COLLECTIONS_PROCESSED/$COLLECTIONS_FOUND"
if [[ $COLLECTIONS_FAILED -gt 0 ]]; then
    log_warning "Failed: $COLLECTIONS_FAILED/$COLLECTIONS_FOUND"
fi
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Verify backup
if [[ "$DRY_RUN" == false ]]; then
    if [[ $COLLECTIONS_FAILED -eq 0 ]]; then
        log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log_info "Verifying backup location..."
        verify_hdfs_backup_location "$HDFS_BACKUP_LOCATION"
    else
        log_warning "Skipping backup verification due to failures"
    fi
fi

echo
print_summary "backup"
}

cmd_delete() {
log_info "Starting delete operation..."

validate_solr_running
get_solr_endpoint

# Authenticate with Solr keytab
kdestroy || true
local solr_keytab
solr_keytab=$(get_latest_keytab "$SERVICE_NAME" "solr.keytab")
kinit_with_keytab "$solr_keytab"

# Get list of collections
log_info "Fetching collection list from ${SOLR_ENDPOINT}"
local all_collections
all_collections=$(list_collections_kerberos "$SOLR_ENDPOINT")
local list_exit_code=$?

if [[ $list_exit_code -ne 0 ]]; then
    log_error "Failed to retrieve collections list"
    exit 1
fi

if [[ -z "$all_collections" ]]; then
    log_warning "No collections found in Solr"
    exit 0
fi

log_verbose "Raw collections list:"
log_verbose "$all_collections"

# Determine which collections to delete
local collections_to_delete=()

if [[ ${#SPECIFIC_COLLECTIONS[@]} -gt 0 ]]; then
    # Delete only specified collections
    log_info "Filtering for specified collections..."
    for specified in "${SPECIFIC_COLLECTIONS[@]}"; do
        if echo "$all_collections" | grep -q "^${specified}$"; then
            collections_to_delete+=("$specified")
            log_verbose "Collection '$specified' found and will be deleted"
        else
            log_warning "Collection '$specified' not found in Solr, skipping"
        fi
    done
else
    # Delete all collections
    log_info "Processing all collections..."
    while IFS= read -r collection; do
        if [[ -n "$collection" ]]; then
            collections_to_delete+=("$collection")
            log_verbose "Added collection to delete list: $collection"
        fi
    done <<< "$all_collections"
fi

COLLECTIONS_FOUND=${#collections_to_delete[@]}

if [[ $COLLECTIONS_FOUND -eq 0 ]]; then
    log_info "No collections to delete"
    exit 0
fi

log_info "Found $COLLECTIONS_FOUND collection(s) to delete"

# Always show collections list (not just in verbose mode)
log_info "Collections to delete:"
for idx in "${!collections_to_delete[@]}"; do
    local collection="${collections_to_delete[$idx]}"
    log_info "  [$((idx + 1))/$COLLECTIONS_FOUND] $collection"
done

confirm_operation "delete" "$COLLECTIONS_FOUND"

# Delete collections
log_info "Starting deletion process..."
echo

log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "Starting deletion process for $COLLECTIONS_FOUND collection(s)..."
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

local total_collections=${#collections_to_delete[@]}
log_info "Total collections in array: $total_collections"

for idx in "${!collections_to_delete[@]}"; do
    local collection="${collections_to_delete[$idx]}"
    
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "[$((idx + 1))/$COLLECTIONS_FOUND] Processing collection: $collection"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Use explicit error handling to prevent early exit
    if delete_collection_kerberos "$SOLR_ENDPOINT" "$collection"; then
        COLLECTIONS_PROCESSED=$((COLLECTIONS_PROCESSED + 1))
        log_success "✓ Collection '$collection' deleted successfully"
    else
        COLLECTIONS_FAILED=$((COLLECTIONS_FAILED + 1))
        FAILED_COLLECTIONS+=("$collection")
        log_error "✗ Collection '$collection' deletion failed"
    fi
    
    log_verbose "Progress: $COLLECTIONS_PROCESSED processed, $COLLECTIONS_FAILED failed out of $COLLECTIONS_FOUND total"
    echo
done

log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "Deletion process completed. Processed: $COLLECTIONS_PROCESSED/$COLLECTIONS_FOUND"
if [[ $COLLECTIONS_FAILED -gt 0 ]]; then
    log_warning "Failed: $COLLECTIONS_FAILED/$COLLECTIONS_FOUND"
fi
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

print_summary "delete"
}

cmd_restore() {
log_info "Starting restore operation..."

if [[ -z "$HDFS_BACKUP_LOCATION" ]]; then
    log_error "HDFS backup location is required for restore operation"
    log_error "Use -b or --backup-location to specify the backup path"
    exit 1
fi

validate_solr_running
get_solr_endpoint
verify_hdfs_backup_location "$HDFS_BACKUP_LOCATION"

# solrctl uses Kerberos authentication, so authenticate with Solr keytab
log_info "Using solrctl for restore (Kerberos authentication required)"
log_verbose "Destroying any existing Kerberos tickets..."
kdestroy || true
# Small delay to ensure ticket destruction completes
sleep 1

local solr_keytab
solr_keytab=$(get_latest_keytab "$SERVICE_NAME" "solr.keytab")
kinit_with_keytab "$solr_keytab"

# Verify we have the correct ticket
log_verbose "Verifying Solr Kerberos ticket..."
if klist 2>/dev/null | grep -q "solr/"; then
    log_verbose "Solr ticket verified"
else
    log_warning "Warning: Solr ticket verification failed, but continuing..."
fi


# Discover collections in backup
local backup_collections
backup_collections=$(discover_backup_collections "$HDFS_BACKUP_LOCATION")

# Determine which collections to restore
local collections_to_restore=()

if [[ "$RESTORE_ALL" == true ]]; then
    # Restore all collections found in backup
    while IFS= read -r collection; do
        if [[ -n "$collection" ]]; then
            collections_to_restore+=("$collection")
        fi
    done <<< "$backup_collections"
elif [[ ${#SPECIFIC_COLLECTIONS[@]} -gt 0 ]]; then
    # Restore only specified collections
    for specified in "${SPECIFIC_COLLECTIONS[@]}"; do
        if echo "$backup_collections" | grep -q "^${specified}$"; then
            collections_to_restore+=("$specified")
        else
            log_warning "Collection '$specified' not found in backup, skipping"
        fi
    done
else
    log_error "Either specify collections with -c or use -a to restore all"
    exit 1
fi

COLLECTIONS_FOUND=${#collections_to_restore[@]}

if [[ $COLLECTIONS_FOUND -eq 0 ]]; then
    log_info "No collections to restore"
    exit 0
fi

log_info "Found $COLLECTIONS_FOUND collection(s) to restore"

if [[ "$VERBOSE" == true ]]; then
    log_info "Collections:"
    for collection in "${collections_to_restore[@]}"; do
        local backup_name
        backup_name=$(get_backup_name "$collection")
        echo "  - $collection (backup name: $backup_name)"
    done
fi

confirm_operation "restore" "$COLLECTIONS_FOUND"

# Restore collections
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "Starting restore process for $COLLECTIONS_FOUND collection(s)..."
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

local total_collections=${#collections_to_restore[@]}
log_info "Total collections in array: $total_collections"

# Set up file descriptor 3 to duplicate stderr for log output
exec 3>&2

for idx in "${!collections_to_restore[@]}"; do
    local collection="${collections_to_restore[$idx]}"
    local backup_name
    backup_name=$(get_backup_name "$collection")
    
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "[$((idx + 1))/$COLLECTIONS_FOUND] Processing collection: $collection"
    log_info "Backup name: $backup_name"
    log_info "HDFS location: $HDFS_BACKUP_LOCATION"
    log_info "HDFS URI: hdfs://${SOLR_HOST}:8020${HDFS_BACKUP_LOCATION}"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check if we should create empty collection instead of restoring data
    if [[ "$CREATE_EMPTY_COLLECTIONS" == true ]]; then
        log_info "Creating empty collection with saved configuration..."
        if create_empty_collection "$collection" "$HDFS_BACKUP_LOCATION"; then
            COLLECTIONS_PROCESSED=$((COLLECTIONS_PROCESSED + 1))
            log_success "✓ Empty collection '$collection' created successfully"
        else
            COLLECTIONS_FAILED=$((COLLECTIONS_FAILED + 1))
            FAILED_COLLECTIONS+=("$collection")
            log_error "✗ Failed to create empty collection '$collection'"
        fi
    else
        # Use solrctl for restore (uses Kerberos authentication)
        log_info "Restoring collection using solrctl..."
        local request_id
        local restore_exit_code
        
        # Call restore function - capture stdout (request_id) while stderr (logs) goes to terminal
        # Use explicit error handling to prevent loop from exiting on failure
        request_id=$(restore_collection_solrctl "$collection" "$backup_name" "$HDFS_BACKUP_LOCATION" 2>&3)
        restore_exit_code=$?
        
        # Validate request_id format
        if [[ -z "$request_id" ]] || [[ ! "$request_id" =~ ^restore_ ]]; then
            # If extraction failed, generate one based on collection name
            request_id="restore_${collection}_$(date +%s)"
            log_warning "Could not extract request ID from solrctl output, using generated ID: $request_id"
        fi
        
        if [[ $restore_exit_code -eq 0 ]]; then
            # Check if this was a "collection exists" case (non-fatal)
            if echo "$request_id" | grep -q "restore_"; then
                log_success "✓ Restore request submitted for '$collection' (Request ID: $request_id)"
                
                # Store request ID for status monitoring
                RESTORE_REQUEST_IDS+=("$request_id")
                RESTORE_COLLECTION_MAP["$request_id"]="$collection"
                
                # Wait a moment and check initial status
                sleep 2
                log_info "Checking restore status..."
                # Don't fail the loop if status check fails
                check_restore_status "$request_id" >/dev/null 2>&1 || true
            else
                # Collection already exists or other non-fatal case
                log_info "✓ Collection '$collection' already exists or restore not needed"
            fi
            
            COLLECTIONS_PROCESSED=$((COLLECTIONS_PROCESSED + 1))
        else
            COLLECTIONS_FAILED=$((COLLECTIONS_FAILED + 1))
            FAILED_COLLECTIONS+=("$collection")
            log_error "✗ Failed to submit restore request for '$collection'"
        fi
    fi
    
    log_verbose "Progress: $COLLECTIONS_PROCESSED processed, $COLLECTIONS_FAILED failed out of $COLLECTIONS_FOUND total"
    echo
done

# Close file descriptor 3
exec 3>&-

log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "Restore process completed. Processed: $COLLECTIONS_PROCESSED/$COLLECTIONS_FOUND"
if [[ $COLLECTIONS_FAILED -gt 0 ]]; then
    log_warning "Failed: $COLLECTIONS_FAILED/$COLLECTIONS_FOUND"
fi
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Monitor restore progress if we have request IDs
if [[ ${#RESTORE_REQUEST_IDS[@]} -gt 0 ]]; then
    echo
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Monitoring restore progress..."
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Monitoring ${#RESTORE_REQUEST_IDS[@]} restore request(s)"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    
    # Track completion status for each request
    declare -A restore_status_map
    for request_id in "${RESTORE_REQUEST_IDS[@]}"; do
        restore_status_map["$request_id"]="running"
        log_verbose "Tracking request: $request_id (collection: ${RESTORE_COLLECTION_MAP[$request_id]})"
    done
    
    local all_completed=false
    local check_count=0
    local max_checks=120  # Maximum 20 minutes (120 * 10 seconds)
    
    while [[ "$all_completed" == false ]] && [[ $check_count -lt $max_checks ]]; do
        all_completed=true
        check_count=$((check_count + 1))
        
        # Always show status (clear previous output for better readability)
        if [[ $check_count -gt 1 ]]; then
            # Move cursor up to overwrite previous status (if supported)
            echo -ne "\033[$((${#RESTORE_REQUEST_IDS[@]} + 3))A" 2>/dev/null || true
        fi
        
        log_info "=== Restore Status Check #$check_count at $(date '+%H:%M:%S') ==="
        echo
        
        # Ensure we have request IDs to monitor
        if [[ ${#RESTORE_REQUEST_IDS[@]} -eq 0 ]]; then
            log_warning "No restore request IDs found to monitor"
            break
        fi
        
        for request_id in "${RESTORE_REQUEST_IDS[@]}"; do
            local collection_name="${RESTORE_COLLECTION_MAP[$request_id]}"
            
            # Initialize status if not set
            if [[ -z "${restore_status_map[$request_id]:-}" ]]; then
                restore_status_map["$request_id"]="running"
            fi
            
            local current_status="${restore_status_map[$request_id]}"
            
            # Skip if already completed or failed (but show status)
            if [[ "$current_status" == "completed" ]] || [[ "$current_status" == "failed" ]]; then
                if [[ "$current_status" == "completed" ]]; then
                    log_success "  ✓ [$collection_name] - Completed"
                else
                    log_error "  ✗ [$collection_name] - Failed"
                fi
                continue
            fi
            
            # Show we're checking this collection (before potentially slow status check)
            echo -n "  Checking [$collection_name]... " >&2
            
            # Check status (silent mode to avoid duplicate log messages)
            # This will also store the detailed status JSON in RESTORE_STATUS_DETAILS
            local status_exit_code=2  # Default to "running"
            
            # Call status check - capture exit code properly
            # Use explicit error handling to prevent script from exiting
            # Temporarily disable exit on error for this check
            set +e
            
            # Always capture both stdout and stderr to a temp file for debugging
            local status_check_output
            status_check_output=$(mktemp)
            
            if [[ "$DEBUG" == true ]]; then
                # In debug mode, don't suppress output so we can see what's happening
                check_restore_status "$request_id" "false" 2>&1 | tee "$status_check_output"
                status_exit_code=${PIPESTATUS[0]}
            else
                # In normal mode, suppress output but still capture exit code
                check_restore_status "$request_id" "true" >"$status_check_output" 2>&1
                status_exit_code=$?
            fi
            
            # If status check failed or returned unexpected result, show debug info
            if [[ "$DEBUG" == true ]] && [[ -f "$status_check_output" ]]; then
                if [[ $status_exit_code -ne 0 ]] && [[ $status_exit_code -ne 2 ]]; then
                    log_verbose "Status check output for $request_id: $(cat "$status_check_output")"
                fi
            fi
            
            # Clean up temp file
            rm -f "$status_check_output" 2>/dev/null || true
            
            set -e
            
            # Clear the "Checking..." line and show final status
            echo -ne "\r\033[K" >&2  # Clear line
            
            # Update status based on result and show output
            if [[ $status_exit_code -eq 0 ]]; then
                # Completed successfully
                restore_status_map["$request_id"]="completed"
                log_success "  ✓ [$collection_name] - Completed"
                
                # Fetch and store the latest detailed status for final verification
                if [[ -n "$PROCESS_DIR" ]] && [[ -f "${PROCESS_DIR}/solr-env.sh" ]]; then
                    source "${PROCESS_DIR}/solr-env.sh" 2>/dev/null || true
                fi
                local solrctl_path="$SOLRCTL_CMD"
                if ! command -v "$SOLRCTL_CMD" &> /dev/null; then
                    if [[ -f "/usr/bin/solrctl" ]]; then
                        solrctl_path="/usr/bin/solrctl"
                    elif [[ -f "/opt/cloudera/parcels/CDH/bin/solrctl" ]]; then
                        solrctl_path="/opt/cloudera/parcels/CDH/bin/solrctl"
                    elif [[ -n "$PROCESS_DIR" ]] && [[ -f "${PROCESS_DIR}/../../bin/solrctl" ]]; then
                        solrctl_path="${PROCESS_DIR}/../../bin/solrctl"
                    fi
                fi
                if [[ -n "$solrctl_path" ]]; then
                    local latest_status
                    latest_status=$("$solrctl_path" collection --request-status "$request_id" 2>&1 | grep -oP '\{.*\}' | head -1 || echo "")
                    if [[ -n "$latest_status" ]]; then
                        RESTORE_STATUS_DETAILS["$request_id"]="$latest_status"
                    fi
                fi
            elif [[ $status_exit_code -eq 2 ]]; then
                # Still running
                all_completed=false
                restore_status_map["$request_id"]="running"
                log_info "  ⏳ [$collection_name] - In progress..."
            else
                # Status check failed - assume still running (might be transient error)
                all_completed=false
                restore_status_map["$request_id"]="running"
                log_warning "  ⚠ [$collection_name] - Status check failed, assuming still running..."
            fi
        done
        
        if [[ "$all_completed" == false ]]; then
            echo
            log_info "Waiting 10 seconds before next check..."
            sleep 10
        fi
    done
    
    echo
    echo
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [[ "$all_completed" == true ]]; then
        log_success "✓ All restores completed successfully!"
        
        # Perform detailed verification of all completed restores
        echo
        log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log_info "Final Restore Verification"
        log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo
        
        local completed_count=0
        local failed_count=0
        local verified_count=0
        
        for request_id in "${RESTORE_REQUEST_IDS[@]}"; do
            local collection_name="${RESTORE_COLLECTION_MAP[$request_id]}"
            local final_status="${restore_status_map[$request_id]}"
            # Check if status details exist (handle unbound variable)
            local status_json=""
            if [[ -n "${RESTORE_STATUS_DETAILS[$request_id]:-}" ]]; then
                status_json="${RESTORE_STATUS_DETAILS[$request_id]}"
            fi
            
            if [[ "$final_status" == "completed" ]]; then
                completed_count=$((completed_count + 1))
                
                # Verify detailed status
                if [[ -n "$status_json" ]] && command -v jq &> /dev/null; then
                    local state
                    local msg
                    local response_status
                    
                    state=$(echo "$status_json" | jq -r '.status.state // "unknown"' 2>/dev/null || echo "unknown")
                    msg=$(echo "$status_json" | jq -r '.status.msg // ""' 2>/dev/null || echo "")
                    response_status=$(echo "$status_json" | jq -r '.responseHeader.status // "unknown"' 2>/dev/null || echo "unknown")
                    
                    # Count successful node responses
                    local success_count=0
                    local total_responses=0
                    
                    if echo "$status_json" | jq -e '.success' >/dev/null 2>&1; then
                        # Count nodes with STATUS="completed" in their responses
                        success_count=$(echo "$status_json" | jq '[.success | to_entries[] | select(.value.STATUS == "completed")] | length' 2>/dev/null || echo "0")
                        total_responses=$(echo "$status_json" | jq '[.success | to_entries[]] | length' 2>/dev/null || echo "0")
                    fi
                    
                    if [[ "$state" == "completed" ]] && [[ "$response_status" == "0" ]]; then
                        verified_count=$((verified_count + 1))
                        log_success "  ✓ $collection_name - Verified successfully"
                        log_info "     Status: $state"
                        if [[ -n "$msg" ]]; then
                            log_info "     Message: $msg"
                        fi
                        if [[ $success_count -gt 0 ]]; then
                            log_info "     Nodes completed: $success_count/$total_responses"
                        fi
                    else
                        log_warning "  ⚠ $collection_name - Completed but verification shows: state=$state, responseStatus=$response_status"
                    fi
                else
                    # Fallback if JSON parsing not available
                    log_success "  ✓ $collection_name - Restored successfully (detailed verification unavailable)"
                fi
            elif [[ "$final_status" == "failed" ]]; then
                failed_count=$((failed_count + 1))
                log_error "  ✗ $collection_name - Restore failed"
                
                # Show error details if available
                if [[ -n "$status_json" ]] && command -v jq &> /dev/null; then
                    local msg
                    msg=$(echo "$status_json" | jq -r '.status.msg // ""' 2>/dev/null || echo "")
                    if [[ -n "$msg" ]]; then
                        log_error "     Error: $msg"
                    fi
                fi
            else
                log_warning "  ⚠ $collection_name - Status unknown"
            fi
        done
        
        echo
        log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log_info "Restore Verification Summary:"
        log_info "  Total collections: ${#RESTORE_REQUEST_IDS[@]}"
        log_info "  Completed: $completed_count"
        log_info "  Verified: $verified_count"
        if [[ $failed_count -gt 0 ]]; then
            log_warning "  Failed: $failed_count"
        fi
        log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        # Final status message
        if [[ $verified_count -eq ${#RESTORE_REQUEST_IDS[@]} ]] && [[ $failed_count -eq 0 ]]; then
            echo
            log_success "✓ All restores verified successfully! All collections have been restored."
        elif [[ $completed_count -eq ${#RESTORE_REQUEST_IDS[@]} ]]; then
            echo
            log_success "✓ All restores completed. Verification: $verified_count/$completed_count verified."
        else
            echo
            log_warning "⚠ Some restores may need attention. Completed: $completed_count/${#RESTORE_REQUEST_IDS[@]}, Verified: $verified_count"
        fi
    elif [[ $check_count -ge $max_checks ]]; then
        log_warning "⚠ Monitoring timeout reached after $((max_checks * 10)) seconds."
        log_warning "Some restores may still be in progress."
        echo
        log_info "You can check status manually using:"
        for request_id in "${RESTORE_REQUEST_IDS[@]}"; do
            local collection_name="${RESTORE_COLLECTION_MAP[$request_id]}"
            local final_status="${restore_status_map[$request_id]}"
            if [[ "$final_status" != "completed" ]]; then
                log_info "  solrctl collection --request-status $request_id  # $collection_name"
            fi
        done
    fi
    
    echo
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
fi

print_summary "restore"
}

cmd_list() {
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "LIST COLLECTIONS"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

validate_solr_running
get_solr_endpoint

# Authenticate with Solr keytab
kdestroy || true
local solr_keytab
solr_keytab=$(get_latest_keytab "$SERVICE_NAME" "solr.keytab")
kinit_with_keytab "$solr_keytab"

# Get list of collections
log_info "Fetching collection list from ${SOLR_ENDPOINT}"
local all_collections
all_collections=$(list_collections_kerberos "$SOLR_ENDPOINT")
local list_exit_code=$?

if [[ $list_exit_code -ne 0 ]]; then
    log_error "Failed to retrieve collections list"
    exit 1
fi

if [[ -z "$all_collections" ]]; then
    log_warning "No collections found in Solr"
    echo
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "SUMMARY"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Collections found: 0"
    log_info "Solr endpoint:     $SOLR_ENDPOINT"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 0
fi

# Count collections
local collection_count
collection_count=$(echo "$all_collections" | wc -l | tr -d ' ')

echo
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "SOLR COLLECTIONS"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "Solr endpoint: $SOLR_ENDPOINT"
log_info "Total collections: $collection_count"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# Display collections
local idx=0
while IFS= read -r collection; do
    if [[ -n "$collection" ]]; then
        idx=$((idx + 1))
        if [[ "$VERBOSE" == true ]]; then
            log_info "[$idx] $collection"
        else
            echo "  [$idx] $collection"
        fi
    fi
done <<< "$all_collections"

echo
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "SUMMARY"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "Collections found: $collection_count"
log_info "Solr endpoint:     $SOLR_ENDPOINT"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

################################################################################
# Main Functions
################################################################################

parse_arguments() {
    # Parse command-line arguments and set global variables.
    #
    # Args:
    #   "$@": All command-line arguments
    #
    # Sets global variables based on parsed options and validates input.
if [[ $# -eq 0 ]]; then
    log_error "No command specified"
    show_help
    exit 1
fi

COMMAND="$1"
shift

case "$COMMAND" in
    backup|delete|restore|list)
        ;;
    -h|--help|help)
        show_help
        exit 0
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        log_error "Valid commands are: backup, delete, restore, list"
        show_help
        exit 1
        ;;
esac

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -c|--collection)
            if [[ -z "${2:-}" ]]; then
                log_error "Option -c/--collection requires a collection name"
                exit 1
            fi
            SPECIFIC_COLLECTIONS+=("$2")
            shift 2
            ;;
        -t|--timestamp)
            ADD_TIMESTAMP=true
            shift
            ;;
        -n|--name)
            if [[ -z "${2:-}" ]]; then
                log_error "Option -n/--name requires a backup name pattern"
                exit 1
            fi
            BACKUP_NAME_PATTERN="$2"
            shift 2
            ;;
        --save-configs)
            SAVE_CONFIGS=true
            shift
            ;;
        -a|--all)
            RESTORE_ALL=true
            shift
            ;;
        --create-empty)
            CREATE_EMPTY_COLLECTIONS=true
            shift
            ;;
        -b|--backup-base|--backup-location)
            if [[ -z "${2:-}" ]]; then
                log_error "Option -b requires a path"
                exit 1
            fi
            if [[ "$COMMAND" == "restore" ]]; then
                HDFS_BACKUP_LOCATION="$2"
            else
                HDFS_BACKUP_BASE="$2"
            fi
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --debug)
            DEBUG=true
            VERBOSE=true  # Debug mode also enables verbose
            shift
            ;;
        -l|--log)
            if [[ -z "${2:-}" ]]; then
                log_error "Option -l/--log requires a file path"
                exit 1
            fi
            LOG_FILE="$2"
            shift 2
            ;;
        --host)
            if [[ -z "${2:-}" ]]; then
                log_error "Option --host requires a hostname"
                exit 1
            fi
            SOLR_HOST="$2"
            shift 2
            ;;
        -*)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
        *)
            log_error "Unexpected argument: $1"
            show_help
            exit 1
            ;;
    esac
done
}

main() {
    # Main entry point for the script.
    #
    # Validates prerequisites, parses arguments, and executes the requested command.
    # Handles error reporting and exit codes.
show_banner

parse_arguments "$@"

validate_prerequisites

if [[ -n "$LOG_FILE" ]]; then
    log_info "Logging to: $LOG_FILE"
    echo "=== Solr All-in-One Management Started: $(date) ===" >> "$LOG_FILE"
    echo "Script: ${SCRIPT_NAME} v${SCRIPT_VERSION}" >> "$LOG_FILE"
    echo "Command: $COMMAND" >> "$LOG_FILE"
    echo "Arguments: $*" >> "$LOG_FILE"
    echo "User: $(whoami)" >> "$LOG_FILE"
    echo "Hostname: $(hostname -f 2>/dev/null || hostname)" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
fi

case "$COMMAND" in
    backup)
        cmd_backup
        ;;
    delete)
        cmd_delete
        ;;
    restore)
        cmd_restore
        ;;
    list)
        cmd_list
        ;;
esac

if [[ -n "$LOG_FILE" ]]; then
    echo "=== Solr All-in-One Management Completed: $(date) ===" >> "$LOG_FILE"
fi

if [[ $COLLECTIONS_FAILED -gt 0 ]]; then
    exit 1
fi
}

# Run main function
main "$@"
