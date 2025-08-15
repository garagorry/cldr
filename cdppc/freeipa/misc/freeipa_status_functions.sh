#!/bin/bash
# =============================================================================
# FreeIPA Status Functions - Comprehensive Health Check Suite
# =============================================================================
#
# This script provides a comprehensive set of functions to monitor and validate
# FreeIPA infrastructure health across multiple nodes in a Cloudera environment.
#
# Author: Jimmy Garagorry 
# Version: 2.0.0
# Last Updated: 2025-08-14
#
# =============================================================================
# USAGE
# =============================================================================
#
# Source this file and run the comprehensive health check:
#   source freeipa_status_functions.sh
#   freeipa_comprehensive_health_check
#
# Or run individual checks:
#   freeipa_status_check
#   freeipa_backup_check
#   freeipa_cipa_check
#   freeipa_ldap_conflicts_check
#   freeipa_replication_agreements_check
#   freeipa_groups_consistency_check
#   freeipa_users_consistency_check
#
# =============================================================================
# DEPENDENCIES
# =============================================================================
#
# Required tools:
#   - salt (SaltStack client)
#   - jq (JSON processor)
#   - ipa (FreeIPA client tools)
#   - cipa (FreeIPA consistency checker)
#   - ldapsearch (LDAP client tools)
#   - host (DNS lookup tool)
#
# Required environment:
#   - activate_salt_env script in PATH
#   - Root or sudo access for FreeIPA operations
#   - Valid FreeIPA credentials in /srv/pillar/freeipa/init.sls
#
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

