#!/bin/bash
# =============================================================================
# FreeIPA Comprehensive Health Check Runner
# =============================================================================
#
# This script provides a user-friendly interface to run FreeIPA health checks
# with enhanced features including progress tracking, logging, and customization.
#
# Author: Jimmy Garagorry
# Version: 2.1.0
# Last Updated: 2025-12-19
#
# =============================================================================
# USAGE
# =============================================================================
#
# Basic usage:
#   ./run_freeipa_health_check.sh
#
# With options:
#   ./run_freeipa_health_check.sh [OPTIONS]
#
# Options:
#   -h, --help          Show this help message
#   -v, --verbose       Enable verbose output
#   -l, --log           Enable logging to file
#   -q, --quiet         Suppress progress indicators
#   -t, --target        Specify Salt target (default: all nodes)
#   -c, --check         Run specific health check only
#   -n, --dry-run       Show what would be executed without running
#
# Examples:
#   ./run_freeipa_health_check.sh -v -l                    # Verbose with logging
#   ./run_freeipa_health_check.sh -c freeipa_status_check  # Single check only
#   ./run_freeipa_health_check.sh -t "*master*"            # Specific target
#
# =============================================================================

# =============================================================================
# CONFIGURATION
# =============================================================================

# Script configuration
SCRIPT_NAME="run_freeipa_health_check.sh"
SCRIPT_VERSION="2.1.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FUNCTIONS_FILE="${SCRIPT_DIR}/freeipa_status_functions.sh"
LOG_DIR="/var/log/freeipa_health_check"
LOG_FILE="${LOG_DIR}/health_check_$(date +%Y%m%d_%H%M%S).log"

# Default settings
VERBOSE=false
LOGGING_ENABLED=false
QUIET_MODE=false
DRY_RUN=false
SALT_TARGET="*"
SPECIFIC_CHECK=""

# =============================================================================
# COLOR DEFINITIONS
# =============================================================================

# Define colors if not already set
if [[ -z "${RED}" ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    PURPLE='\033[0;35m'
    NC='\033[0m' # No Color
fi

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

# Function: show_help - Display help information
function show_help() {
    cat << EOF
${CYAN}${SCRIPT_NAME} v${SCRIPT_VERSION}${NC}

${BLUE}FreeIPA Comprehensive Health Check Runner${NC}

${YELLOW}USAGE:${NC}
    ${SCRIPT_NAME} [OPTIONS]

${YELLOW}OPTIONS:${NC}
    -h, --help          Show this help message
    -v, --verbose       Enable verbose output
    -l, --log           Enable logging to file
    -q, --quiet         Suppress progress indicators
    -t, --target        Specify Salt target (default: all nodes)
    -c, --check         Run specific health check only
    -n, --dry-run       Show what would be executed without running

${YELLOW}EXAMPLES:${NC}
    ${SCRIPT_NAME}                    # Run comprehensive health check
    ${SCRIPT_NAME} -v -l              # Verbose with logging
    ${SCRIPT_NAME} -c freeipa_status_check  # Single check only
    ${SCRIPT_NAME} -t "*master*"      # Specific target
    ${SCRIPT_NAME} -n                 # Dry run mode

${YELLOW}HEALTH CHECKS AVAILABLE:${NC}
    freeipa_status_check               # Services status
    freeipa_backup_check               # Cloud backups
    freeipa_cipa_check                 # Replication consistency
    freeipa_ldap_conflicts_check       # LDAP conflicts
    freeipa_replication_agreements_check # Replication agreements
    freeipa_groups_consistency_check   # Group consistency
    freeipa_users_consistency_check    # User consistency
    freeipa_dns_duplicates_check       # DNS duplicates
    freeipa_cdp_services_check         # CDP services validation (7 services)
    freeipa_checkports                 # Network ports validation
    freeipa_health_agent_check         # Health agent API check
    freeipa_ccm_check                  # CCM availability
    freeipa_ccm_network_status_check   # Control plane connectivity
    freeipa_check_saltuser_password_rotation # Saltuser password
    freeipa_check_nginx                # Nginx configuration
    freeipa_disk_check                 # Disk usage monitoring
    freeipa_memory_check               # Memory monitoring
    freeipa_cpu_check                  # CPU usage monitoring
    freeipa_internode_connectivity_check # Inter-node port connectivity

${YELLOW}EXIT CODES:${NC}
    0 - All health checks passed
    1 - One or more health checks failed
    2 - Script execution error
    3 - Invalid arguments or configuration

EOF
}

# Function: log_message - Enhanced logging with timestamps and levels
function log_message() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Console output
    case "$level" in
        "INFO")
            echo -e "${BLUE}[${timestamp}] INFO:${NC} ${message}"
            ;;
        "SUCCESS")
            echo -e "${GREEN}[${timestamp}] SUCCESS:${NC} ${message}"
            ;;
        "WARNING")
            echo -e "${YELLOW}[${timestamp}] WARNING:${NC} ${message}"
            ;;
        "ERROR")
            echo -e "${RED}[${timestamp}] ERROR:${NC} ${message}"
            ;;
        *)
            echo -e "${PURPLE}[${timestamp}] ${level}:${NC} ${message}"
            ;;
    esac
    
    # File logging if enabled
    if [[ "$LOGGING_ENABLED" == true ]]; then
        echo "[${timestamp}] ${level}: ${message}" >> "$LOG_FILE"
    fi
}

