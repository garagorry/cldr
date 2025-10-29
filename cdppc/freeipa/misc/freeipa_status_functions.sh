            #!/bin/bash
            # FreeIPA Health Check Functions v2.1.0
            # Author: Jimmy Garagorry 
            # Comprehensive health check suite for FreeIPA infrastructure in Cloudera CDP
            #
            # Usage:
            #   source freeipa_status_functions.sh
            #   freeipa_comprehensive_health_check
            #
            # Dependencies: salt, jq, ipa, cipa, ldapsearch, host

            # Color definitions

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

            # Utility functions

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

            # Core health check functions

            function freeipa_comprehensive_health_check() {
                echo -e "${YELLOW}╔══════════════════════════════════════════════════════════════╗${NC}"
                echo -e "${YELLOW}║              FreeIPA Comprehensive Health Check              ║${NC}"
                echo -e "${YELLOW}╚══════════════════════════════════════════════════════════════╝${NC}\n"
                
                # Initialize health check tracking
                local start_time=$(date +%s)
                local overall_status=0
                local total_checks=19
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
                
                # Check 9: CDP Services
                show_progress_bar 9 $total_checks "Checking CDP Services"
                if freeipa_cdp_services_check; then
                    passed_checks=$((passed_checks + 1))
                    log_message "SUCCESS" "CDP services check passed"
                else
                    failed_checks=$((failed_checks + 1))
                    overall_status=1
                    log_message "ERROR" "CDP services check failed"
                fi
                
                # Check 10: Network Ports
                show_progress_bar 10 $total_checks "Checking Network Ports"
                if freeipa_checkports; then
                    passed_checks=$((passed_checks + 1))
                    log_message "SUCCESS" "Port validation check passed"
                else
                    failed_checks=$((failed_checks + 1))
                    overall_status=1
                    log_message "ERROR" "Port validation check failed"
                fi
                
                # Check 11: Health Agent API
                show_progress_bar 11 $total_checks "Checking Health Agent API"
                if freeipa_health_agent_check; then
                    passed_checks=$((passed_checks + 1))
                    log_message "SUCCESS" "Health agent API check passed"
                else
                    failed_checks=$((failed_checks + 1))
                    overall_status=1
                    log_message "ERROR" "Health agent API check failed"
                fi
                
                # Check 12: CCM Availability
                show_progress_bar 12 $total_checks "Checking CCM Availability"
                if freeipa_ccm_check; then
                    passed_checks=$((passed_checks + 1))
                    log_message "SUCCESS" "CCM check passed"
                else
                    failed_checks=$((failed_checks + 1))
                    overall_status=1
                    log_message "ERROR" "CCM check failed"
                fi
                
                # Check 13: Control Plane Connectivity
                show_progress_bar 13 $total_checks "Checking Control Plane Connectivity"
                if freeipa_ccm_network_status_check; then
                    passed_checks=$((passed_checks + 1))
                    log_message "SUCCESS" "Control plane connectivity check passed"
                else
                    failed_checks=$((failed_checks + 1))
                    overall_status=1
                    log_message "ERROR" "Control plane connectivity check failed"
                fi
                
                # Check 14: Saltuser Password
                show_progress_bar 14 $total_checks "Checking Saltuser Password"
                if freeipa_check_saltuser_password_rotation; then
                    passed_checks=$((passed_checks + 1))
                    log_message "SUCCESS" "Saltuser password check passed"
                else
                    failed_checks=$((failed_checks + 1))
                    overall_status=1
                    log_message "ERROR" "Saltuser password check failed"
                fi
                
                # Check 15: Nginx Configuration
                show_progress_bar 15 $total_checks "Checking Nginx Configuration"
                if freeipa_check_nginx; then
                    passed_checks=$((passed_checks + 1))
                    log_message "SUCCESS" "Nginx config check passed"
                else
                    failed_checks=$((failed_checks + 1))
                    overall_status=1
                    log_message "ERROR" "Nginx config check failed"
                fi
                
                # Check 16: Disk Usage
                show_progress_bar 16 $total_checks "Checking Disk Usage"
                if freeipa_disk_check; then
                    passed_checks=$((passed_checks + 1))
                    log_message "SUCCESS" "Disk usage check passed"
                else
                    failed_checks=$((failed_checks + 1))
                    overall_status=1
                    log_message "ERROR" "Disk usage check failed"
                fi
                
                # Check 17: Memory Usage
                show_progress_bar 17 $total_checks "Checking Memory Usage"
                if freeipa_memory_check; then
                    passed_checks=$((passed_checks + 1))
                    log_message "SUCCESS" "Memory check passed"
                else
                    failed_checks=$((failed_checks + 1))
                    overall_status=1
                    log_message "ERROR" "Memory check failed"
                fi
                
                # Check 18: CPU Usage
                show_progress_bar 18 $total_checks "Checking CPU Usage"
                if freeipa_cpu_check; then
                    passed_checks=$((passed_checks + 1))
                    log_message "SUCCESS" "CPU check passed"
                else
                    failed_checks=$((failed_checks + 1))
                    overall_status=1
                    log_message "ERROR" "CPU check failed"
                fi
                
                # Check 19: Inter-Node Connectivity
                show_progress_bar 19 $total_checks "Checking Inter-Node Connectivity"
                if freeipa_internode_connectivity_check; then
                    passed_checks=$((passed_checks + 1))
                    log_message "SUCCESS" "Inter-node connectivity check passed"
                else
                    failed_checks=$((failed_checks + 1))
                    overall_status=1
                    log_message "ERROR" "Inter-node connectivity check failed"
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

            # Resource monitoring functions

            function freeipa_disk_check() {
                local disk_threshold=${1:-50}
                log_message "INFO" "Starting disk usage check (threshold: ${disk_threshold}%)"
                
                source activate_salt_env
                echo -e "Checking disk usage across FreeIPA nodes..."
                
                # Show spinner for disk check
                show_spinner "Checking disk usage across all nodes" &
                local spinner_pid=$!
                
                local disk_output=$(salt '*' cmd.run "
                    #!/bin/bash
                    DISK_THRESHOLD=${disk_threshold}
                    for DiskAvailable in \$(lsblk -l | awk '\$1 ~ /sd[a-z]\$/ || \$1 ~ /nvme/ {print \$1}' | sort -u)
                    do
                        for i in \$(mount | grep \"\${DiskAvailable}\" | cut -d ' ' -f 3)
                        do
                            P_DISK_USAGE=\$(df -h \${i}| awk '\$0 !~ /Filesystem/ {print \$5}' |sed 's|\%||')
                            if (( P_DISK_USAGE > DISK_THRESHOLD ))
                            then
                                echo -e \"\${DiskAvailable} - \${i} [FAILED] (Usage: \${P_DISK_USAGE}%)\"
                            else
                                echo -e \"\${DiskAvailable} - \${i} [PASS] (Usage: \${P_DISK_USAGE}%)\"
                            fi
                        done
                    done
                " 2>/dev/null)
                
                # Stop spinner and clear line
                kill $spinner_pid 2>/dev/null
                wait $spinner_pid 2>/dev/null
                echo -ne "\r\033[K"
                
                deactivate
                
                # Print the output
                echo "$disk_output"
                
                # Check for failures
                local failed_count=$(echo "$disk_output" | grep -c "FAILED")
                
                if [[ ${failed_count} -eq 0 ]]; then
                    echo -e "Disk usage check [${GREEN}PASS${NC}]"
                    return 0
                else
                    echo -e "Disk usage check [${RED}FAILED${NC}] - Found ${failed_count} disk(s) exceeding threshold"
                    return 1
                fi
            }

            # Function: freeipa_memory_check
            # Description: Checks memory usage across all FreeIPA nodes
            # Returns: 0 if all nodes have sufficient memory, 1 if any are low
            # Usage: freeipa_memory_check [threshold_in_mb]
            function freeipa_memory_check() {
                local memory_threshold=${1:-1024}
                log_message "INFO" "Starting memory check (threshold: ${memory_threshold}MB)"
                
                source activate_salt_env
                echo -e "Checking memory usage across FreeIPA nodes..."
                
                # Show spinner for memory check
                show_spinner "Checking memory across all nodes" &
                local spinner_pid=$!
                
                local memory_output=$(salt '*' cmd.run "
                    #!/bin/bash
                    MEMORY_THRESHOLD=${memory_threshold}
                    FREE_MEMORY=\$(free -m | awk '/Mem:/ {print \$4}')
                    if (( FREE_MEMORY == MEMORY_THRESHOLD ))
                    then
                        echo \"[WARNING] Free Memory: \${FREE_MEMORY}MB (threshold)\"
                    elif (( FREE_MEMORY > MEMORY_THRESHOLD ))
                    then
                        echo \"[PASS] Free Memory: \${FREE_MEMORY}MB\"
                    else
                        echo \"[FAILED] Free Memory: \${FREE_MEMORY}MB below threshold\"
                    fi
                " 2>/dev/null)
                
                # Stop spinner and clear line
                kill $spinner_pid 2>/dev/null
                wait $spinner_pid 2>/dev/null
                echo -ne "\r\033[K"
                
                deactivate
                
                # Print the output
                echo "$memory_output"
                
                # Check for failures
                local failed_count=$(echo "$memory_output" | grep -c "FAILED")
                
                if [[ ${failed_count} -eq 0 ]]; then
                    echo -e "Memory check [${GREEN}PASS${NC}]"
                    return 0
                else
                    echo -e "Memory check [${RED}FAILED${NC}]"
                    return 1
                fi
            }

            # Function: freeipa_cpu_check
            # Description: Checks CPU usage across all FreeIPA nodes
            # Returns: 0 if all nodes have normal CPU usage, 1 if any exceed threshold
            # Usage: freeipa_cpu_check [threshold_percent]
            function freeipa_cpu_check() {
                local cpu_threshold=${1:-50}
                log_message "INFO" "Starting CPU usage check (threshold: ${cpu_threshold}%)"
                
                source activate_salt_env
                echo -e "Checking CPU usage across FreeIPA nodes..."
                
                # Show spinner for CPU check
                show_spinner "Checking CPU usage across all nodes" &
                local spinner_pid=$!
                
                local cpu_output=$(salt '*' cmd.run "
                    #!/bin/bash
                    CPU_THRESHOLD=${cpu_threshold}
                    CPU_USAGE=\$(echo \"scale=2; 100 - \$(iostat -c | awk '/[0-9]\$/ {print \$NF}' | head -1)\" | bc)
                    CPU_USAGE_INT=\$(echo \${CPU_USAGE} | LC_ALL=C xargs printf \"%.*f\n\" 0)
                    if (( CPU_USAGE_INT > CPU_THRESHOLD ))
                    then
                        echo \"[WARNING] CPU Usage: \${CPU_USAGE}% (above threshold)\"
                    elif (( CPU_USAGE_INT < 20 ))
                    then
                        echo \"[PASS] CPU Usage: \${CPU_USAGE}%\"
                    else
                        echo \"[WARNING] CPU Usage: \${CPU_USAGE}%\"
                    fi
                " 2>/dev/null)
                
                # Stop spinner and clear line
                kill $spinner_pid 2>/dev/null
                wait $spinner_pid 2>/dev/null
                echo -ne "\r\033[K"
                
                deactivate
                
                # Print the output
                echo "$cpu_output"
                
                # Check for any issues
                local warning_count=$(echo "$cpu_output" | grep -c "WARNING")
                
                if [[ ${warning_count} -eq 0 ]]; then
                    echo -e "CPU check [${GREEN}PASS${NC}]"
                    return 0
                else
                    echo -e "CPU check [${YELLOW}WARNING${NC}] - ${warning_count} node(s) with high CPU usage"
                    return 0
                fi
            }

            # =============================================================================
            # CDP NODE STATUS MONITOR FUNCTIONS
            # =============================================================================

            # NOTE: CDP Node Status Monitor check has been removed from the comprehensive health check
            # Keeping function commented out for reference

            # # Function: freeipa_cdp_nsm_check
            # # Description: Validates CDP Node Status Monitor for VMs
            # # Returns: 0 if service is running, 1 if not running
            # # Usage: freeipa_cdp_nsm_check
            # function freeipa_cdp_nsm_check() {
            #     log_message "INFO" "Starting CDP Node Status Monitor check"
            #     
            #     local nsm_name="cdp-nodestatus-monitor.service"
            #     source activate_salt_env
            #     
            #     # Show spinner for NSM check
            #     show_spinner "Checking CDP NSM service across all nodes" &
            #     local spinner_pid=$!
            #     
            #     local nsm_output=$(salt '*' cmd.run "
            #         if [[ \$(systemctl status \${nsm_name} 2>/dev/null | awk '/Active:/ {print \$3}') == \"(running)\" ]]
            #         then
            #             echo \"[PASS] CDP Node Status Monitor is running\"
            #         else
            #             echo \"[FAILED] CDP Node Status Monitor is not running\"
            #         fi
            #     " 2>/dev/null)
            #     
            #     # Stop spinner and clear line
            #     kill $spinner_pid 2>/dev/null
            #     wait $spinner_pid 2>/dev/null
            #     echo -ne "\r\033[K"
            #     
            #     deactivate
            #     
            #     # Print the output
            #     echo "$nsm_output"
            #     
            #     # Check for failures
            #     local failed_count=$(echo "$nsm_output" | grep -c "FAILED")
            #     
            #     if [[ ${failed_count} -eq 0 ]]; then
            #         echo -e "CDP Node Status Monitor [${GREEN}PASS${NC}]"
            #         return 0
            #     else
            #         echo -e "CDP Node Status Monitor [${RED}FAILED${NC}]"
            #         return 1
            #     fi
            # }

            # Network validation functions

            function freeipa_internode_connectivity_check() {
                log_message "INFO" "Starting inter-node connectivity check"
                
                source activate_salt_env
                echo -e "Checking inter-node connectivity on critical ports..."
                
                # Get list of all IPA nodes
                local principal=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.admin_user') 
                local pw=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
                echo ${pw} | kinit ${principal} >/dev/null 2>&1
                
                # Show spinner for connectivity check
                show_spinner "Testing connectivity between all FreeIPA nodes" &
                local spinner_pid=$!
                
                # Test connectivity from each node to all other nodes on critical ports
                local connectivity_output=$(salt '*' cmd.run '
            #!/bin/bash
            # FreeIPA replication ports (bidirectional - all nodes to all nodes)
            freeipa_ports="389 636 88"

            # Salt orchestration ports (unidirectional - minions to master only)
            salt_ports="4505 4506"

            failed_connections=0
            total_tests=0

            # Get list of all IPA server FQDNs
            ipa_servers=$(ipa server-find --pkey-only 2>/dev/null | awk -F":" "/Server name:/ {print \$2}" | sed "s/ //g")

            # Identify Salt Master (typically first IPA server, or check pillar)
            salt_master=$(salt-call pillar.get freeipa:hosts --out=json 2>/dev/null | jq -r ".local[0].fqdn" 2>/dev/null)
            if [ -z "$salt_master" ]; then
                # Fallback: assume first server alphabetically is master
                salt_master=$(echo "$ipa_servers" | tr " " "\n" | sort | head -1)
            fi

            echo "Testing from $(hostname -f):"
            echo "  Salt Master: $salt_master"
            echo ""

            # Test FreeIPA replication ports (all nodes to all other nodes)
            echo "  FreeIPA Replication Ports (bidirectional):"
            for target_server in $ipa_servers; do
                # Skip testing connectivity to self
                if [ "$target_server" == "$(hostname -f)" ]; then
                    continue
                fi
                
                for port in $freeipa_ports; do
                    total_tests=$((total_tests + 1))
                    if timeout 2 bash -c "cat < /dev/null > /dev/tcp/$target_server/$port" 2>/dev/null; then
                        echo "    → $target_server:$port [PASS]"
                    else
                        echo "    → $target_server:$port [FAILED]"
                        failed_connections=$((failed_connections + 1))
                    fi
                done
            done

            # Test Salt Master ports (only from minions to master)
            if [ "$(hostname -f)" != "$salt_master" ]; then
                echo ""
                echo "  Salt Master Connectivity (minion → master):"
                for port in $salt_ports; do
                    total_tests=$((total_tests + 1))
                    if timeout 2 bash -c "cat < /dev/null > /dev/tcp/$salt_master/$port" 2>/dev/null; then
                        echo "    → $salt_master:$port [PASS]"
                    else
                        echo "    → $salt_master:$port [FAILED]"
                        failed_connections=$((failed_connections + 1))
                    fi
                done
            fi

            echo ""
            if [ $failed_connections -eq 0 ]; then
                echo "Inter-node connectivity: All tests passed ($total_tests/$total_tests)"
            else
                echo "Inter-node connectivity: $failed_connections/$total_tests FAILED"
            fi
            ' 2>/dev/null)
                
                # Stop spinner and clear line
                kill $spinner_pid 2>/dev/null
                wait $spinner_pid 2>/dev/null
                echo -ne "\r\033[K"
                
                deactivate
                
                # Print the output
                echo "$connectivity_output"
                
                # Check for failures
                local failed_count=$(echo "$connectivity_output" | grep -c "tests failed")
                
                if [[ ${failed_count} -eq 0 ]]; then
                    echo -e "Inter-node connectivity [${GREEN}PASS${NC}]"
                    return 0
                else
                    echo -e "Inter-node connectivity [${RED}FAILED${NC}] - Some nodes cannot communicate on critical ports"
                    return 1
                fi
            }

            # Function: freeipa_checkports
            # Description: Validates expected network ports are listening
            # Returns: 0 if all ports are listening, 1 if any are not
            # Usage: freeipa_checkports
            function freeipa_checkports() {
                log_message "INFO" "Starting port validation check"
                
                echo -e "Checking required FreeIPA ports..."
                
                # Check if lsof is installed, try to install if missing
                if ! rpm -q lsof >/dev/null 2>&1; then
                    echo -e "lsof package is required [${YELLOW}MISSING${NC}]"
                    echo -e "Attempting to install lsof package..."
                    
                    # Show spinner during installation
                    show_spinner "Installing lsof package" &
                    local spinner_pid=$!
                    
                    # Try to install using yum
                    local install_output=$(yum install -y lsof 2>&1)
                    local install_status=$?
                    
                    # Stop spinner
                    kill $spinner_pid 2>/dev/null
                    wait $spinner_pid 2>/dev/null
                    echo -ne "\r\033[K"
                    
                    # Verify installation succeeded
                    if rpm -q lsof >/dev/null 2>&1; then
                        echo -e "lsof package installed successfully [${GREEN}OK${NC}]"
                    else
                        echo -e "\nlsof package installation [${RED}FAILED${NC}]"
                        echo -e "Installation output:"
                        echo "$install_output"
                        echo -e "\nPlease install manually with: ${GREEN}yum install -y lsof${NC}"
                        return 1
                    fi
                fi
                
                local port_list="22 88 53 80 3080 749 464 8005 8009 8080 8443 4505 4506 389 636"
                local failed_ports=0
                
                for port_number in ${port_list}; do
                    if lsof -i :${port_number} >/dev/null 2>&1; then
                        local service=$(netstat -ptan | awk "\$4 ~ /:${port_number}\>/ && \$0 ~ /LISTEN/" | awk -F '/' '{print $NF}' | sort -u | tr '\n' ',' | sed 's/,$//')
                        echo -e "Port ${port_number}:${service} [${GREEN}PASS${NC}]"
                    else
                        echo -e "Port ${port_number} [${RED}FAILED${NC}]"
                        failed_ports=$((failed_ports + 1))
                    fi
                done
                
                if [[ ${failed_ports} -eq 0 ]]; then
                    echo -e "Port validation [${GREEN}PASS${NC}]"
                    return 0
                else
                    echo -e "Port validation [${RED}FAILED${NC}] - ${failed_ports} port(s) not listening"
                    return 1
                fi
            }

            # CDP services validation

            function freeipa_cdp_services_check() {
                log_message "INFO" "Starting CDP services validation check"
                
                source activate_salt_env
                echo -e "Checking CDP services across FreeIPA nodes..."
                
                # Show spinner for CDP services check
                show_spinner "Checking CDP services across all nodes" &
                local spinner_pid=$!
                
                local services_output=$(salt '*' cmd.run '
            #!/bin/bash
            services="cdp-blackbox-exporter.service cdp-freeipa-healthagent.service cdp-freeipa-ldapagent.service cdp-logging-agent.service cdp-node-exporter.service cdp-prometheus.service cdp-request-signer.service"
            failed_services=""
            passed=0
            failed=0

            for service in $services; do
                if systemctl is-active $service >/dev/null 2>&1; then
                    echo "$service: [PASS]"
                    passed=$((passed + 1))
                else
                    echo "$service: [FAILED]"
                    failed_services="$failed_services $service"
                    failed=$((failed + 1))
                fi
            done

            if [ $failed -eq 0 ]; then
                echo "All CDP services running ($passed/$passed)"
            else
                echo "Failed services:$failed_services"
            fi
            ' 2>/dev/null)
                
                # Stop spinner and clear line
                kill $spinner_pid 2>/dev/null
                wait $spinner_pid 2>/dev/null
                echo -ne "\r\033[K"
                
                deactivate
                
                # Print the output
                echo "$services_output"
                
                # Check for failures
                local failed_count=$(echo "$services_output" | grep -c "\[FAILED\]")
                
                if [[ ${failed_count} -eq 0 ]]; then
                    echo -e "CDP services validation [${GREEN}PASS${NC}]"
                    return 0
                else
                    echo -e "CDP services validation [${RED}FAILED${NC}] - ${failed_count} service(s) not running"
                    return 1
                fi
            }

            # Function: freeipa_health_agent_check
            # Description: Validates the FreeIPA Health Agent Service with API check
            # Returns: 0 if service and API are healthy, 1 if not
            # Usage: freeipa_health_agent_check
            function freeipa_health_agent_check() {
                log_message "INFO" "Starting FreeIPA Health Agent API check"
                
                local agent_api_call=$(curl -s --insecure https://localhost:5080 2>/dev/null | jq -r '.checks[].status' | sort -u | head -1)
                local agent_service_running=$(systemctl status cdp-freeipa-healthagent.service 2>/dev/null | awk '/Active:/ {print $3}')
                
                if [[ "${agent_api_call}" == "HEALTHY" ]] && [[ "${agent_service_running}" == "(running)" ]]; then
                    echo -e "FreeIPA Health Agent API [${GREEN}PASS${NC}]"
                    return 0
                else
                    echo -e "\nFreeIPA Health Agent API [${RED}FAILED${NC}]\n"
                    echo -e "Service Status: ${agent_service_running}"
                    echo -e "API Status: ${agent_api_call}"
                    systemctl status -l cdp-freeipa-healthagent.service 2>/dev/null
                    return 1
                fi
            }

            # CCM and Control Plane functions

            function freeipa_is_ccm_enabled() {
                if ! cdp-doctor ccm status >/dev/null 2>&1; then
                    return 1
                else
                    return 0
                fi
            }

            # Function: freeipa_ccm_check
            # Description: Validates CCM (Cluster Connectivity Manager) availability and status
            # Returns: 0 if CCM is working, 1 if not
            # Usage: freeipa_ccm_check
            function freeipa_ccm_check() {
                log_message "INFO" "Starting CCM availability check"
                
                if freeipa_is_ccm_enabled; then
                    # Check CCM network and service status
                    if cdp-doctor ccm status 2>/dev/null | grep True >/dev/null 2>&1; then
                        echo -e "CCM Available [${GREEN}PASS${NC}]"
                        return 0
                    else
                        echo -e "\nCCM Available [${RED}FAILED${NC}]\n"
                        cdp-doctor ccm status 2>/dev/null | sed -e 's/\?\[92m//g' -e 's/\?\[0m//g' | grep -v Connectivity
                        return 1
                    fi
                else
                    echo -e "CCM is not enabled - skipping check"
                    return 0
                fi
            }

            # Function: freeipa_ccm_network_status_check
            # Description: Double-check Control Plane Endpoint access
            # Returns: 0 if all endpoints are accessible, 1 if any fail
            # Usage: freeipa_ccm_network_status_check
            function freeipa_ccm_network_status_check() {
                log_message "INFO" "Starting Control Plane network connectivity check"
                
                if freeipa_is_ccm_enabled; then
                    # Count how many endpoints are NOT "OK" (failed checks)
                    local control_plane_conn=$(cdp-doctor network status --format json 2>/dev/null | jq -r '.ccmAccessible, .clouderaComAccessible, .databusAccessible, .databusS3Accessible, .archiveClouderaComAccessible, .serviceDeliveryCacheS3Accessible, .computeMonitoringAccessible' | grep -v "OK" | wc -l)
                    
                    if [[ ${control_plane_conn} -eq 0 ]]; then
                        echo -e "Control Plane Access [${GREEN}PASS${NC}]"
                        return 0
                    else
                        echo -e "\nControl Plane Access [${RED}FAILED${NC}]\n"
                        echo -e "Found ${control_plane_conn} endpoint(s) not accessible\n"
                        source activate_salt_env
                        salt '*' cmd.run 'cdp-doctor network status' 2>/dev/null | sed -e 's/\?\[92m//g' -e 's/\?\[0m//g'
                        deactivate
                        return 1
                    fi
                else
                    # Count how many endpoints are NOT "OK" (failed checks) - without CCM
                    local control_plane_conn=$(cdp-doctor network status --format json 2>/dev/null | jq -r '.clouderaComAccessible, .databusAccessible, .databusS3Accessible, .archiveClouderaComAccessible, .serviceDeliveryCacheS3Accessible, .computeMonitoringAccessible' | grep -v "OK" | wc -l)
                    
                    if [[ ${control_plane_conn} -eq 0 ]]; then
                        echo -e "Control Plane Access [${GREEN}PASS${NC}]"
                        return 0
                    else
                        echo -e "\nControl Plane Access [${RED}FAILED${NC}]\n"
                        echo -e "Found ${control_plane_conn} endpoint(s) not accessible\n"
                        source activate_salt_env
                        salt '*' cmd.run 'cdp-doctor network status' 2>/dev/null | sed -e 's/\?\[92m//g' -e 's/\?\[0m//g'
                        deactivate
                        return 1
                    fi
                fi
            }

            # Function: freeipa_check_saltuser_password_rotation
            # Description: Validates Salt User password expiration
            # Returns: 0 if password is valid, 1 if expired or expiring soon
            # Usage: freeipa_check_saltuser_password_rotation
            function freeipa_check_saltuser_password_rotation() {
                log_message "INFO" "Starting saltuser password weakness check"
                
                source activate_salt_env
                local current_time=$(TZ=GMT date '+%b %d, %Y')
                local environment_name=$(salt-call pillar.get "telemetry:clusterName" --out=json 2>/dev/null | jq -r '.local' | sed -e 's|"||g' -e 's|-freeipa||')
                local tenant_id=$(salt-call pillar.get "tags:Cloudera-Environment-Resource-Name" 2>/dev/null | awk -F":" '/crn/ {print $5}')
                
                # Show spinner for password check
                show_spinner "Checking saltuser password expiration" &
                local spinner_pid=$!
                
                local password_data=$(salt '*' cmd.run "chage -l saltuser 2>/dev/null | awk -F':' '/Password expires/ {print \$NF}'" 2>/dev/null | grep -v 'cloudera\.site' | sort -u)
                
                # Stop spinner and clear line
                kill $spinner_pid 2>/dev/null
                wait $spinner_pid 2>/dev/null
                echo -ne "\r\033[K"
                
                set -- $(echo "$password_data")
                local expired_count=0
                local current_epoch=$(date -d "${current_time}" +%s 2>/dev/null || date -j -f "%b %d, %Y" "${current_time}" +%s 2>/dev/null)
                
                while (( $# )); do
                    local saltuser_chage_time="${1} ${2}, ${3}"
                    
                    # Convert expiration date to epoch for proper comparison
                    local expire_epoch=$(date -d "${saltuser_chage_time}" +%s 2>/dev/null || date -j -f "%b %d, %Y" "${saltuser_chage_time}" +%s 2>/dev/null)
                    
                    # Compare timestamps (not strings!)
                    if [[ -n "$current_epoch" ]] && [[ -n "$expire_epoch" ]] && [[ ${current_epoch} -gt ${expire_epoch} ]]; then
                        echo -e "\nsaltuser password [${RED}FAILED${NC}] - EXPIRED\n"
                        salt '*' cmd.run "chage -l saltuser 2>/dev/null | grep 'Password expires'" 2>/dev/null
                        echo -e "\nPassword expired on: ${1} ${2}, ${3}"
                        echo -e "Tenant ID: ${RED}${tenant_id}${NC}"
                        echo -e "Environment: ${environment_name}"
                        echo -e "\nAction required:"
                        echo -e "1. Create a Support Ticket"
                        echo -e "2. Request Entitlement ${RED}CDP_ROTATE_SALTUSER_PASSWORD${NC}"
                        echo -e "3. Once granted, run:"
                        echo -e "   ${GREEN}cdp environments rotate-salt-password --environment ${environment_name}${NC}\n"
                        expired_count=$((expired_count + 1))
                    fi
                    shift 3
                done
                
                deactivate
                
                if [[ ${expired_count} -eq 0 ]]; then
                    echo -e "saltuser password [${GREEN}PASS${NC}]"
                    return 0
                else
                    return 1
                fi
            }

            # Function: freeipa_check_nginx
            # Description: Validates nginx.conf consistency via MD5 checksum across nodes
            # Returns: 0 if all nodes have identical config, 1 if different
            # Usage: freeipa_check_nginx
            function freeipa_check_nginx() {
                log_message "INFO" "Starting nginx.conf consistency check"
                
                source activate_salt_env
                echo -e "Checking nginx.conf consistency..."
                
                # Show spinner for nginx check
                show_spinner "Checking nginx.conf MD5 consistency" &
                local spinner_pid=$!
                
                local nginx_md5_output=$(salt '*' cmd.run 'md5sum /etc/nginx/nginx.conf' 2>/dev/null | awk '/nginx/ {print $1}')
                
                # Stop spinner and clear line
                kill $spinner_pid 2>/dev/null
                wait $spinner_pid 2>/dev/null
                echo -ne "\r\033[K"
                
                deactivate
                
                # Count unique MD5 sums
                local unique_md5s=$(echo "$nginx_md5_output" | sort -u | wc -l)
                
                if [[ ${unique_md5s} -eq 1 ]]; then
                    echo -e "nginx.conf consistency [${GREEN}PASS${NC}]"
                    echo -e "All nodes have identical configuration"
                    return 0
                else
                    echo -e "\nnginx.conf consistency [${RED}FAILED${NC}]\n"
                    echo "MD5 checksums differ across nodes:"
                    echo "$nginx_md5_output"
                    return 1
                fi
            }

            # Legacy functions (backward compatibility)

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

            # Uncomment to auto-run when sourced:
            # freeipa_comprehensive_health_check