# Function: show_spinner - Display a spinning progress indicator
# Usage: show_spinner "message" &
#        SPINNER_PID=$!
#        # ... long running task ...
#        kill $SPINNER_PID 2>/dev/null
#        wait $SPINNER_PID 2>/dev/null
#        echo -ne "\r\033[K"  # Clear the spinner line
function show_spinner() {
    local message="$1"
    local spinner_chars=("⠋" "⠙" "⠹" "⠸" "⠼" "⠴" "⠦" "⠧" "⠇" "⠏")
    local i=0
    
    while true; do
        echo -ne "\r${CYAN}${spinner_chars[$i]}${NC} ${message}..."
        sleep 0.1
        i=$(( (i + 1) % ${#spinner_chars[@]} ))
    done
}

# Function: show_progress_bar - Display a progress bar
# Usage: show_progress_bar current total "message"
function show_progress_bar() {
    local current=$1
    local total=$2
    local message="$3"
    local width=50
    local percentage=$((current * 100 / total))
    local completed=$((width * current / total))
    local remaining=$((width - completed))
    
    printf "\r${CYAN}[${NC}"
    printf "%${completed}s" | tr ' ' '█'
    printf "%${remaining}s" | tr ' ' '░'
    printf "${CYAN}]${NC} %3d%% %s" "$percentage" "$message"
    
    if [[ $current -eq $total ]]; then
        echo
    fi
}

# Function: log_message - Enhanced logging with timestamps and levels
function log_message() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
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
}

# =============================================================================
# CORE HEALTH CHECK FUNCTIONS
# =============================================================================

# Function: freeipa_comprehensive_health_check
# Description: Executes all FreeIPA health checks in sequence with progress tracking
# Returns: 0 if all checks pass, 1 if any check fails
# Usage: freeipa_comprehensive_health_check
function freeipa_comprehensive_health_check() {
    echo -e "${YELLOW}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║              FreeIPA Comprehensive Health Check              ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════════════════════╝${NC}\n"
    
    # Initialize health check tracking
    local start_time=$(date +%s)
    local overall_status=0
    local total_checks=8
    local passed_checks=0
    local failed_checks=0
    
    log_message "INFO" "Health check started at $(date '+%Y-%m-%d %H:%M:%S')"
    echo
    
    # Check 1: FreeIPA Services Status
    show_progress_bar 1 $total_checks "Checking FreeIPA Services Status"
    if freeipa_status_check; then
        passed_checks=$((passed_checks + 1))
        log_message "SUCCESS" "FreeIPA services status check passed"
    else
        failed_checks=$((failed_checks + 1))
        overall_status=1
        log_message "ERROR" "FreeIPA services status check failed"
    fi
    
    # Check 2: FreeIPA Cloud Backups
    show_progress_bar 2 $total_checks "Checking FreeIPA Cloud Backups"
    if freeipa_backup_check; then
        passed_checks=$((passed_checks + 1))
        log_message "SUCCESS" "FreeIPA cloud backups check passed"
    else
        failed_checks=$((failed_checks + 1))
        overall_status=1
        log_message "ERROR" "FreeIPA cloud backups check failed"
    fi
    
    # Check 3: FreeIPA Replication CIPA State
    show_progress_bar 3 $total_checks "Checking FreeIPA Replication CIPA State"
    if freeipa_cipa_check; then
        passed_checks=$((passed_checks + 1))
        log_message "SUCCESS" "FreeIPA replication CIPA state check passed"
    else
        failed_checks=$((failed_checks + 1))
        overall_status=1
        log_message "ERROR" "FreeIPA replication CIPA state check failed"
    fi
    
    # Check 4: LDAP Conflicts
    show_progress_bar 4 $total_checks "Checking LDAP Conflicts"
    if freeipa_ldap_conflicts_check; then
        passed_checks=$((passed_checks + 1))
        log_message "SUCCESS" "LDAP conflicts check passed"
    else
        failed_checks=$((failed_checks + 1))
        overall_status=1
        log_message "ERROR" "LDAP conflicts check failed"
    fi
    
    # Check 5: Replication Agreements
    show_progress_bar 5 $total_checks "Checking Replication Agreements"
    if freeipa_replication_agreements_check; then
        passed_checks=$((passed_checks + 1))
        log_message "SUCCESS" "Replication agreements check passed"
    else
        failed_checks=$((failed_checks + 1))
        overall_status=1
        log_message "ERROR" "Replication agreements check failed"
    fi
    
    # Check 6: Group Consistency Across Nodes
    show_progress_bar 6 $total_checks "Checking Group Consistency Across Nodes"
    if freeipa_groups_consistency_check; then
        passed_checks=$((passed_checks + 1))
        log_message "SUCCESS" "Group consistency check passed"
    else
        failed_checks=$((failed_checks + 1))
        overall_status=1
        log_message "ERROR" "Group consistency check failed"
    fi
    
    # Check 7: User Consistency Across Nodes
    show_progress_bar 7 $total_checks "Checking User Consistency Across Nodes"
    if freeipa_users_consistency_check; then
        passed_checks=$((passed_checks + 1))
        log_message "SUCCESS" "User consistency check passed"
    else
        failed_checks=$((failed_checks + 1))
        overall_status=1
        log_message "ERROR" "User consistency check failed"
    fi
    
    # Check 8: DNS Entries for Duplicates
    show_progress_bar 8 $total_checks "Checking DNS Entries for Duplicates"
    if freeipa_dns_duplicates_check; then
        passed_checks=$((passed_checks + 1))
        log_message "SUCCESS" "DNS duplicates check passed"
    else
        failed_checks=$((failed_checks + 1))
        overall_status=1
        log_message "ERROR" "DNS duplicates check failed"
    fi
    
    # Calculate execution time
    local end_time=$(date +%s)
    local execution_time=$((end_time - start_time))
    
    # Print comprehensive summary
    echo -e "\n${YELLOW}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║                    Health Check Summary                      ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo -e "${BLUE}Total Checks:${NC} ${total_checks}"
    echo -e "${GREEN}Passed:${NC} ${passed_checks}"
    echo -e "${RED}Failed:${NC} ${failed_checks}"
    echo -e "${BLUE}Execution Time:${NC} ${execution_time} seconds"
    
    if [[ ${overall_status} -eq 0 ]]; then
        echo -e "\n${GREEN}🎉 Overall Status: HEALTHY${NC}"
        log_message "SUCCESS" "All health checks completed successfully"
    else
        echo -e "\n${RED}⚠️  Overall Status: UNHEALTHY${NC}"
        log_message "ERROR" "Health check completed with ${failed_checks} failure(s)"
    fi
    
    log_message "INFO" "Health check completed at $(date '+%Y-%m-%d %H:%M:%S')"
    
    return ${overall_status}
}

# Function: freeipa_status_check
# Description: Validates FreeIPA services across all IPA nodes
# Returns: 0 if all services are running, 1 if any service is down
# Usage: freeipa_status_check
function freeipa_status_check() {
    log_message "INFO" "Starting FreeIPA services status check"
    
    # Show spinner for long-running operation
    show_spinner "Checking FreeIPA services across all nodes" &
    local spinner_pid=$!
    
    source activate_salt_env
    local exit_count=$(salt '*' cmd.run 'ipactl status' 2>/dev/null | egrep -v 'successful|RUNNING|cloudera\.site' | wc -l)
    
    # Stop spinner and clear line
    kill $spinner_pid 2>/dev/null
    wait $spinner_pid 2>/dev/null
    echo -ne "\r\033[K"
    
    if [[ ${exit_count} != 0 ]]; then
        echo -e "Expected Services are running [${RED}FAILED${NC}]"
        salt '*' cmd.run 'ipactl status' 2>/dev/null
        deactivate
        return 1
    else
        echo -e "Expected services are running [${GREEN}PASS${NC}]"
        salt '*' cmd.run 'ipactl status' 2>/dev/null
        deactivate
        return 0
    fi
}

# Function: freeipa_backup_check
# Description: Tests FreeIPA backup functionality and cloud storage access
# Returns: 0 if backup test succeeds, 1 if backup test fails
# Usage: freeipa_backup_check
function freeipa_backup_check() {
    log_message "INFO" "Starting FreeIPA backup functionality check"
    
    local backup_executed=$(ls $(awk -F "[=|\"]" '/\[backup_path\]=/ {print $(NF -1)}' /usr/local/bin/freeipa_backup) | wc -l)
    local test_backup_cmd=$(/usr/local/bin/freeipa_backup -p 2>/dev/null | grep '^Uploaded successfully' >/dev/null 2>&1 && echo $?)

    if [[ ${backup_executed} -eq 0 ]] && [[ ${test_backup_cmd} -eq 0 ]]; then
        echo -e "FreeIPA Cloud Backups [${GREEN}PASS${NC}]"
        
        # Show spinner for backup status retrieval
        show_spinner "Retrieving latest backup status" &
        local spinner_pid=$!
        
        salt '*' cmd.run "
        #!/bin/bash
        if [[ -f /var/log/ipabackup_status_hourly.json ]]
        then
            echo -e 'Latest backups:'
            tail -n1  /var/log/ipabackup_status_hourly.json  | jq -r '[.time, .status, .message]|@csv'
        fi
        " 2>/dev/null
        
        # Stop spinner and clear line
        kill $spinner_pid 2>/dev/null
        wait $spinner_pid 2>/dev/null
        echo -ne "\r\033[K"
        
        return 0
    else
        echo -e "FreeIPA Cloud Backups [${RED}FAILED${NC}]"
        echo -e "Please double-check /var/log/ipabackup.log"
        tail -n 20 /var/log/ipabackup.log
        return 1
    fi
}

# Function: freeipa_cipa_check
# Description: Checks FreeIPA replication consistency using CIPA tool
# Returns: 0 if replication is consistent, 1 if inconsistencies found
# Usage: freeipa_cipa_check
function freeipa_cipa_check() {
    log_message "INFO" "Starting FreeIPA replication CIPA consistency check"
    
    # Show spinner for CIPA check
    show_spinner "Running CIPA replication consistency check" &
    local spinner_pid=$!
    
    local cipa_status=$(/usr/bin/cipa -d $(hostname -d) -W $(tail -n +2 /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password') | sed -ne '3,$p' | awk '/[^\+-]/ {print $(NF -1)}' | sort -u | grep -v '|$' | wc -l)
    
    # Stop spinner and clear line
    kill $spinner_pid 2>/dev/null
    wait $spinner_pid 2>/dev/null
    echo -ne "\r\033[K"
    
    if [[ ${cipa_status} -eq 1 ]]; then
        echo -e "FreeIPA Replication CIPA test [${GREEN}PASS${NC}]"
        /usr/bin/cipa -d $(hostname -d) -W $(tail -n +2 /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
        return 0
    else
        echo -e "FreeIPA Replication CIPA test [${RED}FAILED${NC}]"
        /usr/bin/cipa -d $(hostname -d) -W $(tail -n +2 /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
        return 1
    fi
}

# Function: freeipa_replication_agreements_check
# Description: Validates FreeIPA replication agreements between servers
# Returns: 0 if all agreements are healthy, 1 if any agreement has issues
# Usage: freeipa_replication_agreements_check
function freeipa_replication_agreements_check() {
    log_message "INFO" "Starting FreeIPA replication agreements check"
    
    local principal=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.admin_user') 
    local pw=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    echo ${pw} | kinit ${principal} >/dev/null 2>&1
    
    # Show spinner for replication status check
    show_spinner "Checking replication agreements status" &
    local spinner_pid=$!
    
    # Status of replication between IPA servers
    local freeipa_replica_agreements=$(for replica in $(ipa-replica-manage list | awk '{print $1}' | tr -d ":"); do ipa-replica-manage -v list ${replica}; echo ;done | awk '/last update status:/' | sort -u)
    
    # Stop spinner and clear line
    kill $spinner_pid 2>/dev/null
    wait $spinner_pid 2>/dev/null
    echo -ne "\r\033[K"
    
    if [[ ${freeipa_replica_agreements} =~ succeeded$ ]]; then
        echo -e "FreeIPA Replication Agreements [${GREEN}PASS${NC}]"
        for ipa_node in $(ipa-replica-manage list | awk '{print $1}' | tr -d ":")
        do
            echo -e "${YELLOW}${ipa_node}${NC}"
            ipa-replica-manage -v list ${ipa_node}
            echo
        done
        return 0
    else
        echo -e "FreeIPA Replication Agreements [${RED}FAILED${NC}]"
        for ipa_node in $(ipa-replica-manage list | awk '{print $1}' | tr -d ":")
        do
            echo -e "${YELLOW}${ipa_node}${NC}"
            ipa-replica-manage -v list ${ipa_node}
            echo
        done
        return 1
    fi
}

# Function: freeipa_groups_consistency_check
# Description: Verifies group consistency across all FreeIPA nodes using MD5 hashing
# Returns: 0 if all nodes have identical groups, 1 if inconsistencies found
# Usage: freeipa_groups_consistency_check
function freeipa_groups_consistency_check() {
    log_message "INFO" "Starting group consistency check across FreeIPA nodes"
    
    source activate_salt_env  
    echo -e "Checking group consistency across FreeIPA nodes..."
    
    # Show spinner for group consistency check
    show_spinner "Checking group consistency across all nodes" &
    local spinner_pid=$!
    
    local group_md5_output=$(salt '*' cmd.run '
        #!/bin/bash
        PRINCIPAL=$(sed "1d" /srv/pillar/freeipa/init.sls | jq -r ".freeipa.admin_user") 
        PW=$(sed "1d" /srv/pillar/freeipa/init.sls | jq -r ".freeipa.password")
        echo ${PW} | kinit ${PRINCIPAL} >/dev/null 2>&1
        if [[ $(ipa config-show | awk "/Search size limit:/ {print \$NF}") == 100 ]]
        then
            ipa config-mod --searchrecordslimit=10000 >/dev/null 2>&1
            ipa group-find --all | grep "dn:" | md5sum
        else
            ipa group-find --all | grep "dn:" | md5sum
        fi
    ' 2>/dev/null)
    
    # Stop spinner and clear line
    kill $spinner_pid 2>/dev/null
    wait $spinner_pid 2>/dev/null
    echo -ne "\r\033[K"
    
    deactivate

    # Print the output for user visibility
    echo "$group_md5_output"

    # Extract all md5sums from the output
    # Salt output is typically:
    # minion:
    #     <md5sum>  -
    # So, md5sum is in $2 if indented, or $1 if not indented (rare), or $3 if extra whitespace
    local md5s=($(echo "$group_md5_output" | awk '{for(i=1;i<=NF;i++) if($i ~ /^[a-f0-9]{32}$/) print $i}'))

    # Remove duplicates
    local unique_md5s=($(printf "%s\n" "${md5s[@]}" | sort -u))

    if [[ ${#unique_md5s[@]} -eq 1 && ${#md5s[@]} -gt 0 ]]; then
        echo -e "Group consistency across nodes [${GREEN}PASS${NC}]"
        return 0
    else
        echo -e "Group consistency across nodes [${RED}FAILED${NC}]"
        return 1
    fi
}

# Function: freeipa_users_consistency_check
# Description: Verifies user consistency across all FreeIPA nodes using MD5 hashing
# Returns: 0 if all nodes have identical users, 1 if inconsistencies found
# Usage: freeipa_users_consistency_check
function freeipa_users_consistency_check() {
    log_message "INFO" "Starting user consistency check across FreeIPA nodes"
    
    source activate_salt_env
    echo -e "Checking user consistency across FreeIPA nodes..."
    
    # Show spinner for user consistency check
    show_spinner "Checking user consistency across all nodes" &
    local spinner_pid=$!
    
    local user_md5_output=$(salt '*' cmd.run '
        #!/bin/bash
        PRINCIPAL=$(sed "1d" /srv/pillar/freeipa/init.sls | jq -r ".freeipa.admin_user") 
        PW=$(sed "1d" /srv/pillar/freeipa/init.sls | jq -r ".freeipa.password")
        echo ${PW} | kinit ${PRINCIPAL} >/dev/null 2>&1
        if [[ $(ipa config-show | awk "/Search size limit:/ {print \$NF}") == 100 ]]
        then
            ipa config-mod --searchrecordslimit=10000 >/dev/null 2>&1
            ipa user-find --all | grep "dn:" | md5sum
        else
            ipa user-find --all | grep "dn:" | md5sum
        fi
    ' 2>/dev/null)
    
    # Stop spinner and clear line
    kill $spinner_pid 2>/dev/null
    wait $spinner_pid 2>/dev/null
    echo -ne "\r\033[K"
    
    deactivate

    # Print the output for user visibility
    echo "$user_md5_output"

    # Extract all md5sums from the output
    local md5s=($(echo "$user_md5_output" | awk '{for(i=1;i<=NF;i++) if($i ~ /^[a-f0-9]{32}$/) print $i}'))

    # Remove duplicates
    local unique_md5s=($(printf "%s\n" "${md5s[@]}" | sort -u))

    if [[ ${#unique_md5s[@]} -eq 1 && ${#md5s[@]} -gt 0 ]]; then
        echo -e "User consistency across nodes [${GREEN}PASS${NC}]"
        return 0
    else
        echo -e "User consistency across nodes [${RED}FAILED${NC}]"
        return 1
    fi
}

# Function: freeipa_dns_duplicates_check
# Description: Comprehensive DNS duplicate entry validation for forward and reverse zones
# Returns: 0 if no duplicates found, 1 if duplicates detected
# Usage: freeipa_dns_duplicates_check
function freeipa_dns_duplicates_check() {
    log_message "INFO" "Starting DNS duplicates check for forward and reverse zones"
    
    echo -e "Checking DNS entries for duplicates..."
    
    # Check forward DNS entries
    echo -e "Checking forward DNS entries..."
    local forward_duplicates=0
    source activate_salt_env
    local principal=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.admin_user') 
    local pw=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    echo ${pw} | kinit ${principal} >/dev/null 2>&1
    
    local freeipa_domain=$(salt-call pillar.get freeipa:domain --out=json 2>/dev/null | jq -r '.local')
    
    # Show spinner for forward DNS check
    show_spinner "Checking forward DNS zones for duplicates" &
    local spinner_pid=$!
    
    for dns_forward_zone in $(ipa dnszone-find | awk -F":" '/Zone/ &&  $0 !~ /arpa/ {print $2}' | sed 's/ //g')
    do
        for a_record in $(ipa dnsrecord-find ${dns_forward_zone} | awk -F ":" '/Record.*[0-9]+/ || /Record.*ipa\-/ || /Record.*ipaserver/ || /A record/' | awk -F ":" '/Record.*name/ {print $NF}' | sed 's/ //g')
        do
            if [[ ${a_record} == ipa-ca ]]; then
                if [[ $(host -t A ipa-ca | wc -l) == $(ipa server-find --pkey-only  |  awk -F "[:]" '/Server/ {print "host -t A"$NF}' | bash | awk '{print $NF}' | wc -l) ]]; then
                    echo -e "  ${a_record}.${freeipa_domain} [${GREEN}PASS${NC}]"
                else
                    echo -e "  ${a_record}.${freeipa_domain} [${RED}FAILED${NC}]"
                    forward_duplicates=$((forward_duplicates + 1))
                fi
            else
                # Check for alias (CNAME) in host output
                local host_output=$(host -t A ${a_record})
                if echo "$host_output" | grep -q "is an alias for"; then
                    # If there is an alias, do not consider as duplicated, always PASS
                    echo -e "  ${a_record}.${freeipa_domain} [${GREEN}PASS${NC}]"
                else
                    # Needs to report only one entry
                    if [[ $(echo "$host_output" | grep 'has address' | wc -l) -eq 1 ]]; then
                        echo -e "  ${a_record}.${freeipa_domain} [${GREEN}PASS${NC}]"
                    else
                        echo -e "  ${a_record}.${freeipa_domain} [${RED}FAILED${NC}]"
                        forward_duplicates=$((forward_duplicates + 1))
                    fi
                fi
            fi
        done
    done
    
    # Stop spinner and clear line
    kill $spinner_pid 2>/dev/null
    wait $spinner_pid 2>/dev/null
    echo -ne "\r\033[K"
    
    # Check reverse DNS entries
    echo -e "Checking reverse DNS entries..."
    local reverse_duplicates=0
    local t_stamp=$(date +"%Y%m%d%H%M%S")
    
    # Show spinner for reverse DNS check
    show_spinner "Checking reverse DNS zones for duplicates" &
    spinner_pid=$!
    
    for dns_reverse_zone in $(ipa dnszone-find | awk -F":" '/Zone/ &&  /arpa/ {print $2}' | sed 's/ //g')
    do
        echo -e "  Zone: ${dns_reverse_zone}"
        ipa dnsrecord-find ${dns_reverse_zone} | awk -F ":" '/Record.*[0-9]+/ || /PTR record/' | awk -F":" '/PTR record:/ {print $NF}' | sed 's/ //g' > /tmp/dns-${t_stamp}
        for ptr_record in $(ipa dnsrecord-find ${dns_reverse_zone} | awk -F ":" '/Record.*[0-9]+/ || /PTR record/' | awk -F":" '/PTR record:/ {print $NF}' | sed 's/ //g')
        do
            if [[ $(grep -c ${ptr_record} /tmp/dns-${t_stamp}) -eq 1 ]]; then
                echo -e "    ${ptr_record} [${GREEN}PASS${NC}]"
            else
                echo -e "    ${ptr_record} [${RED}FAILED${NC}]"
                reverse_duplicates=$((reverse_duplicates + 1))
            fi
        done
    done
    
    # Stop spinner and clear line
    kill $spinner_pid 2>/dev/null
    wait $spinner_pid 2>/dev/null
    echo -ne "\r\033[K"
    
    rm -rf /tmp/dns-${t_stamp}
    deactivate
    
    local total_duplicates=$((forward_duplicates + reverse_duplicates))
    if [[ ${total_duplicates} -eq 0 ]]; then
        echo -e "DNS duplicates check [${GREEN}PASS${NC}]"
        return 0
    else
        echo -e "DNS duplicates check [${RED}FAILED${NC}] - Found ${total_duplicates} duplicate entries"
        return 1
    fi
}

# =============================================================================
# LEGACY FUNCTIONS (Maintained for backward compatibility)
# =============================================================================

# Function: freeipa_status
# Description: Legacy function for FreeIPA services status check
# Usage: freeipa_status
function freeipa_status() {
    freeipa_status_check
}

# Function: freeipa_test_backup
# Description: Legacy function for FreeIPA backup test
# Usage: freeipa_test_backup
function freeipa_test_backup() {
    freeipa_backup_check
}

# Function: freeipa_cipa_state
# Description: Legacy function for FreeIPA CIPA state check
# Usage: freeipa_cipa_state
function freeipa_cipa_state() {
    freeipa_cipa_check
}

# Function: freeipa_ldap_conflicts_check
# Description: Checks for LDAP conflicts in FreeIPA
# Returns: 0 if no conflicts, 1 if conflicts found
# Usage: freeipa_ldap_conflicts_check
function freeipa_ldap_conflicts_check() {
    log_message "INFO" "Starting LDAP conflicts check"
    
    local ldap_srv=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.hosts[].fqdn' | tail -n 1)
    local bind_dn="cn=Directory Manager"
    local pw=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    
    # Show spinner for LDAP conflicts check
    show_spinner "Checking for LDAP conflicts" &
    local spinner_pid=$!
    
    local ldap_conflicts_check=$(/usr/bin/cipa -d $(hostname -d) -W $(tail -n +2 /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password') | awk '/LDAP Conflicts/ {print $5,$7,$9}' | grep 0 >/dev/null 2>&1 && echo $?)
    
    # Stop spinner and clear line
    kill $spinner_pid 2>/dev/null
    wait $spinner_pid 2>/dev/null
    echo -ne "\r\033[K"
    
    if [[ ${ldap_conflicts_check} -eq 0 ]]; then
        echo -e "FreeIPA LDAP Conflicts [${GREEN}PASS${NC}]"
        return 0
    else
        echo -e "\nFreeIPA LDAP Conflicts [${RED}FAILED${NC}]\n"
        local user_group_ldap_conflict=$(ldapsearch -H ldap://${ldap_srv} -o ldif-wrap=no -D "${bind_dn}" -w ${pw} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict | awk -F '[ |=|,]' '/nsds5ReplConflict.*cn=users/ || /nsds5ReplConflict.*cn=groups/ {print $5}' | sort -u | wc -l)
        if [[ ${user_group_ldap_conflict} -ne 0 ]]; then
            echo -e "${RED}Users or Groups in Conflict${NC}"
            freeipa_get_user_group_in_conflicts
        else
            echo -e "${RED}Hosts entries in Conflict${NC}"
            freeipa_get_idns_in_conflicts
        fi
        return 1
    fi
}

# Function: freeipa_get_user_group_in_conflicts
# Description: Retrieves user/group LDAP conflicts
# Usage: freeipa_get_user_group_in_conflicts
function freeipa_get_user_group_in_conflicts() {
    local ldap_srv=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.hosts[].fqdn' | tail -n 1)
    local bind_dn="cn=Directory Manager"
    local pw=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    ldapsearch -H ldap://${ldap_srv} -o ldif-wrap=no -D "${bind_dn}" -w ${pw} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict | awk -F '[ |=|,]' '/nsds5ReplConflict.*cn=users/ || /nsds5ReplConflict.*cn=groups/ {print $5}' | sort -u
}

# Function: freeipa_get_idns_in_conflicts
# Description: Retrieves host LDAP conflicts
# Usage: freeipa_get_idns_in_conflicts
function freeipa_get_idns_in_conflicts() {
    local ldap_srv=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.hosts[].fqdn' | tail -n 1)
    local bind_dn="cn=Directory Manager"
    local pw=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    ldapsearch -H ldap://${ldap_srv} -o ldif-wrap=no -D "${bind_dn}" -w ${pw} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict | awk -F '[ |=|,]' '/nsds5ReplConflict.*idnsName=/ {print $5}' | sort -u
}

# Function: freeipa_create_ldap_conflict_file
# Description: Creates a file with LDAP conflicts for analysis
# Usage: freeipa_create_ldap_conflict_file
function freeipa_create_ldap_conflict_file() {
    local ldap_conflicts_file=/tmp/LDAP_CONFLICTS.txt
    local ldap_srv=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.hosts[].fqdn' | tail -n 1)
    local bind_dn="cn=Directory Manager"
    local pw=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    ldapsearch -H ldap://${ldap_srv} -o ldif-wrap=no -D "${bind_dn}" -w ${pw} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict > ${ldap_conflicts_file} 2>/dev/null
    echo "LDAP conflicts saved to: ${ldap_conflicts_file}"
}

# Function: freeipa_duplicated_forward_dns_entries
# Description: Checks for duplicated A records in forward DNS zones
# Usage: freeipa_duplicated_forward_dns_entries
function freeipa_duplicated_forward_dns_entries() {
    source activate_salt_env
    local principal=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.admin_user') 
    local pw=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    echo ${pw} | kinit ${principal} >/dev/null 2>&1
    set -- $(ipa server-find --pkey-only  |  awk -F "[:]" '/Server/ {print "host -t A"$NF}' | bash | awk '{print $NF}')
    local freeipa_domain=$(salt-call pillar.get freeipa:domain --out=json 2>/dev/null | jq -r '.local')
    for dns_forward_zone in $(ipa dnszone-find | awk -F":" '/Zone/ &&  $0 !~ /arpa/ {print $2}' | sed 's/ //g')
    do
        for a_record in $(ipa dnsrecord-find ${dns_forward_zone} | awk -F ":" '/Record.*[0-9]+/ || /Record.*ipa\-/ || /Record.*ipaserver/ || /A record/' | awk -F ":" '/Record.*name/ {print $NF}' | sed 's/ //g')
        do
            if [[ ${a_record} == ipa-ca ]]; then
                #ipa-ca should respond to the same ipa server records
                if [[ $(host -t A ipa-ca | wc -l) == $(ipa server-find --pkey-only  |  awk -F "[:]" '/Server/ {print "host -t A"$NF}' | bash | awk '{print $NF}' | wc -l) ]]; then
                    echo -e "${a_record}.${freeipa_domain} [${GREEN}PASS${NC}]"
                else
                    echo -e "${a_record}.${freeipa_domain} [${RED}FAILED${NC}]"
                fi
            else
                # Needs to report only one entry
                if [[ $(host -t A ${a_record} | grep 'has address' | wc -l) -eq 1 ]]; then
                    echo -e "${a_record}.${freeipa_domain} [${GREEN}PASS${NC}]"
                else
                    echo -e "${a_record}.${freeipa_domain} [${RED}FAILED${NC}]"
                fi
            fi
        done
    done  
    deactivate
}

# Function: freeipa_duplicated_reverse_dns_entries
# Description: Checks for duplicated PTR records in reverse DNS zones
# Usage: freeipa_duplicated_reverse_dns_entries
function freeipa_duplicated_reverse_dns_entries() {
    local principal=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.admin_user') 
    local pw=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    echo ${pw} | kinit ${principal} >/dev/null 2>&1
    local t_stamp=$(date +"%Y%m%d%H%M%S")
    for dns_reverse_zone in $(ipa dnszone-find | awk -F":" '/Zone/ &&  /arpa/ {print $2}' | sed 's/ //g')
    do
        echo -e "\n${dns_reverse_zone}\n"
        ipa dnsrecord-find ${dns_reverse_zone} | awk -F ":" '/Record.*[0-9]+/ || /PTR record/' | awk -F":" '/PTR record:/ {print $NF}' | sed 's/ //g' > /tmp/dns-${t_stamp}
        for ptr_record in $(ipa dnsrecord-find ${dns_reverse_zone} | awk -F ":" '/Record.*[0-9]+/ || /PTR record/' | awk -F":" '/PTR record:/ {print $NF}' | sed 's/ //g')
        do
            if [[ $(grep -c ${ptr_record} /tmp/dns-${t_stamp}) -eq 1 ]]; then
                echo -e "${ptr_record} [${GREEN}PASS${NC}]"
            else
                echo -e "\n${ptr_record} [${RED}FAILED${NC}]\n"
                ipa dnsrecord-find ${dns_reverse_zone} | grep --color -B1 "${ptr_record}"
            fi
        done
    done
    rm -rf /tmp/dns-${t_stamp}
}

# =============================================================================
# MAIN EXECUTION SECTION
# =============================================================================

# Uncomment the line below to automatically run the comprehensive health check
# when this script is sourced
# freeipa_comprehensive_health_check
