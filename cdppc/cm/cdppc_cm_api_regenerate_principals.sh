#!/usr/bin/env bash
#
# Description: Script to renew Kerberos Principals using the CM API.
#              This script needs to run from the CM node as the root user.
#              Requires a Workload user and password.
#
# Access API DOC (STATIC)
# https://<<CM_FQDN>>/static/apidocs/index.html
#
# Date       Author               Description
# ---------- ------------------- ---------------------------------------------------------
# 06/06/2023 Jimmy Garagorry      Created
#==========================================================================================

# Function: do_test_credentials - Double-check credentials provided {{{1
#-----------------------------------------------------------------------
function do_test_credentials () 
{
  curl ${CURL_OPTIONS} -X GET "${CM_SERVER}/api/version" > /tmp/null 2>&1
  if grep "Bad credentials" /tmp/null > /dev/null 2>&1
  then
    CRED_VALIDATED=1
    echo -e "\n===> Please double-check the credentials provided <===\n"
    rm -rf /tmp/null 
  else
    CRED_VALIDATED=0
    rm -rf /tmp/null 
  fi
}

# Function: run_as_root_check - Double-check if root is executing the script {{{1
#-----------------------------------------------------------------------
function run_as_root_check () 
{
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color

    # Need to run the script as the root user
    if [[ $(id -u) -ne 0 ]]
    then
        echo -e "You are not the -->> ${RED}root${NC} <<-- user. Please execute: >> ${GREEN}sudo -i${NC} << then execute ${GREEN}$0${NC} again"
        exit 1
    fi
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

# Function: cluster_mgmt_service_restart_all - API Call to restart all CM MGMT services {{{1
#-----------------------------------------------------------------------
function cluster_mgmt_service_restart_all () 
{
    for MGMT_ROLE in $(curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleConfigGroups" | jq -r '.items[].name')
    do
        MGMT_ROLE_TYPE=$(curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleConfigGroups/${MGMT_ROLE}" | jq -r '.roleType')
        curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -d "{\"items\":[\"${MGMT_ROLE_TYPE}\"]}" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleCommands/restart"
    done
}

# Function: cluster_mgmt_service_stop_all - API Call to stop all CM MGMT services {{{1
#-----------------------------------------------------------------------
function cluster_mgmt_service_stop_all () 
{
    for MGMT_ROLE in $(curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleConfigGroups" | jq -r '.items[].name')
    do
        MGMT_ROLE_TYPE=$(curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleConfigGroups/${MGMT_ROLE}" | jq -r '.roleType')
        curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -d "{\"items\":[\"${MGMT_ROLE_TYPE}\"]}" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleCommands/stop"
    done
}

# Function: cluster_mgmt_service_start_all - API Call to start all CM MGMT services {{{1
#-----------------------------------------------------------------------
function cluster_mgmt_service_start_all () 
{
    for MGMT_ROLE in $(curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleConfigGroups" | jq -r '.items[].name')
    do
        MGMT_ROLE_TYPE=$(curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleConfigGroups/${MGMT_ROLE}" | jq -r '.roleType')
        curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -d "{\"items\":[\"${MGMT_ROLE_TYPE}\"]}" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleCommands/start"
    done
}

# Function: cluster_service_full_start - API Call to start all CM services {{{1
#-----------------------------------------------------------------------
function cluster_service_full_start () 
{
    curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/commands/start"
}

# Function: cluster_service_full_stop - API Call to stop all CM services {{{1
#-----------------------------------------------------------------------
function cluster_service_full_stop () 
{
    curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/commands/stop"
}

# Function: cluster_service_full_restart - API Call to restart all CM services {{{1
#-----------------------------------------------------------------------
function cluster_service_full_restart () 
{
    curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/commands/restart"
}

# Function: cluster_regenerate_kerberos_creds - API Call to Regenerate all Kerberos Credentials {{{1
#-----------------------------------------------------------------------
function cluster_regenerate_kerberos_creds () 
{
    # curl -X POST "http://<CM_SERVER_FQDN>:7180/api/v45/cm/commands/generateCredentials" -H "accept: application/json"
    curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/cm/commands/generateCredentials"
}

# Function: cluster_delete_kerberos_creds - API Call to delete existing Kerberos Credentials {{{1
#-----------------------------------------------------------------------
function cluster_delete_kerberos_creds () 
{
    # curl -k -u admin -X POST "https://$(hostname):7183/api/v33/clusters/CDH6.3.x/commands/deleteCredentials" -H "accept: application/json"
    curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/commands/deleteCredentials"
}

# Function: get_db_conn_parameters - Get DB details to use PSQL {{{1
#-----------------------------------------------------------------------
function get_db_conn_parameters () {
    export CM_SERVER_DB_FILE=/etc/cloudera-scm-server/db.properties
    export CM_DB_HOST=$(awk -F"=" '/db.host/ {print $NF}' ${CM_SERVER_DB_FILE})
    export CM_DB_NAME=$(awk -F"=" '/db.name/ {print $NF}' ${CM_SERVER_DB_FILE})
    export CM_DB_USER=$(awk -F"=" '/db.user/ {print $NF}' ${CM_SERVER_DB_FILE})
    export PGPASSWORD=$(awk -F"=" '/db.password/ {print $NF}' ${CM_SERVER_DB_FILE})
}

# Function: update_knox_state_on_local_cm_for_regenerate_keytabs - Update Knox State on CM DB  {{{1
#-----------------------------------------------------------------------
function update_knox_state_on_local_cm_for_regenerate_keytabs () 
{
    usermod --shell /bin/bash postgres
    su - postgres -c "export CM_SERVER_DB_FILE=/etc/cloudera-scm-server/db.properties
    export CM_DB_HOST=$(awk -F"=" '/db.host/ {print $NF}' ${CM_SERVER_DB_FILE})
    export CM_DB_NAME=$(awk -F"=" '/db.name/ {print $NF}' ${CM_SERVER_DB_FILE})
    export CM_DB_USER=$(awk -F"=" '/db.user/ {print $NF}' ${CM_SERVER_DB_FILE})
    export PGPASSWORD=$(awk -F"=" '/db.password/ {print $NF}' ${CM_SERVER_DB_FILE})
    echo \"UPDATE roles SET configured_status = 'STOPPED' WHERE name like 'knox%';\" | psql -h ${CM_DB_HOST} -U ${CM_DB_USER} -d ${CM_DB_NAME}" >/dev/null 2>&1
    usermod --shell /sbin/nologin postgres
}

# Function: update_knox_state_on_remote_cm_for_regenerate_keytabs - Update Knox State on Remote CM DB  {{{1
#-----------------------------------------------------------------------
function update_knox_state_on_remote_cm_for_regenerate_keytabs () 
{
    export CM_SERVER_DB_FILE=/etc/cloudera-scm-server/db.properties
    export CM_DB_HOST=$(awk -F"=" '/db.host/ {print $NF}' ${CM_SERVER_DB_FILE})
    export CM_DB_NAME=$(awk -F"=" '/db.name/ {print $NF}' ${CM_SERVER_DB_FILE})
    export CM_DB_USER=$(awk -F"=" '/db.user/ {print $NF}' ${CM_SERVER_DB_FILE})
    export PGPASSWORD=$(awk -F"=" '/db.password/ {print $NF}' ${CM_SERVER_DB_FILE})
    echo "UPDATE roles SET configured_status = 'STOPPED' WHERE name like 'knox%';" | psql -h ${CM_DB_HOST} -U ${CM_DB_USER} -d ${CM_DB_NAME} 2>/dev/null
}

# Function: update_cm_knox_state - Update Knox State to STOPPED state  {{{1
#-----------------------------------------------------------------------
function update_cm_knox_state () 
{
    if [[ $(awk -F'=' '/^com.cloudera.cmf.db.host=/ {print $NF}' /etc/cloudera-scm-server/db.properties) == $(hostname -f) ]]
    then    
        # If Postgres is running in the CM Node
        update_knox_state_on_local_cm_for_regenerate_keytabs
    else
        # If Postgres is running in the Cloud Provider (PaaS Postgres)
        update_knox_state_on_remote_cm_for_regenerate_keytabs
    fi
}

# Function: stop_knox_role_salt - Stop the Knox Role using supervisorctl  {{{1
#-----------------------------------------------------------------------
function stop_knox_role_salt () 
{
    source activate_salt_env
    salt '*' cmd.run 'echo stop $(echo exit | /opt/cloudera/cm-agent/bin/supervisorctl -c /var/run/cloudera-scm-agent/supervisor/supervisord.conf | awk "/knox/ { print \$1 }") | /opt/cloudera/cm-agent/bin/supervisorctl -c /var/run/cloudera-scm-agent/supervisor/supervisord.conf >/dev/null 2>&1' >/dev/null 2>&1
}

# Function: main - Call the actions {{{1
#-----------------------------------------------------------------------
function main () 
{
    run_as_root_check
    read -p "What is your Workload username: "  WORKLOAD_USER
    unset WORKLOAD_USER_PASS
    unset CHARTCOUNT
    echo -n "Enter your Workload user Password: "
    #stty -echo
    while IFS= read -r -n1 -s CHAR; do
        case "${CHAR}" in
        $'\0')
            break
            ;;
        $'\177')
            if [ ${#WORKLOAD_USER_PASS} -gt 0 ]; then
                echo -ne "\b \b"
                WORKLOAD_USER_PASS=${WORKLOAD_USER_PASS::-1}
            fi
            ;;
        *)
            CHARTCOUNT=$((CHARTCOUNT + 1))
            echo -n '*'
            WORKLOAD_USER_PASS+="${CHAR}"
            ;;
        esac
    done
    echo

    export CM_SERVER_DB_FILE=/etc/cloudera-scm-server/db.properties
    export CM_DB_HOST=$(awk -F"=" '/db.host/ {print $NF}' ${CM_SERVER_DB_FILE})
    export CM_DB_NAME=$(awk -F"=" '/db.name/ {print $NF}' ${CM_SERVER_DB_FILE})
    export CM_DB_USER=$(awk -F"=" '/db.user/ {print $NF}' ${CM_SERVER_DB_FILE})
    export PGPASSWORD=$(awk -F"=" '/db.password/ {print $NF}' ${CM_SERVER_DB_FILE})
    export CM_CLUSTER_NAME=$(echo -e "SELECT name FROM clusters;" | psql -h ${CM_DB_HOST} -U ${CM_DB_USER} -d ${CM_DB_NAME} | grep -v Proxy | tail -n 3 | head -n1| sed 's| ||g')
    export CM_SERVER="https://$(hostname -f):7183"
    export CURL_OPTIONS="-s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} --noproxy '*'"
    export PS3_M_PPAL="What option would you like to try [-> To get the Menu Press Enter]: "

    do_test_credentials

    if [[ ${CRED_VALIDATED} == 0 ]]
    then
        export CM_API_VERSION=$(curl ${CURL_OPTIONS}  -X GET "${CM_SERVER}/api/version")
    else
        exit 1
    fi
    
    clear
    
    PS3=${PS3_M_PPAL}
    echo -e "Working on Cluster: [${RED}${CM_CLUSTER_NAME}${NC}]\n"
    select ANSWER in "Stop All Cluster Services" "Start All Cluster Services" "Regenerate All Kerberos Credentials" "Exit"
    do
        case ${ANSWER} in
            "Stop All Cluster Services")
                clear
                echo -e "Stopping all Cluster services on: [${RED}${CM_CLUSTER_NAME}${NC}]\n"
                cluster_service_full_stop
                echo
                do_spin &
                SPIN_PID=$!
                sleep 30
                kill -9 $SPIN_PID 2>/dev/null
                wait $SPIN_PID >/dev/null 2>&1  
                echo -e "Stopping all MGMT services on: [${RED}${CM_CLUSTER_NAME}${NC}]\n"              
                cluster_mgmt_service_stop_all
                echo
                do_spin &
                SPIN_PID=$!
                sleep 10
                stop_knox_role_salt
                update_cm_knox_state
                echo
                kill -9 $SPIN_PID 2>/dev/null
                wait $SPIN_PID >/dev/null 2>&1 
                ;;
            "Start All Cluster Services")
                clear
                echo -e "Starting all Cluster services on: [${RED}${CM_CLUSTER_NAME}${NC}]\n"
                cluster_service_full_start
                echo
                do_spin &
                SPIN_PID=$!
                sleep 30
                kill -9 $SPIN_PID 2>/dev/null
                wait $SPIN_PID >/dev/null 2>&1  
                echo -e "Starting all MGMT services on: [${RED}${CM_CLUSTER_NAME}${NC}]\n" 
                cluster_mgmt_service_start_all
                ;;
            "Regenerate All Kerberos Credentials")
                clear
                cluster_delete_kerberos_creds
                echo
                do_spin &
                SPIN_PID=$!
                sleep 30
                cluster_regenerate_kerberos_creds
                echo
                do_spin &
                SPIN_PID=$!
                echo -e "Now start All services on: [${RED}${CM_CLUSTER_NAME}${NC}]\n" 
                ;;
            "Exit")
                exit 0
                ;;
            *) 
                echo "Invalid option, please try again. [-> To get the Menu Press Enter]:"
        esac
    done
}

clear

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

main
exit 0