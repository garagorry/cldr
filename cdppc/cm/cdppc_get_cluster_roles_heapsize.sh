#!/usr/bin/env bash
#
# Description: Script to get the Heap Size for all Running Roles in a cluster using the CM API.
#              This script needs to run from the CM node as the root user (not using sudo).
#              Requires a Workload user and password.
#
# Access API DOC (STATIC)
# https://<<CM_FQDN>>/static/apidocs/index.html
#
# Date       Author               Description
# ---------- ------------------- ---------------------------------------------------------
# 05/04/2023 Jimmy Garagorry      Created
#==========================================================================================

# Function: do_spin - Create the spinner for long running processes {{{1
#-----------------------------------------------------------------------
function do_spin () {
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

# Function: do_test_credentials - Double-check credentials provided {{{1
#-----------------------------------------------------------------------
function do_test_credentials () {
curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/version" > /tmp/null 2>&1
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

# Function: do_get_roles_heapsize - Get Heap Size for Hadoop Services {{{1
#-----------------------------------------------------------------------
do_get_roles_heapsize () {
    CONT=0
    for CLUSTER_SERIVCE_NAME in $(curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/services"|jq -r '.items[].name')
    do
    #    echo ${CLUSTER_SERIVCE_NAME}
        for roleConfigName in $(curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERIVCE_NAME}/roleConfigGroups" | jq -r '.items[].name')
        do
            #echo ${roleConfigName}
            #curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERIVCE_NAME}/roleConfigGroups/${roleConfigName}" | jq -r '. | ((.config.items[] | select( .name | contains("heapsize"))|"\(.name) | \(.value)"))' 
            #curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERIVCE_NAME}/roleConfigGroups/${roleConfigName}" | jq -r '. | (.name, (.config.items[] | select( .name | contains("heapsize"))|"\(.name) | \(.value)"))'  | grep --color -B1 'heap.*[0-9]$'
            set -- $(curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERIVCE_NAME}/roleConfigGroups/${roleConfigName}" | jq -r '. | (.name, (.config.items[] | select( .name | contains("heap"))|"\(.name) \(.value)"))'  | grep --color -B1 'heap.*[0-9]$')
            for roleConfigValue in $@
            do
                roleConfigArray[${CONT}]=${roleConfigValue}
                (( CONT += 1 ))
            done 
        done
    done
    echo ${roleConfigArray[*]} | sort -u    
}

# Function: do_get_role_mgmt_heapsize - Get Heap Size for CM MGMT Services {{{1
#-----------------------------------------------------------------------
function do_get_role_mgmt_heapsize () {
  set -- $(curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleConfigGroups" | jq -r '.items[] | (.name, (.config.items[] | select( .name | contains("heap"))|"\(.name) \(.value)"))' | grep --color -B1 'heap.*[0-9]$')
  for roleConfigValue in $@
  do
      roleConfigArray[${CONT}]=${roleConfigValue}
      (( CONT += 1 ))
  done 
  echo ${roleConfigArray[*]} | sed 's|--||g' | sort -u
}

# Function: get_roles_running_supervisorctl - Get Roles running in all nodes using salt and supervisorctl {{{1
#-----------------------------------------------------------------------
function get_roles_running_supervisorctl () 
{
        source activate_salt_env
        salt '*' cmd.run 'echo exit | /opt/cloudera/cm-agent/bin/supervisorctl -c /var/run/cloudera-scm-agent/supervisor/supervisord.conf' 2>/dev/null
}

# Function: main - Call the actions {{{1
#-----------------------------------------------------------------------
function main () 
{
    run_as_root_check
    clear
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

    do_test_credentials

    if [[ ${CRED_VALIDATED} == 0 ]]
    then
        export CM_API_VERSION=$(curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/version")
    else
        exit 1
    fi

    export BLUE='\033[0;34m'
    export NC='\033[0m' # No Color

    echo -e "\n===> ${BLUE}<<< Getting Heap Size for Configured Roles in ${CM_CLUSTER_NAME} ... >>>${NC} <===\n"
    do_spin &
    SPIN_PID=$!
    set -- $(do_get_roles_heapsize)
    kill -9 $SPIN_PID >/dev/null 2>&1
    wait $SPIN_PID >/dev/null 2>&1

    while (( $# ))
    do
        #echo "$1 | $2 | $3"
        printf "%50s %35s %-20d \n" $1 $2 $3 
        shift 3
    done | sort -u -k 2,2
    echo

    echo -e "\n===> ${BLUE}<<< Getting Heap Size for MGMT Roles in ${CM_CLUSTER_NAME} ... >>>${NC} <===\n"
    do_spin &
    SPIN_PID=$!

    set -- $(do_get_role_mgmt_heapsize)
    kill -9 $SPIN_PID >/dev/null 2>&1
    wait $SPIN_PID >/dev/null 2>&1

    while (( $# ))
    do
        #echo "$1 | $2 | $3"
        printf "%50s %35s %-20d \n" $1 $2 $3 
        shift 3
    done | sort -u -k 2,2
    echo

    get_roles_running_supervisorctl
}
main
exit 0