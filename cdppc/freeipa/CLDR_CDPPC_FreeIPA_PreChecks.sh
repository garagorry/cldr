#!/usr/bin/env bash
#
# ------------------------------------------------------------------
# Description:
# - FreeIPA Pre-Flight Checks
# - This script needs to run from an IPA node as the root user.
# ------------------------------------------------------------------
# ------------------------------------------------------------------
# Author: Jimmy Garagorry | jimmy@garagorry.com
# ------------------------------------------------------------------
# We can't trap 9) SIGKILL | 19) SIGSTOP
#  kill -l
#  1) SIGHUP       2) SIGINT       3) SIGQUIT      4) SIGILL       5) SIGTRAP
#  6) SIGABRT      7) SIGBUS       8) SIGFPE       9) SIGKILL     10) SIGUSR1
# 11) SIGSEGV     12) SIGUSR2     13) SIGPIPE     14) SIGALRM     15) SIGTERM
# 16) SIGSTKFLT   17) SIGCHLD     18) SIGCONT     19) SIGSTOP     20) SIGTSTP
# 21) SIGTTIN     22) SIGTTOU     23) SIGURG      24) SIGXCPU     25) SIGXFSZ
# 26) SIGVTALRM   27) SIGPROF     28) SIGWINCH    29) SIGIO       30) SIGPWR
# 31) SIGSYS      34) SIGRTMIN    35) SIGRTMIN+1  36) SIGRTMIN+2  37) SIGRTMIN+3
# 38) SIGRTMIN+4  39) SIGRTMIN+5  40) SIGRTMIN+6  41) SIGRTMIN+7  42) SIGRTMIN+8
# 43) SIGRTMIN+9  44) SIGRTMIN+10 45) SIGRTMIN+11 46) SIGRTMIN+12 47) SIGRTMIN+13
# 48) SIGRTMIN+14 49) SIGRTMIN+15 50) SIGRTMAX-14 51) SIGRTMAX-13 52) SIGRTMAX-12
# 53) SIGRTMAX-11 54) SIGRTMAX-10 55) SIGRTMAX-9  56) SIGRTMAX-8  57) SIGRTMAX-7
# 58) SIGRTMAX-6  59) SIGRTMAX-5  60) SIGRTMAX-4  61) SIGRTMAX-3  62) SIGRTMAX-2
# 63) SIGRTMAX-1  64) SIGRTMAX

# Remove temporary files upon completion
trap 'salt "*" cmd.run "
    if (( $(klist 2>/dev/null | wc -l) > 0 ))
    then
        kdestroy 2>/dev/null
    fi
    rm -rf /tmp/LDAP_CONFLICTS.txt
    rm -rf /home/cloudbreak/freeipa_disk_precheck.sh
    rm -rf /home/cloudbreak/freeipa_memory_precheck.sh
    rm -rf /home/cloudbreak/freeipa_cpu_precheck.sh
    rm -rf /home/cloudbreak/freeipa_functions_create_report.sh
    rm -rf /tmp/freeipa_disk_precheck.sh
    rm -rf /tmp/freeipa_memory_precheck.sh
    rm -rf /tmp/freeipa_cpu_precheck.sh
    rm -rf /tmp/freeipa_functions_create_report.sh
    " 2>/dev/null
' EXIT

trap 'trap_not_exit' SIGHUP SIGINT SIGQUIT SIGTSTP

# Function: trap_not_exit - Avoid CTRL + C, CTRL + Z, CTRL \ {{{1
#-----------------------------------------------------------------------
function trap_not_exit () 
{
	while true
	do
	  clear
	  echo "You cannot finish this script using:"
	  echo "CTRL + C"
	  echo "CTRL + Z"
	  echo "CTRL \ "
	  echo -n "Press C + Enter to continue: "
	  read OPC
	  case ${OPC} in
	    C|c)
            clear
		    echo "Press ENTER to get the Menu"
	    	break
		    ;;
	    *)
	    	echo ":-( Invalid Option"
            sleep 2
		    ;;
	  esac
	done
}

# Function: term_check - Validates the minimum terminal size {{{1
#-----------------------------------------------------------------------
function term_check () 
{
    if [ "${COLS}" -lt 84 ] || [ "${ROWS}" -lt 10]
    then
        echo "Insufficient terminal size"
        echo "Please enlarge or maximize the size of the terminal."
        exit 1
    fi
}

# Function: set_term - Sanity Terminal Check {{{1
#---------------------------------------------------------------
function set_term () 
{
    # Move the cursor on upper-left corner and clear the entire screen
    tput clear
    # Make cursor normal visible
    tput cnorm
    # Exit special mode
    tput rmcup
}

# Function: do_spin - Create the spinner for long running processes {{{1
#-----------------------------------------------------------------------
function do_spin ()
{
    spinner="/|\\-/|\\-"
    while :
    do
        for i in $(seq 0 7)
        do
            echo -n "${spinner:$i:1}"
            echo -en "\010"
            sleep 1
        done
    done
}

# Function: do_enable_minion2master_copy - Prepare the Salt Master to Push a file from the minion {{{1
#-----------------------------------------------------------------------
function do_enable_minion2master_copy ()
{
    # Create a backup of the salt master configuration file to restore after the script finish
    if [[ ! -d /home/cloudbreak/backup ]]
    then
        mkdir /home/cloudbreak/backup
    fi

    if egrep 'file_recv:|file_recv_max_size:' /etc/salt/master.d/custom.conf >/dev/null 2>&1
    then
        echo "Required configs already applied"
    else
        cp /etc/salt/master.d/custom.conf /home/cloudbreak/backup/salt_master_d_custom.conf.orig_$(date +"%Y%m%d%H%M%S")
        cp /etc/salt/master.d/custom.conf /etc/salt/master.d/custom.conf.orig
        # Enable options to Push a file from the minion up to the master <<cachedir /var/cache/salt/master/minions/minion-id/files>>
        echo -e "file_recv: True"  >> /etc/salt/master.d/custom.conf
        echo -e "file_recv_max_size: 50000" >> /etc/salt/master.d/custom.conf
        systemctl restart salt-master >/dev/null 2>&1
        sleep 15
    fi
}

# Function: recover_default_salt_master_conf - Restore Salt master Configuration {{{1
#-----------------------------------------------------------------------
function recover_default_salt_master_conf ()
{
    if ! egrep 'file_recv:|file_recv_max_size:' /etc/salt/master.d/custom.conf.orig >/dev/null 2>&1
    then
        mv -f /etc/salt/master.d/custom.conf.orig /etc/salt/master.d/custom.conf
        systemctl restart salt-master >/dev/null 2>&1
        sleep 20
    fi
}