# Function: show_banner - Display professional banner
function show_banner() {
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║              FreeIPA Health Check Runner v${SCRIPT_VERSION}              ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo
}

# Function: validate_environment - Check prerequisites
function validate_environment() {
    log_message "INFO" "Validating environment and prerequisites..."
    
    # Check if functions file exists
    if [[ ! -f "${FUNCTIONS_FILE}" ]]; then
        log_message "ERROR" "Functions file not found: ${FUNCTIONS_FILE}"
        return 1
    fi
    
    # Check if running as root (recommended)
    if [[ $EUID -ne 0 ]]; then
        log_message "WARNING" "Not running as root. Some operations may fail."
        log_message "WARNING" "Consider running with: sudo $0"
    fi
    
    # Try to activate Salt environment if available
    local salt_activated=false
    if ! command -v salt &> /dev/null; then
        # Salt not in PATH, try to activate it
        if [[ -f "activate_salt_env" ]]; then
            source activate_salt_env &> /dev/null && salt_activated=true
        elif [[ -f "/root/activate_salt_env" ]]; then
            source /root/activate_salt_env &> /dev/null && salt_activated=true
        elif [[ -f "/usr/local/bin/activate_salt_env" ]]; then
            source /usr/local/bin/activate_salt_env &> /dev/null && salt_activated=true
        fi
        
        # Check if Salt is now available
        if command -v salt &> /dev/null; then
            log_message "INFO" "Salt environment activated successfully"
            salt_activated=true
        fi
    else
        salt_activated=true
    fi
    
    # Check for required tools (after trying to activate Salt)
    local required_tools=("jq" "ipa" "cipa" "ldapsearch" "host")
    local missing_tools=()
    
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    # Warn about Salt only if activation failed
    if [[ "$salt_activated" == false ]]; then
        log_message "WARNING" "Salt not available. Tried sourcing 'activate_salt_env' from common locations."
        log_message "WARNING" "Some health checks require Salt. Run: source activate_salt_env"
    fi
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log_message "WARNING" "Missing optional tools: ${missing_tools[*]}"
        log_message "WARNING" "Some health checks may not run"
    fi
    
    return 0
}

# Function: parse_arguments - Parse command line arguments
function parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -l|--log)
                LOGGING_ENABLED=true
                shift
                ;;
            -q|--quiet)
                QUIET_MODE=true
                shift
                ;;
            -t|--target)
                SALT_TARGET="$2"
                shift 2
                ;;
            -c|--check)
                SPECIFIC_CHECK="$2"
                shift 2
                ;;
            -n|--dry-run)
                DRY_RUN=true
                shift
                ;;
            *)
                log_message "ERROR" "Unknown option: $1"
                show_help
                exit 3
                ;;
        esac
    done
}

