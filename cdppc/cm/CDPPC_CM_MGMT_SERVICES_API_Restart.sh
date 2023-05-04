#!/usr/bin/env bash
#
# Description: Script to restart CM MGMT Services using the CM API.
#              This script needs to run from the CM node as the root user.
#              Requires a Workload user and password.
#
# Access API DOC (STATIC)
# https://<<CM_FQDN>>/static/apidocs/index.html
# 
# MgmtRoleCommandsResource:	
#   POST /cm/service/roleCommands/jmapDump
#   POST /cm/service/roleCommands/jmapHisto
#   POST /cm/service/roleCommands/jstack
#   POST /cm/service/roleCommands/lsof
#   POST /cm/service/roleCommands/restart
#   POST /cm/service/roleCommands/start
#   POST /cm/service/roleCommands/stop
#
# Date       Author               Description
# ---------- ------------------- ---------------------------------------------------------
# 04/26/2023 Jimmy Garagorry      Created
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

# Function: cluster_mgmt_service_stop - API Call to stop a CM MGMT service {{{1
#-----------------------------------------------------------------------
function cluster_mgmt_service_stop () 
{
  curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -d "{\"items\":[\"${MGMT_ROLE_TYPE}\"]}" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleCommands/stop"
}

# Function: cluster_mgmt_service_start - API Call to start a CM MGMT service {{{1
#-----------------------------------------------------------------------
function cluster_mgmt_service_start () 
{
  curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -d "{\"items\":[\"${MGMT_ROLE_TYPE}\"]}" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleCommands/start"
}

# Function: cluster_mgmt_service_restart - API Call to restart a CM MGMT service {{{1
#-----------------------------------------------------------------------
function cluster_mgmt_service_restart () 
{
  curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -d "{\"items\":[\"${MGMT_ROLE_TYPE}\"]}" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleCommands/restart"
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

    do_test_credentials

    if [[ ${CRED_VALIDATED} == 0 ]]
    then
    export CM_API_VERSION=$(curl ${CURL_OPTIONS}  -X GET "${CM_SERVER}/api/version")
    else
    exit 1
    fi

    for MGMT_ROLE in $(curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleConfigGroups" | jq -r '.items[].name')
    do
        for MGMT_ROLE_TYPE in $(curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleConfigGroups/${MGMT_ROLE}" | jq -r '.roleType')
        do
            PS3="What do you want to do for << ${MGMT_ROLE_TYPE^^} >> Service? [-> To get the Menu Press Enter]: "
            echo -e "\n#== CLUSTER: ${CM_CLUSTER_NAME} | SERVICE: ${MGMT_ROLE_TYPE^^} ==#\n"
            select ANSWER in "Start" "Stop" "Restart" "Next Service" "Restart All" "Exit"
            do
                case ${ANSWER} in
                    "Start")
                        cluster_mgmt_service_start
                        ;;
                    "Stop")
                        cluster_mgmt_service_stop
                        ;;
                    "Restart")
                        cluster_mgmt_service_restart
                        ;;
                    "Next Service")
                        break
                        ;;
                    "Restart All")
                        echo -e "\nRestarting:\n$(curl ${CURL_OPTIONS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleTypes"| jq -r '.[]')\n"
                        cluster_mgmt_service_restart_all
                        ;;
                    "Exit")
                        exit 0
                    ;;
                    *) 
                        echo -e "\nInvalid option, please try again. [-> To get the Menu Press Enter]:\n"
                esac
            done
        done
    done
}

clear
main
exit 0