# Function: freeipa_services_running - List FreeIPA required services state {{{1
#-----------------------------------------------------------------------
function freeipa_services_running ()
{
    FREEIPA_SERVICE_LIST="certmonger crond gssproxy httpd ipa-custodia ipa-dnskeysyncd kadmin krb5kdc named-pkcs11 nginx $(systemctl | awk '/pki-tomcatd@/ {print $1}') polkit salt-api salt-bootstrap salt-master salt-minion sshd sssd $(systemctl | awk '/dirsrv@/ {print $1}')"
    for Service in ${FREEIPA_SERVICE_LIST}
    do
        SERVICE_CURRENT_STATE=$(systemctl status ${Service} | awk '/Active:/ {print $3}')
        if [[ ${SERVICE_CURRENT_STATE} == "(running)" ]]
        then
            echo -e "${Service} [${GREEN}PASS${NC}]"
        else
            echo -e "\n${Service} [${RED}FAILED${NC}]\n"
            systemctl status ${Service}
            echo
        fi
    done
}

# Function: freeipa_status - Validates FreeIPA services across the IPA nodes {{{1
#-----------------------------------------------------------------------
function freeipa_status ()
{
    EXIT_COUNT=$(salt '*' cmd.run 'ipactl status' 2>/dev/null | egrep -v 'successful|RUNNING|cloudera\.site' | wc -l)
    if [[ ${EXIT_COUNT} != 0 ]]
    then
        echo -e "Expected Services are running [${RED}FAILED${NC}]"
        salt '*' cmd.run 'ipactl status' 2>/dev/null
    else
        echo -e "Expected services are running [${GREEN}PASS${NC}]"
    fi
}

# Function: freeipa_cdp_nsm - Validates CDP Node Status Monitor for VMs {{{1
#-----------------------------------------------------------------------
function freeipa_cdp_nsm ()
{
    NSM_NAME="cdp-nodestatus-monitor.service"
    if [[ $(systemctl status ${NSM_NAME} | awk '/Active:/ {print $3}') == "(running)" ]]
    then
        echo -e "CDP Node Status Monitor for VMs [${GREEN}PASS${NC}]\n"
    else
        echo -e "\nCDP Node Status Monitor for VMs [${RED}FAILED${NC}]\n"
        systemctl status ${NSM_NAME}
        echo
    fi
}

# Function: freeipa_checkports - Validates Expected Open Ports {{{1
#-----------------------------------------------------------------------
function freeipa_checkports ()
{
    echo -e "\n${YELLOW}[02|01] FreeIPA Listenig Ports${NC}\n"
    if rpm -q lsof >/dev/null 2>&1
    then
        for PortNumber in 22 88 1080 53 80 3080 749 464 8005 8009 8080 8443 4505 4506 389 636
        do
            if lsof -i :${PortNumber} >/dev/null 2>&1
            then
                echo -e "${PortNumber}:$(netstat -ptan | awk "\$4 ~ /:${PortNumber}\>/ && \$0 ~ /LISTEN/" | awk -F '/' '{print $NF}' | sort -u) [${GREEN}PASS${NC}]"
            else
                echo -e "\n${PortNumber} [${RED}FAILED${NC}]\n"
            fi
        done
    else
        echo -e "lsof package is required to run this test\nPlease consider installing the package by running: ${RED}yum install -y lsof${NC}"
        echo -en "${GREEN}Would you like to install it? (Y/N): ${NC}"
        read ANSWER

        while true
        do
            case ${ANSWER} in
            Y|y|Yes|YES|yes)
                echo -e "Executing ${RED}yum install -y lsof${NC}\n"
                do_spin &
                SPIN_PID=$!
                yum install -y lsof >/dev/null 2>&1
                kill -9 $SPIN_PID 2>/dev/null
                wait $SPIN_PID >/dev/null 2>&1

                if rpm -q lsof >/dev/null 2>&1
                then
                    for PortNumber in 22 88 1080 53 80 3080 749 464 8005 8009 8080 8443 4505 4506 389 636
                    do
                        if lsof -i :${PortNumber} >/dev/null 2>&1
                        then
                            echo -e "${PortNumber}:$(netstat -ptan | awk "\$4 ~ /:${PortNumber}\>/ && \$0 ~ /LISTEN/" | awk -F '/' '{print $NF}' | sort -u) [${GREEN}PASS${NC}]"
                        else
                            echo -e "\n${PortNumber} [${RED}FAILED${NC}]\n"
                        fi
                    done
                else
                    echo -e "It seems the package did not get installed ...Ignoring this test"
                    echo -e "\nCDP Required Service Check [${RED}FAILED${NC}]\n"
                fi
                break
                ;;
            N|n|No|NO|no)
                echo "Ignoring this test..."
                echo -e "LISTENING State for all the Required Network Ports [${RED}FAILED${NC}]\n"
                break
                ;;
            *)
                echo ":-( Invalid Option..."
                echo -en "${GREEN}Would you like to install it? (Y/N): ${NC}"
                read ANSWER
            ;;
            esac
        done
    fi
}

