# Functions to get the FreeIPA status #
#
# Function: freeipa_status - Validates FreeIPA services across the IPA nodes {{{1
#-----------------------------------------------------------------------
function freeipa_status ()
{
    source activate_salt_env
    EXIT_COUNT=$(salt '*' cmd.run 'ipactl status' 2>/dev/null | egrep -v 'successful|RUNNING|cloudera\.site' | wc -l)
    if [[ ${EXIT_COUNT} != 0 ]]
    then
        echo -e "Expected Services are running [${RED}FAILED${NC}]\n"
        salt '*' cmd.run 'ipactl status' 2>/dev/null
    else
        echo -e "Expected services are running [${GREEN}PASS${NC}]\n"
        salt '*' cmd.run 'ipactl status' 2>/dev/null
    fi
    deactivate
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
        echo -e "FreeIPA Replication CIPA test [${GREEN}PASS${NC}]\n"
        /usr/local/bin/cipa -d $(hostname -d) -W $(tail -n +2 /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    else
        echo -e "\nFreeIPA Replication CIPA test [${RED}FAILED${NC}]\n"
        /usr/local/bin/cipa -d $(hostname -d) -W $(tail -n +2 /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    fi
}
# Function: freeipa_create_ldap_conflict_file - Create a file with LDAP conflicts {{{1
#-----------------------------------------------------------------------
function freeipa_create_ldap_conflict_file ()
{
    LDAP_CONFLICTS_FILE=/tmp/LDAP_CONFLICTS.txt
    LDAP_SRV=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.hosts[].fqdn' | tail -n 1)
    BIND_DN="cn=Directory Manager"
    PW=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    ldapsearch -H ldap://${LDAP_SRV} -o ldif-wrap=no -D "${BIND_DN}" -w ${PW} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict > ${LDAP_CONFLICTS_FILE} 2>/dev/null
}
# Function: freeipa_get_user_group_in_conflicts - Get User/Groups LDAP conflicts {{{1
#-----------------------------------------------------------------------
function freeipa_get_user_group_in_conflicts ()
{
    LDAP_SRV=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.hosts[].fqdn' | tail -n 1)
    BIND_DN="cn=Directory Manager"
    PW=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    ldapsearch -H ldap://${LDAP_SRV} -o ldif-wrap=no -D "${BIND_DN}" -w ${PW} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict | awk -F '[ |=|,]' '/nsds5ReplConflict.*cn=users/ || /nsds5ReplConflict.*cn=groups/ {print $5}' | sort -u
}
# Function: freeipa_get_idns_in_conflicts - Get hosts LDAP conflicts {{{1
#-----------------------------------------------------------------------
function freeipa_get_idns_in_conflicts ()
{
    LDAP_SRV=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.hosts[].fqdn' | tail -n 1)
    BIND_DN="cn=Directory Manager"
    PW=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    ldapsearch -H ldap://${LDAP_SRV} -o ldif-wrap=no -D "${BIND_DN}" -w ${PW} "(&(objectClass=ldapSubEntry)(nsds5ReplConflict=*))" \* nsds5ReplConflict | awk -F '[ |=|,]' '/nsds5ReplConflict.*idnsName=/ {print $5}' | sort -u
}
# Function: freeipa_ldap_conflicts_check - Check and report if there are LDAP conflicts {{{1
#-----------------------------------------------------------------------
function freeipa_ldap_conflicts_check ()
{
    LDAP_SRV=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.hosts[].fqdn' | tail -n 1)
    BIND_DN="cn=Directory Manager"
    PW=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
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
    PRINCIPAL=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.admin_user') 
    PW=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    echo ${PW} | kinit ${PRINCIPAL} >/dev/null 2>&1
    # Status of replication between IPA servers
    FREEIPA_REPLICA_AGREEMENTS=$(for REPLICA in $(ipa-replica-manage list | awk '{print $1}' | tr -d ":"); do ipa-replica-manage -v list ${REPLICA}; echo ;done | awk '/last update status:/' | sort -u)
    # last update status: Error (0) Replica acquired successfully: Incremental update succeeded
    if [[  ${FREEIPA_REPLICA_AGREEMENTS} =~ succeeded$ ]]
    then
        echo -e "FreeIPA Replication Agreements [${GREEN}PASS${NC}]\n"
        for IPA_NODE in $(ipa-replica-manage list | awk '{print $1}' | tr -d ":")
        do
            echo -e "${YELLOW}${IPA_NODE}${NC}\n"
            ipa-replica-manage -v list ${IPA_NODE}
            echo
        done
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
# Function: freeipa_md5sum_groups - Double-check if all FreeIPA nodes have the same group list {{{1
#-----------------------------------------------------------------------
function freeipa_md5sum_groups ()
{
    source activate_salt_env  
    salt '*' cmd.run '
        #!/bin/bash
        PRINCIPAL=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.admin_user') 
        PW=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
        echo ${PW} | kinit ${PRINCIPAL} >/dev/null 2>&1
        if [[ $(ipa config-show | awk "/Search size limit:/ {print \$NF}") == 100 ]]
        then
            ipa config-mod --searchrecordslimit=10000 >/dev/null 2>&1
            ipa group-find --all | grep 'dn:' | md5sum
        else
            ipa group-find --all | grep 'dn:' | md5sum
        fi
    ' 2>/dev/null
    deactivate
}
# Function: freeipa_md5sum_users - Double-check if all FreeIPA nodes have the same user list {{{1
#-----------------------------------------------------------------------
function freeipa_md5sum_users ()
{
    source activate_salt_env
    salt '*' cmd.run '
        #!/bin/bash
        PRINCIPAL=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.admin_user') 
        PW=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
        echo ${PW} | kinit ${PRINCIPAL} >/dev/null 2>&1
        if [[ $(ipa config-show | awk "/Search size limit:/ {print \$NF}") == 100 ]]
        then
            ipa config-mod --searchrecordslimit=10000 >/dev/null 2>&1
            ipa user-find --all | grep 'dn:' | md5sum
        else
            ipa user-find --all | grep 'dn:' | md5sum
        fi
    ' 2>/dev/null
    deactivate
}
# Function: freeipa_duplicated_forward_dns_entries - Query DNS for duplicated A Records {{{1
#-----------------------------------------------------------------------
function freeipa_duplicated_forward_dns_entries ()
{
    source activate_salt_env
    PRINCIPAL=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.admin_user') 
    PW=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    echo ${PW} | kinit ${PRINCIPAL} >/dev/null 2>&1
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
    deactivate
}
# Function: freeipa_duplicated_reverse_dns_entries - Query DNS for duplicated PTR Records {{{1
#-----------------------------------------------------------------------
function freeipa_duplicated_reverse_dns_entries ()
{
    PRINCIPAL=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.admin_user') 
    PW=$(sed '1d' /srv/pillar/freeipa/init.sls | jq -r '.freeipa.password')
    echo ${PW} | kinit ${PRINCIPAL} >/dev/null 2>&1
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