# Function: setup_logging - Initialize logging if enabled
function setup_logging() {
    if [[ "$LOGGING_ENABLED" == true ]]; then
        # Create log directory if it doesn't exist
        mkdir -p "$LOG_DIR"
        
        # Log script start
        echo "=== FreeIPA Health Check Started: $(date) ===" >> "$LOG_FILE"
        echo "Script: ${SCRIPT_NAME} v${SCRIPT_VERSION}" >> "$LOG_FILE"
        echo "Arguments: $*" >> "$LOG_FILE"
        echo "User: $(whoami)" >> "$LOG_FILE"
        echo "Hostname: $(hostname -f)" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
        
        log_message "INFO" "Logging enabled: $LOG_FILE"
    fi
}

# Function: run_specific_check - Execute a single health check
function run_specific_check() {
    local check_name="$1"
    
    log_message "INFO" "Running specific health check: $check_name"
    
    # Check if function exists
    if ! declare -f "$check_name" > /dev/null; then
        log_message "ERROR" "Health check function '$check_name' not found"
        log_message "INFO" "Available functions:"
        awk '/^function/ {print "  " $2}' "$FUNCTIONS_FILE" | grep -v "show_"
        return 1
    fi
    
    # Execute the check
    if "$check_name"; then
        log_message "SUCCESS" "Health check '$check_name' completed successfully"
        return 0
    else
        log_message "ERROR" "Health check '$check_name' failed"
        return 1
    fi
}

# Function: cleanup - Cleanup function for script exit
function cleanup() {
    if [[ "$LOGGING_ENABLED" == true ]]; then
        echo "" >> "$LOG_FILE"
        echo "=== FreeIPA Health Check Completed: $(date) ===" >> "$LOG_FILE"
        echo "Exit Code: $1" >> "$LOG_FILE"
    fi
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

# Set up cleanup trap
trap 'cleanup $?' EXIT

# Parse command line arguments
parse_arguments "$@"

# Show banner
show_banner

# Setup logging if enabled
setup_logging "$@"

# Validate environment
if ! validate_environment; then
    log_message "ERROR" "Environment validation failed"
    exit 2
fi

# Source the functions
log_message "INFO" "Sourcing FreeIPA status functions..."
if ! source "${FUNCTIONS_FILE}"; then
    log_message "ERROR" "Failed to source functions file"
    exit 2
fi

# Check if comprehensive health check function exists
if ! declare -f freeipa_comprehensive_health_check > /dev/null; then
    log_message "ERROR" "Comprehensive health check function not found"
    log_message "ERROR" "Please ensure you have the latest version of freeipa_status_functions.sh"
    exit 2
fi

# Display configuration
log_message "INFO" "Configuration:"
log_message "INFO" "  Verbose Mode: $VERBOSE"
log_message "INFO" "  Logging: $LOGGING_ENABLED"
log_message "INFO" "  Quiet Mode: $QUIET_MODE"
log_message "INFO" "  Dry Run: $DRY_RUN"
log_message "INFO" "  Salt Target: $SALT_TARGET"
if [[ -n "$SPECIFIC_CHECK" ]]; then
    log_message "INFO" "  Specific Check: $SPECIFIC_CHECK"
fi

echo

# Execute health checks based on configuration
if [[ "$DRY_RUN" == true ]]; then
    log_message "INFO" "DRY RUN MODE - No health checks will be executed"
    if [[ -n "$SPECIFIC_CHECK" ]]; then
        log_message "INFO" "Would run: $SPECIFIC_CHECK"
    else
        log_message "INFO" "Would run: freeipa_comprehensive_health_check"
    fi
    exit 0
fi

# Run specific check or comprehensive health check
if [[ -n "$SPECIFIC_CHECK" ]]; then
    if run_specific_check "$SPECIFIC_CHECK"; then
        log_message "SUCCESS" "Specific health check completed successfully!"
        exit 0
    else
        log_message "ERROR" "Specific health check failed!"
        exit 1
    fi
else
    # Run comprehensive health check
    log_message "INFO" "Starting comprehensive FreeIPA health check..."
    echo
    
    if freeipa_comprehensive_health_check; then
        log_message "SUCCESS" "Comprehensive health check completed successfully!"
        echo
        echo -e "${GREEN}✅ All health checks passed!${NC}"
        exit 0
    else
        log_message "ERROR" "Comprehensive health check completed with failures!"
        echo
        echo -e "${RED}❌ Some health checks failed!${NC}"
        exit 1
    fi
fi