# Function: freeipa_health_agent - Validates the FreeIPA Health Agent Service {{{1
#-----------------------------------------------------------------------
function freeipa_health_agent ()
{
    AGENT_API_CALL=$(curl -s --insecure https://localhost:5080 | jq '.checks[].status' | sed 's/\"//g' | sort -u)
    AGENT_SERVICE_RUNNING=$(systemctl status cdp-freeipa-healthagent.service | awk '/Active:/ {print $3}')
    if [[  ${AGENT_API_CALL} == "HEALTHY" ]] && [[ ${AGENT_SERVICE_RUNNING}  == "(running)" ]]
    then
        echo -e "FreeIPA Health Agent Service [${GREEN}PASS${NC}]"
    else
        echo -e "\nFreeIPA Health Agent Service [${RED}FAILED${NC}]\n"
        systemctl status -l cdp-freeipa-healthagent.service
    fi
}

# Function: freeipa_create_remote_scripts - Create a copy scripts to be executed using salt {{{1
#-----------------------------------------------------------------------
function freeipa_create_remote_scripts ()
{
cat > /home/cloudbreak/freeipa_disk_precheck.sh <<EOF
#!/usr/bin/env bash
# Disk used under 50%
DISK_THRESHOLD=50
echo -e "\n[04|01] Disk Space Used\n"
for DiskAvailable in \$(lsblk -l | awk '\$1 ~ /sd[a-z]\$/ || \$1 ~ /nvme/ {print \$1}' | sort -u)
do
    for i in \$(mount | grep "\${DiskAvailable}" | cut -d ' ' -f 3)
    do
        P_DISK_USAGE=\$(df -h \${i}| awk '\$0 !~ /Filesystem/ {print \$5}' |sed "s|\%||")
        if (( P_DISK_USAGE > DISK_THRESHOLD ))
        then
            echo -e "\n\${DiskAvailable} - \${i} [FAILED]\n"
            df -h \${i}
        else
            echo -e "\${DiskAvailable} - \${i} [PASS]"
            df -h \${i} | awk '\$0 !~ /Filesystem/ {print \$NF,"Used",\$4}'
        fi
    done
done
EOF

cat > /home/cloudbreak/freeipa_memory_precheck.sh <<EOF
#!/usr/bin/env bash
# Check for memory usage under 1gb
echo -e "\n[04|02] Memory Used\n"
FREE_MEMORY=\$(free -m | awk '/Mem:/ {print \$4}')
if (( FREE_MEMORY == 1024 ))
then
    echo -e "Free Memory (Available -> \${FREE_MEMORY}) under 1G [WARNING]"
elif (( FREE_MEMORY > 1024 ))
then
    echo -e "Free Memory (Available -> \${FREE_MEMORY}) [PASS]"
else
    echo -e "Free Memory (Available -> \${FREE_MEMORY}) [FAILED]\n"
    free --human --wide --total
fi
EOF

cat > /home/cloudbreak/freeipa_cpu_precheck.sh <<EOF
#!/usr/bin/env bash
echo -e "\n[04|03] CPU Used\n"
CPU_USAGE=\$(echo "scale=2; 100 - \$(iostat -c | awk '/[0-9]\$/ {print \$NF}')" | bc)
if (( \$(echo \${CPU_USAGE} | LC_ALL=C xargs printf "%.*f\n" 0) > 50 ))
then
    echo -e "CPU Usage (%used -> \${CPU_USAGE}) is more than 50% [WARNING]\n"

elif (( \$(echo \${CPU_USAGE} | LC_ALL=C xargs printf "%.*f\n" 0)  < 20 ))
then
    echo -e "CPU Usage (%used -> \${CPU_USAGE}) [PASS]\n"
else
    echo -e "CPU Usage  (%used -> \${CPU_USAGE}) [FAILED]\n"
    iostat -c
    CPU_USAGE=\$(echo "scale=2; 100 - \$(iostat -c | awk '/[0-9]\$/ {print \$NF}')" | bc)
    echo -e "CPU Usage (%used -> \${CPU_USAGE})\n"
fi
EOF

cat > /home/cloudbreak/freeipa_functions_create_report.sh <<EOF
#!/usr/bin/env bash
#
function freeipa_services_running_report ()
{
    FREEIPA_SERVICE_LIST="certmonger crond gssproxy httpd ipa-custodia ipa-dnskeysyncd kadmin krb5kdc named-pkcs11 nginx \$(systemctl | awk '/pki-tomcatd@/ {print \$1}') polkit salt-api salt-bootstrap salt-master salt-minion sshd sssd \$(systemctl | awk '/dirsrv@/ {print \$1}')"
    for Service in \${FREEIPA_SERVICE_LIST}
    do
        echo -e "\n[\${Service}]\n"
        systemctl status \${Service}
    done
}

function freeipa_status_report ()
{
    salt '*' cmd.run 'ipactl status' 2>/dev/null
}

function freeipa_cdp_nsm_report ()
{
    NSM_NAME="cdp-nodestatus-monitor.service"
    salt '*' cmd.run "systemctl status \${NSM_NAME}" 2>/dev/null
}

function freeipa_checkports_report ()
{
    if rpm -q lsof >/dev/null 2>&1
    then
        for PortNumber in 22 88 1080 53 80 3080 749 464 8005 8009 8080 8443 4505 4506 389 636
        do
            if lsof -i :\${PortNumber} >/dev/null 2>&1
            then
                echo -e "\n\${PortNumber}:\$(netstat -ptan | awk "\\\$4 ~ /:\${PortNumber}\>/ && \\\$0 ~ /LISTEN/" | awk -F '/' '{print \$NF}' | sort -u)\n"
                netstat -ln46 | awk "/:\${PortNumber}\\>/" | sort -u
            else
                echo -e "\nCDP Required Service on port \${PortNumber} is not LISTENING\n"
            fi
        done
    else
        yum install -y lsof
        rpm -q lsof >/dev/null 2>&1
        if [[ \$? == 0 ]]
        then
            for PortNumber in 22 88 1080 53 80 3080 749 464 8005 8009 8080 8443 4505 4506 389 636
            do
                if lsof -i :\${PortNumber} >/dev/null 2>&1
                then
                    echo -e "\nCDP Required Service: \${PortNumber}:\$(netstat -ptan | awk "\\\$4 ~ /:\${PortNumber}\>/ && \\\$0 ~ /LISTEN/" | awk -F '/' '{print \$NF}' | sort -u)\n"
                    netstat -ln46 | awk "/:\${PortNumber}\\>/" | sort -u
                else
                    echo -e "\nCDP Required Service on port \${PortNumber} is not LISTENING\n"
                fi
            done
        else
            echo -e "\nlsof package couldn't be installed\n"
        fi
    fi
}

function freeipa_health_agent ()
{
    systemctl status -l cdp-freeipa-healthagent.service
    echo
    curl -s --insecure https://localhost:5080 | jq '.'
}

function freeipa_disk_precheck_report ()
{
    for DiskAvailable in \$(lsblk -l | awk '\$1 ~ /sd[a-z]\$/ || \$1 ~ /nvme/ {print \$1}' | sort -u)
    do
        for i in \$(mount | grep "\${DiskAvailable}" | cut -d ' ' -f 3)
        do
             echo -e "\${DiskAvailable}"
             df -h \${i}
             echo
        done
    done
}

function freeipa_memory_precheck ()
{
    free --human --wide --total
    echo
}

function freeipa_cpu_precheck_report()
{
    iostat -c
    CPU_USAGE=\$(echo "scale=2; 100 - \$(iostat -c | awk '/[0-9]\$/ {print \$NF}')" | bc)
    echo -e "CPU Usage (%used -> \${CPU_USAGE})\n"
}

function freeipa_forward_dns_report ()
{
    for MINION_NODE in \$(salt-key --out json 2>/dev/null | jq -r '.minions[]')
    do
        host -t A \${MINION_NODE} 2>/dev/null
        echo
    done
}

function freeipa_reverse_dns_report ()
{
    for MINION_NODE in \$(salt-key --out json 2>/dev/null | jq -r '.minions[]')
    do
        host -t PTR \$(host -t A \${MINION_NODE} 2>/dev/null | awk '{print \$NF}') 2>/dev/null
        echo
    done
}

function freeipa_check_nginx_report ()
{
    salt '*' cmd.run 'cat /etc/nginx/nginx.conf && md5sum /etc/nginx/nginx.conf' 2>/dev/null
}

function freeipa_test_backup_report ()
{
    /usr/local/bin/freeipa_backup -p 2>/dev/null
    echo -e '\nLatest backups:\n'
    tail -n1  /var/log/ipabackup_status_hourly.json  | jq -r '[.time, .status, .message]|@csv'
}

function freeipa_cipa_state_report ()
{
    /usr/local/bin/cipa -d \$(hostname -d) -W \$(tail -n +2 /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
}

function freeipa_create_ldap_conflict_file ()
{
    ldapsearch -H ldap://\${LDAP_SRV} -o ldif-wrap=no -D "\${BIND_DN}" -w \${PW} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict > \${LDAP_CONFLICTS_FILE} 2>/dev/null
}

function freeipa_get_user_group_in_conflicts ()
{
    ldapsearch -H ldap://\${LDAP_SRV} -o ldif-wrap=no -D "\${BIND_DN}" -w \${PW} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict
    ldapsearch -H ldap://\${LDAP_SRV} -o ldif-wrap=no -D "\${BIND_DN}" -w \${PW} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict | awk -F '[ |=|,]' '/nsds5ReplConflict.*cn=users/ || /nsds5ReplConflict.*cn=groups/ {print \$5}' | sort -u
}

function freeipa_get_idns_in_conflicts ()
{
    ldapsearch -H ldap://\${LDAP_SRV} -o ldif-wrap=no -D "\${BIND_DN}" -w \${PW} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict
    ldapsearch -H ldap://\${LDAP_SRV} -o ldif-wrap=no -D "\${BIND_DN}" -w \${PW} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict | awk -F '[ |=|,]' '/nsds5ReplConflict.*idnsName=/ {print \$5}' | sort -u
}

function freeipa_ldap_conflicts_check ()
{
    LDAP_CONFLICTS_CHECK=\$(/usr/local/bin/cipa -d \$(hostname -d) -W \$(tail -n +2 /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password') | awk '/LDAP Conflicts/ {print \$5,\$7,\$9}' | grep 0 >/dev/null 2>&1 && echo \$?)
    if [[ \${LDAP_CONFLICTS_CHECK} -eq 0 ]]
    then
        echo -e "No FreeIPA LDAP Conflicts\n"
    else
        echo -e "\nFreeIPA LDAP Conflicts [\FAILED\]\n"
        USER_GROUP_LDAP_CONFLICT=\$(ldapsearch -H ldap://\${LDAP_SRV} -o ldif-wrap=no -D "\${BIND_DN}" -w \${PW} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict | awk -F '[ |=|,]' '/nsds5ReplConflict.*cn=users/ || /nsds5ReplConflict.*cn=groups/ {print \$5}' | sort -u | wc -l)
        if [[ \${USER_GROUP_LDAP_CONFLICT} -ne 0 ]]
        then
            echo -e "\Users or Groups in Conflict\"
            freeipa_get_user_group_in_conflicts
        else
            echo -e "\Hosts entries in Conflict\"
            freeipa_get_idns_in_conflicts
        fi
    fi
}

function freeipa_replication_agreements_report ()
{
    for REPLICA in \$(ipa-replica-manage list | awk '{print \$1}' | tr -d ":")
    do
        echo -e "\${REPLICA}:\n"
        ipa-replica-manage -v list \${REPLICA}
        echo
    done
}

function freeipa_check_saltuser_password_rotation_report ()
{
    export CURRENT_TIME="\$(TZ=GMT date '+%b %d, %Y')"
    export ENVIRONMENT_NAME=\$(salt-call pillar.get "telemetry:clusterName" --out=json 2>/dev/null | jq '.local' | sed -e 's|"||g' -e 's|-freeipa||')
    TenantID=\$(salt-call pillar.get "tags:Cloudera-Environment-Resource-Name" 2>/dev/null | awk -F":" '/crn/ {print \$5}')
    set -- \$(chage -l saltuser | awk -F":" "/Password expires/ {print \\\$NF}" 2>/dev/null)
    SALTUSER_CHAGE_TIME="\${1} \${2} \${3}"
    if [[ \${CURRENT_TIME} > \${SALTUSER_CHAGE_TIME} ]]
    then
        echo -e "saltuser valid password [FAILED]\n"
        chage -l saltuser 2>/dev/null
        echo -e "\nDouble-check the Entitlement CDP_ROTATE_SALTUSER_PASSWORD for this Tenant: \${TenantID}"
        echo -e "Once the Entitlement is granted use:\ncdp environments rotate-salt-password --environment \${ENVIRONMENT_NAME}\n"
    else
        echo -e "\nsaltuser valid password [PASS]\n"
        chage -l saltuser 2>/dev/null
        echo
    fi
}

function freeipa_is_ccm_enabled ()
{
    if ! cdp-doctor ccm status >/dev/null 2>&1
    then
        return 1
    else
        return 0
    fi
}

function freeipa_ccm_network_status_report ()
{
    cdp-doctor network status
    echo
}

function freeipa_ccm_report ()
{
    freeipa_is_ccm_enabled
    if [[ \$? == 0 ]]
    then
        cdp-doctor ccm status
    else
        echo -e "\nCCM is not enabled\n"
    fi
    echo
}

function main_report ()
{
    echo -e "\n###################################################################################################"
    echo -e "01 | REQUIRED SERVICES RUNNING \$(hostname -f)"
    echo -e "###################################################################################################\n"

    echo -e "\n[01|01] FreeIPA Required Services\n"
    freeipa_services_running_report
    echo -e "\n[01|02] FreeIPA Status\n"
    freeipa_status_report
    echo -e "\n[01|03] CDP Node Status Monitor for VMs\n"
    freeipa_cdp_nsm_report

    echo -e "\n###################################################################################################"
    echo -e "02 | REQUIRED PORTS LISTENING \$(hostname -f)"
    echo -e "###################################################################################################\n"

    echo -e "\n[02|01] FreeIPA Listenig Ports\n"
    freeipa_checkports_report


    echo -e "\n###################################################################################################"
    echo -e "03 | FREEIPA HEALTH AGENT \$(hostname -f)"
    echo -e "###################################################################################################\n"

    echo -e "\n[03|01] FreeIPA Health Agent Service\n"
    freeipa_health_agent

    echo -e "\n###################################################################################################"
    echo -e "04 | OPERATING SYSTEM \$(hostname -f)"
    echo -e "###################################################################################################\n"

    echo -e "\n[04|01] Disk Space Used\n"
    freeipa_disk_precheck_report
    echo -e "\n[04|02] Memory Used\n"
    freeipa_memory_precheck
    echo -e "\n[04|03] CPU Used\n"
    freeipa_cpu_precheck_report
    echo -e "\n[04|04] Forward DNS Test\n"
    freeipa_forward_dns_report
    echo -e "\n[04|05] Reverse DNS Test\n"
    freeipa_reverse_dns_report
    echo -e "\n[04|06] Reviewing /etc/nginx/nginx.conf\n"
    freeipa_check_nginx_report

    echo -e "\n###################################################################################################"
    echo -e "05 | FREEIPA BACKUPS \$(hostname -f)"
    echo -e "###################################################################################################\n"

    echo -e "\n[05|01] FreeIPA Cloud Backups\n"
    freeipa_test_backup_report

    echo -e "\n###################################################################################################"
    echo -e "06 | FREEIPA REPLICATION \$(hostname -f)"
    echo -e "###################################################################################################\n"

    echo -e "\n[06|01] CIPA output\n"
    freeipa_cipa_state_report
    echo -e "\n[06|02] LDAP Conflicts\n"
    freeipa_ldap_conflicts_check
    echo -e "\n[06|03] Replication Agreements\n"
    freeipa_replication_agreements_report

    echo -e "\n###################################################################################################"
    echo -e "07 | ORCHESTRATION AND CONTROL PLANE CONNECTIVITY \$(hostname -f)"
    echo -e "###################################################################################################\n"

    echo -e "\n[07|01] saltuser has a valid password\n"
    freeipa_check_saltuser_password_rotation_report
    echo -e "\n[07|02] Control Plane Access\n"
    freeipa_ccm_network_status_report
    echo -e "\n[07|03] CCM Available\n"
    freeipa_ccm_report
}

export LDAP_CONFLICTS_FILE=/tmp/LDAP_CONFLICTS.txt
export LDAP_SRV=\$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.hosts[].fqdn' | tail -n 1)
export BIND_DN="cn=Directory Manager"
export PRINCIPAL=\$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.admin_user')
export PW=\$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
echo \${PW} | kinit \${PRINCIPAL} >/dev/null 2>&1
source activate_salt_env
main_report
EOF
}

# Function: freeipa_forward_dns - Get FreeIPA hostname resolved using salt {{{1
#-----------------------------------------------------------------------
function freeipa_forward_dns ()
{
    salt '*' cmd.run '
    #!/bin/bash
    if host -t A $(hostname -f) >/dev/null 2>/dev/null
    then
        echo -e "Forward DNS test for $(hostname -f):$(hostname -I) [${GREEN}PASS${NC}]"
    else
        echo -e "Forward DNS test for $(hostname -f):$(hostname -I) [${RED}FAILED${NC}]"
    fi
    ' 2>/dev/null
}

# Function: freeipa_reverse_dns - Get FreeIPA IP resolved using salt {{{1
#-----------------------------------------------------------------------
function freeipa_reverse_dns ()
{
    salt '*' cmd.run '
    #!/bin/bash
    if host -t PTR $(hostname -I) >/dev/null 2>/dev/null
    then
        echo -e "Reverse DNS test for $(hostname -I):$(hostname -f) [${GREEN}PASS${NC}]"
    else
        echo -e "Reverse DNS test for $(hostname -I):$(hostname -f) [${RED}FAILED${NC}]"
    fi
    ' 2>/dev/null
}

# Function: freeipa_check_nginx - Validate md5sum for nginx config file {{{1
#-----------------------------------------------------------------------
function freeipa_check_nginx ()
{
    NGINX_FILE_STATE=$(salt '*' cmd.run 'md5sum /etc/nginx/nginx.conf' 2>/dev/null | awk '/nginx/ {print $1}' | sort -u | wc -l)
    if [[ ${NGINX_FILE_STATE} -eq 1 ]]
    then
        echo -e "Double-check nginx.conf [${GREEN}PASS${NC}]"
        echo -e "Please save locally a copy of ${RED}/etc/nginx/nginx.conf${NC}"
    else
        echo -e "\nDouble-check nginx.conf [${RED}FAILED${NC}]\n"
        salt '*' cmd.run 'md5sum /etc/nginx/nginx.conf' 2>/dev/null
    fi
}

# Function: freeipa_test_backup - Test FreeIPA backup is able to read/write in the cloud storage location {{{1
#-----------------------------------------------------------------------
function freeipa_test_backup ()
{
    BACKUP_EXECUTED=$(ls  $(awk -F "[=|\"]" '/\[backup_path\]=/ {print $(NF -1)}' /usr/local/bin/freeipa_backup) | wc -l)
    TEST_BACKUP_CMD=$(/usr/local/bin/freeipa_backup -p 2>/dev/null | grep '^Uploaded successfully' >/dev/null 2>&1 && echo $?)

    if [[ ${BACKUP_EXECUTED} -eq 0 ]] && [[ ${TEST_BACKUP_CMD} -eq 0 ]]
    then
        echo -e "\n[05|01] FreeIPA Cloud Backups [${GREEN}PASS${NC}]\n"
        salt '*' cmd.run "
        #!/bin/bash
        if [[ -f /var/log/ipabackup_status_hourly.json ]]
        then
            echo -e 'Latest backups:'
            tail -n1  /var/log/ipabackup_status_hourly.json  | jq -r '[.time, .status, .message]|@csv'
        fi
        " 2>/dev/null
    else
        echo -e "\n[05|01] FreeIPA Cloud Backups [${RED}FAILED${NC}]\n"
        echo -e "Please double-check /var/log/ipabackup.log\n"
        tail -n 20 /var/log/ipabackup.log
    fi
}

# Function: freeipa_cipa_state - Check consistency across FreeIPA servers {{{1
#-----------------------------------------------------------------------
function freeipa_cipa_state ()
{
    CIPA_STATUS=$( /usr/local/bin/cipa -d $(hostname -d) -W $(tail -n +2 /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password') | sed -ne '3,$p' | awk '/[^\+-]/ {print $(NF -1)}' | sort -u | grep -v '|$' | wc -l)
    if [[  ${CIPA_STATUS} -eq 1 ]]
    then
        echo -e "FreeIPA Replication CIPA test [${GREEN}PASS${NC}]"
    else
        echo -e "\nFreeIPA Replication CIPA test [${RED}FAILED${NC}]\n"
        /usr/local/bin/cipa -d $(hostname -d) -W $(tail -n +2 /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    fi
}

# Function: freeipa_create_ldap_conflict_file - Create a file with LDAP conflicts {{{1
#-----------------------------------------------------------------------
function freeipa_create_ldap_conflict_file ()
{
    ldapsearch -H ldap://${LDAP_SRV} -o ldif-wrap=no -D "${BIND_DN}" -w ${PW} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict > ${LDAP_CONFLICTS_FILE} 2>/dev/null
}

# Function: freeipa_get_user_group_in_conflicts - Get User/Groups LDAP conflicts {{{1
#-----------------------------------------------------------------------
function freeipa_get_user_group_in_conflicts ()
{
    ldapsearch -H ldap://${LDAP_SRV} -o ldif-wrap=no -D "${BIND_DN}" -w ${PW} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict | awk -F '[ |=|,]' '/nsds5ReplConflict.*cn=users/ || /nsds5ReplConflict.*cn=groups/ {print $5}' | sort -u
}

# Function: freeipa_get_idns_in_conflicts - Get hosts LDAP conflicts {{{1
#-----------------------------------------------------------------------
function freeipa_get_idns_in_conflicts ()
{
    ldapsearch -H ldap://${LDAP_SRV} -o ldif-wrap=no -D "${BIND_DN}" -w ${PW} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict | awk -F '[ |=|,]' '/nsds5ReplConflict.*idnsName=/ {print $5}' | sort -u
}

# Function: freeipa_ldap_conflicts_check - Check and report if there are LDAP conflicts {{{1
#-----------------------------------------------------------------------
function freeipa_ldap_conflicts_check ()
{
    LDAP_CONFLICTS_CHECK=$(/usr/local/bin/cipa -d $(hostname -d) -W $(tail -n +2 /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password') | awk '/LDAP Conflicts/ {print $5,$7,$9}' | grep 0 >/dev/null 2>&1 && echo $?)
    if [[ ${LDAP_CONFLICTS_CHECK} -eq 0 ]]
    then
        echo -e "FreeIPA LDAP Conflicts [${GREEN}PASS${NC}]"
    else
        echo -e "\nFreeIPA LDAP Conflicts [${RED}FAILED${NC}]\n"
        USER_GROUP_LDAP_CONFLICT=$(ldapsearch -H ldap://${LDAP_SRV} -o ldif-wrap=no -D "${BIND_DN}" -w ${PW} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict | awk -F '[ |=|,]' '/nsds5ReplConflict.*cn=users/ || /nsds5ReplConflict.*cn=groups/ {print $5}' | sort -u | wc -l)
        if [[ ${USER_GROUP_LDAP_CONFLICT} -ne 0 ]]
        then
            echo -e "${RED}Users or Groups in Conflict${NC}"
            freeipa_get_user_group_in_conflicts
        else
            echo -e "${RED}Hosts entries in Conflict${NC}"
            freeipa_get_idns_in_conflicts
        fi
    fi
}

# Function: freeipa_replication_agreements - Check FreeIPA Replication Agreements {{{1
#-----------------------------------------------------------------------
function freeipa_replication_agreements ()
{
    # Status of replication between IPA servers
    FREEIPA_REPLICA_AGREEMENTS=$(for REPLICA in $(ipa-replica-manage list | awk '{print $1}' | tr -d ":"); do ipa-replica-manage -v list ${REPLICA}; echo ;done | awk '/last update status:/' | sort -u)
    # last update status: Error (0) Replica acquired successfully: Incremental update succeeded
    if [[  ${FREEIPA_REPLICA_AGREEMENTS} =~ succeeded$ ]]
    then
        echo -e "FreeIPA Replication Agreements [${GREEN}PASS${NC}]"
    else
        echo -e "\nFreeIPA Replication Agreements [${RED}FAILED${NC}]\n"
        for IPA_NODE in $(ipa-replica-manage list | awk '{print $1}' | tr -d ":")
        do
            echo -e "${YELLOW}${IPA_NODE}${NC}\n"
            ipa-replica-manage -v list ${IPA_NODE}
            echo
        done
    fi
}

# Function: freeipa_check_saltuser_password_rotation - Validate Salt User Valid Password {{{1
#-----------------------------------------------------------------------
function freeipa_check_saltuser_password_rotation ()
{
    set -- $(salt '*' cmd.run "chage -l saltuser | awk -F":" '/Password expires/ {print \$NF}'"  2>/dev/null |  grep -v 'cloudera\.site' | sort -u)
    export CURRENT_TIME="$(TZ=GMT date '+%b %d, %Y')"
    export ENVIRONMENT_NAME=$(salt-call pillar.get "telemetry:clusterName" --out=json 2>/dev/null | jq '.local' | sed -e 's|"||g' -e 's|-freeipa||')
    TenantID=$(salt-call pillar.get "tags:Cloudera-Environment-Resource-Name" 2>/dev/null | awk -F":" '/crn/ {print $5}')
    while (( $# ))
    do
        SALTUSER_CHAGE_TIME=="${1} ${2}, ${3}"
        if [[ ${CURRENT_TIME} > ${SALTUSER_CHAGE_TIME} ]]
        then
            echo -e "\nsaltuser valid password [${RED}FAILED${NC}]\n"
            salt '*' cmd.run "chage -l saltuser | awk -F":" '/Password expires/'"  2>/dev/null
            echo -e "\nPassword expires <<$1 $2 $3>>"
            echo -e "It is required to rotate the saltuser password"
            echo -e "Create a Support Ticket and ask for help to enable the Entitlement ${RED}CDP_ROTATE_SALTUSER_PASSWORD${NC} for this Tenant: ${RED}${TenantID}${NC}"
            echo -e "Once the Entitlement is granted use:\n${GREEN}cdp environments rotate-salt-password --environment ${ENVIRONMENT_NAME}${NC}\n"
        else
            echo -e "saltuser valid password [${GREEN}PASS${NC}]"
        fi
        shift 3
    done
}

# Function: freeipa_is_ccm_enabled - Check if CCM is enabled {{{1
#-----------------------------------------------------------------------
function freeipa_is_ccm_enabled ()
{
    if ! cdp-doctor ccm status >/dev/null 2>&1
    then
        return 1
    else
        return 0
    fi
}

# Function: freeipa_ccm_network_status - Double-check Control Plane Endpoint access {{{1
#-----------------------------------------------------------------------
function freeipa_ccm_network_status ()
{
    freeipa_is_ccm_enabled
    if [[ $? == 0 ]]
    then
        CONTROL_PLANE_CONN=$(cdp-doctor network status --format json | jq -r '.anyNeighboursAccessible, .ccmAccessible, .clouderaComAccessible, .databusAccessible, .databusS3Accessible, .archiveClouderaComAccessible, .serviceDeliveryCacheS3Accessible' | grep -v OK | wc -l)
        if [[ ${CONTROL_PLANE_CONN} == 0 ]]
        then
            echo -e "Control Plane Access [${GREEN}PASS${NC}]\n"
        else
            echo -e "\nControl Plane Access [${RED}FAILED${NC}]\n"
            salt '*' cmd.run 'cdp-doctor network status' 2>/dev/null | sed -e 's/\?\[92m//g' -e 's/\?\[0m//g'
        fi
    else
        CONTROL_PLANE_CONN=$(cdp-doctor network status --format json | jq -r '.anyNeighboursAccessible, .clouderaComAccessible, .databusAccessible, .databusS3Accessible, .archiveClouderaComAccessible, .serviceDeliveryCacheS3Accessible' | grep -v OK | wc -l)
        if [[ ${CONTROL_PLANE_CONN} == 0 ]]
        then
            echo -e "Control Plane Access [${GREEN}PASS${NC}]"
        else
            echo -e "\nControl Plane Access [${RED}FAILED${NC}]\n"
            salt '*' cmd.run 'cdp-doctor network status' 2>/dev/null | sed -e 's/\?\[92m//g' -e 's/\?\[0m//g'
        fi
    fi
}

# Function: freeipa_ccm - Double-check CCM is working {{{1
#-----------------------------------------------------------------------
function freeipa_ccm ()
{
    freeipa_is_ccm_enabled
    if [[ $? == 0 ]]
    then
        # Check CCM network and service status
        if cdp-doctor ccm status | grep True >/dev/null 2>&1
        then
            echo -e "CCM Available [${GREEN}PASS${NC}]\n"
        else
            echo -e "\nCCM Available [${RED}FAILED${NC}]\n"
            salt '*' cmd.run 'cdp-doctor ccm status' 2>/dev/null | sed -e 's/\?\[92m//g' -e 's/\?\[0m//g' | grep -v Connectivity
        fi
    else
        echo -e "CCM is not enabled\n"
    fi
}

# Function: freeipa_md5sum_groups - Double-check if all FreeIPA nodes have the same group list {{{1
#-----------------------------------------------------------------------
function freeipa_md5sum_groups ()
{
salt '*' cmd.run '
    #!/bin/bash
    PRINCIPAL=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.admin_user') 
    PW=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    echo ${PW} | kinit ${PRINCIPAL} >/dev/null 2>&1
    ipa group-find --all | grep 'dn:' | md5sum
' 2>/dev/null
}

# Function: freeipa_md5sum_users - Double-check if all FreeIPA nodes have the same user list {{{1
#-----------------------------------------------------------------------
function freeipa_md5sum_users ()
{
salt '*' cmd.run '
    #!/bin/bash
    PRINCIPAL=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.admin_user') 
    PW=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    echo ${PW} | kinit ${PRINCIPAL} >/dev/null 2>&1
    ipa user-find --all | grep 'dn:' | md5sum
' 2>/dev/null
}

# Function: freeipa_duplicated_forward_dns_entries - Query DNS for duplicated A Records {{{1
#-----------------------------------------------------------------------
function freeipa_duplicated_forward_dns_entries ()
{
    set -- $(ipa server-find --pkey-only  |  awk -F "[:]" '/Server/ {print "host -t A"$NF}' | bash | awk '{print $NF}')
    FREEIPA_DOMAIN=$(salt-call pillar.get freeipa:domain --out=json 2>/dev/null | jq -r '.local')
    for DNS_FORWARD_ZONE in $(ipa dnszone-find | awk -F":" '/Zone/ &&  $0 !~ /arpa/ {print $2}' | sed 's/ //g')
    do
        for A_RECORD in $(ipa dnsrecord-find ${DNS_FORWARD_ZONE} | awk -F ":" '/Record.*[0-9]+/ || /Record.*ipa\-/ || /Record.*ipaserver/ || /A record/' | awk -F ":" '/Record.*name/ {print $NF}' | sed 's/ //g')
        do
            if [[ ${A_RECORD} == ipa-ca ]]
            then
                #ipa-ca should respond to the same ipa server records
                if [[ $(host -t A ipa-ca | wc -l) == $(ipa server-find --pkey-only  |  awk -F "[:]" '/Server/ {print "host -t A"$NF}' | bash | awk '{print $NF}' | wc -l) ]]
                then
                    echo -e "${A_RECORD}.${FREEIPA_DOMAIN} [${GREEN}PASS${NC}]"
                else
                    echo -e "${A_RECORD}.${FREEIPA_DOMAIN} [${RED}FAILED${NC}]"
                fi
            else
                # Needs to report only one entry
                # host -t A ${A_RECORD}
                if [[ $(host -t A ${A_RECORD} | grep 'has address' | wc -l) -eq 1 ]]
                then
                    echo -e "${A_RECORD}.${FREEIPA_DOMAIN} [${GREEN}PASS${NC}]"
                else
                    echo -e "${A_RECORD}.${FREEIPA_DOMAIN} [${RED}FAILED${NC}]"
                fi
            fi
        done
    done  
}

# Function: freeipa_duplicated_reverse_dns_entries - Query DNS for duplicated PTR Records {{{1
#-----------------------------------------------------------------------
function freeipa_duplicated_reverse_dns_entries ()
{
    T_STAMP=$(date +"%Y%m%d%H%M%S")
    for DNS_REVERSE_ZONE in $(ipa dnszone-find | awk -F":" '/Zone/ &&  /arpa/ {print $2}' | sed 's/ //g')
    do
        echo -e "\n${DNS_REVERSE_ZONE}\n"
        ipa dnsrecord-find ${DNS_REVERSE_ZONE} | awk -F ":" '/Record.*[0-9]+/ || /PTR record/' | awk -F":" '/PTR record:/ {print $NF}' | sed 's/ //g' > /tmp/dns-${T_STAMP}
        for PTR_RECORD in $(ipa dnsrecord-find ${DNS_REVERSE_ZONE} | awk -F ":" '/Record.*[0-9]+/ || /PTR record/' | awk -F":" '/PTR record:/ {print $NF}' | sed 's/ //g')
        do
            if [[ $(grep -c ${PTR_RECORD} /tmp/dns-${T_STAMP}) -eq 1 ]]
            then
                echo -e "${PTR_RECORD} [${GREEN}PASS${NC}]"
            else
                echo -e "\n${PTR_RECORD} [${RED}FAILED${NC}]\n"
                ipa dnsrecord-find ${DNS_REVERSE_ZONE} | grep --color -B1 "${PTR_RECORD}"
            fi
        done
    done
    rm -rf /tmp/dns-${T_STAMP}
}

# Function: freeipa_fd_per_proc - Get FD used vs Configured for FreeIPA services {{{1
#-----------------------------------------------------------------------
function freeipa_fd_per_proc ()
{

}

# Function: menu_ppal - Show the Principal Menu {{{1
#-----------------------------------------------------------------------
function menu_ppal ()
{
    PS3="Please select an option [-> For Menu Press Enter]: "
    FREEIPA_DOMAIN=$(salt-call pillar.get freeipa:domain --out=json 2>/dev/null | jq -r '.local')
    echo -e "\n#== FREEIPA Health Check for ${FREEIPA_DOMAIN} ==#\n"
    select ANSWER in "FreeIPA Node Health Check" "FreeIPA Support Report" "Exit"
    do
        case ${ANSWER} in
        "FreeIPA Node Health Check")
            main_health_check
        ;;
        "FreeIPA Support Report")
            echo -e "\n... Preparing the Support Health Check Report ...\n"
            do_spin &
            SPIN_PID=$!
            # /tmp/freeipa_functions_create_report.sh is created once the script is executed. This file will be deleted upon the EXIT signal is received
            T_STAMP=$(date +"%Y%m%d%H%M%S")
            salt '*' cmd.run 'bash /tmp/freeipa_functions_create_report.sh' 2>/dev/null | tee -a /tmp/FreeIPA_Support_Bundle-$(hostname -f)_${T_STAMP}.out
            kill -9 $SPIN_PID 2>/dev/null
            wait $SPIN_PID >/dev/null 2>&1
            echo -e "\n... Please create a Support Ticket and attach to it -> /tmp/FreeIPA_Support_Bundle-$(hostname -f)_${T_STAMP}.out <-...\n"
        ;;
        "Exit")
            echo -e "\n===> ${BLUE}Restoring Default Configuration${NC} <===\n"
            do_spin &
            SPIN_PID=$!
            recover_default_salt_master_conf
            kill -9 $SPIN_PID 2>/dev/null
            wait $SPIN_PID >/dev/null 2>&1
            exit 0
        ;;
        *) echo -e "\nInvalid option, please try again. [For Menu Press Enter]:\n"
        esac
    done
}

# Function: menu_ppal - Run local Healt Check {{{1
#-----------------------------------------------------------------------
function main_health_check ()
{
    echo -e "\n===> ${BLUE}FreeIPA Health Checks${NC} <===\n"

    echo -e "###################################################################################################"
    echo -e "01 | REQUIRED SERVICES RUNNING <<$(hostname -f)>>"
    echo -e "###################################################################################################"

    #echo -e "${GREEN}Are the required services running? ${NC}"
    #echo -e "\n[01-FreeIPA] Related services running\n"
    echo -e "\n${YELLOW}[01|01] FreeIPA Required Services${NC}\n"
    do_spin &
    SPIN_PID=$!
    freeipa_services_running
    kill -9 $SPIN_PID 2>/dev/null
    wait $SPIN_PID >/dev/null 2>&1

    #echo  -e "\n[02-FreeIPA] services status"
    echo -e "\n${YELLOW}[01|02] FreeIPA Status${NC}\n"
    do_spin &
    SPIN_PID=$!
    freeipa_status
    kill -9 $SPIN_PID 2>/dev/null
    wait $SPIN_PID >/dev/null 2>&1

    #echo -e "\n[03-FreeIPA] CDP Node Status Monitor for Virtual Machines\n"
    echo -e "\n${YELLOW}[01|03] CDP Node Status Monitor for VMs${NC}\n"
    freeipa_cdp_nsm

    #echo -e "\n${GREEN}LISTENING State all the Required Network Ports${NC}\n"
    echo -e "###################################################################################################"
    echo -e "02 | REQUIRED PORTS LISTENING <<$(hostname -f)>>"
    echo -e "###################################################################################################"
    do_spin &
    SPIN_PID=$!
    freeipa_checkports
    kill -9 $SPIN_PID 2>/dev/null
    wait $SPIN_PID >/dev/null 2>&1

    echo -e "\n###################################################################################################"
    echo -e "03 | FREEIPA HEALTH AGENT <<$(hostname -f)>>"
    echo -e "###################################################################################################"

    echo -e "\n${YELLOW}[03|01] FreeIPA Health Agent Service${NC}\n"
    freeipa_health_agent

    echo -e "\n###################################################################################################"
    echo -e "04 | OPERATING SYSTEM <<$(hostname -f)>>"
    echo -e "###################################################################################################"

    #echo -e "\n${GREEN}OS Validations\n${NC}"

    for FILES_TO_RUN in ${FILES2EXEC_HEALTHCHECK}
    do
        # Execute the script in IPA Nodes
        salt -C 'E@.*(ipa).*' cmd.run "bash /tmp/${FILES_TO_RUN}" 2>/dev/null
    done

    #echo -e "\n[04-FreeIPA] - Forward DNS\n"
    echo -e "\n${YELLOW}[04|04] Forward DNS Test${NC}\n"
    freeipa_forward_dns
    echo -e "\n${YELLOW}[04|05] Reverse DNS Test${NC}\n"
    #echo -e "\n[05-FreeIPA] - Reverse DNS\n"
    freeipa_reverse_dns
    echo -e "\n${YELLOW}[04|06] Reviewing /etc/nginx/nginx.conf${NC}\n"
    #echo -e "\n[06-FreeIPA] - NGINX Validation\n"
    freeipa_check_nginx

    echo -e "\n###################################################################################################"
    echo -e "05 | FREEIPA BACKUPS <<$(hostname -f)>>"
    echo -e "###################################################################################################"

    #echo -e "\n${GREEN} Are FreeIPA Backups to the Cloud Working? ${NC}\n"
    freeipa_test_backup


    echo -e "\n###################################################################################################"
    echo -e "06 | FREEIPA REPLICATION <<$(hostname -f)>>"
    echo -e "###################################################################################################"

    #echo -e "\n${GREEN}FreeIPA Replication${NC}\n"
    echo -e "\n${YELLOW}[06|01] CIPA output${NC}\n"
    freeipa_cipa_state

    echo -e "\n${YELLOW}[06|02] LDAP Conflicts${NC}\n"
    freeipa_create_ldap_conflict_file
    freeipa_ldap_conflicts_check

    echo -e "\n${YELLOW}[06|03] Replication Agreements${NC}\n"
    do_spin &
    SPIN_PID=$!
    freeipa_replication_agreements
    kill -9 $SPIN_PID 2>/dev/null
    wait $SPIN_PID >/dev/null 2>&1

    echo -e "\n###################################################################################################"
    echo -e "07 | ORCHESTRATION AND CONTROL PLANE CONNECTIVITY <<$(hostname -f)>>"
    echo -e "###################################################################################################"

    echo -e "\n${YELLOW}[07|01] saltuser has a valid password${NC}\n"
    do_spin &
    SPIN_PID=$!
    freeipa_check_saltuser_password_rotation
    kill -9 $SPIN_PID 2>/dev/null
    wait $SPIN_PID >/dev/null 2>&1

    echo -e "\n${YELLOW}[07|02] Control Plane Access${NC}\n"
    do_spin &
    SPIN_PID=$!
    freeipa_ccm_network_status
    kill -9 $SPIN_PID 2>/dev/null
    wait $SPIN_PID >/dev/null 2>&1

    echo -e "${YELLOW}[07|03] CCM Available${NC}\n"
    freeipa_ccm
}

# Function: main - Run the required functions {{{1
#-----------------------------------------------------------------------
function main ()
{
    echo -e "\n===> ${BLUE}Preparing the Environment${NC} <===\n"
    do_spin &
    SPIN_PID=$!
    do_enable_minion2master_copy
    freeipa_create_remote_scripts
    # Get the list of ipa nodes
    set -- $(salt-key --out json 2>/dev/null | jq -r '.minions[]' | egrep 'ipa')
    for FILES_TO_COPY in ${FILES2COPY}
    do
        # Copy the scripts to IPA nodes
        salt-cp --chunked --list "$(echo $@ | sed 's| |,|g')" /home/cloudbreak/${FILES_TO_COPY} /tmp/${FILES_TO_COPY} >/dev/null 2>&1
    done
    kill -9 $SPIN_PID 2>/dev/null
    wait $SPIN_PID >/dev/null 2>&1

    clear
    menu_ppal
}

# Color Codes:
# ===========
# Black        0;30     Dark Gray     1;30
# Red          0;31     Light Red     1;31
# Green        0;32     Light Green   1;32
# Brown/Orange 0;33     Yellow        1;33
# Blue         0;34     Light Blue    1;34
# Purple       0;35     Light Purple  1;35
# Cyan         0;36     Light Cyan    1;36      
# Light Gray   0;37     White         1;37
# -------------------------------------------------------------------
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[0;33m'
export BLUE='\033[0;34m'
export NC='\033[0m' # No Color

# Need to run the script as the root user
if [[ $(id -u) -ne 0 ]]
then
    echo -e "You are not the -->> ${RED}root${NC} <<-- user. Please execute: >> ${GREEN}sudo -i${NC} << then execute ${GREEN}$0${NC} again"
    exit 1
fi

# No arguments allowed
if [[ $# -gt 0 ]] ; then
  echo -e "Invalid Syntax!"
  echo -e "The valid syntax is  ${GREEN}./$(basename $0)${NC}"
  exit 2
fi

clear
source activate_salt_env
# This is required for option 1 "Health Check locally"
export LDAP_CONFLICTS_FILE=/tmp/LDAP_CONFLICTS.txt
export FILES2COPY="freeipa_disk_precheck.sh freeipa_memory_precheck.sh freeipa_cpu_precheck.sh freeipa_functions_create_report.sh"
export FILES2EXEC_HEALTHCHECK="freeipa_disk_precheck.sh freeipa_memory_precheck.sh freeipa_cpu_precheck.sh"
export FILES2EXEC_REPORT="freeipa_functions_create_report.sh"
export LDAP_SRV=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.hosts[].fqdn' | tail -n 1)
export BIND_DN="cn=Directory Manager"
export PRINCIPAL=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.admin_user')
export PW=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
echo ${PW} | kinit ${PRINCIPAL} >/dev/null 2>&1
main