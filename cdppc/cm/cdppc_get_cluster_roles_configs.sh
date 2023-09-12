#!/usr/bin/env bash
#
# Description: Script to get the Non Default values for all Running Roles in a cluster using the CM API.
#              This script needs to run from the CM node as the root user (not using sudo).
#              Requires a Workload user and password.
#
# Non-Default Values
# /clusters/{clusterName}/services/{serviceName}/config
# /clusters/{clusterName}/services/{serviceName}/roles/{roleName}/config
#
# Access API DOC (STATIC)
# https://<<CM_FQDN>>/static/apidocs/index.html
#
# Date       Author               Description
# ---------- ------------------- ---------------------------------------------------------
# 05/22/2023 Jimmy Garagorry      Created
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
    NC='\033[0m' # No Colors

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

# Function: do_get_roles_configs - Get Non Default values Per Services {{{1
#-----------------------------------------------------------------------
do_get_roles_configs () {
    for CLUSTER_SERIVCE_NAME in $(curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/services" | jq -r '.items[].name')
    do
        # Retrieves the configuration of a specific service.
        curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERIVCE_NAME}/config?view=summary"  | tee -a ${OUTPUT_DIR}/ServiceConfigs/$(hostname -f)_${CM_CLUSTER_NAME}_${CLUSTER_SERIVCE_NAME}_config.json
        for roleConfigName in $(curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERIVCE_NAME}/roleConfigGroups" | jq -r '.items[].name')
        do
            # Retrieves the configuration of a specific role.
            curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERIVCE_NAME}/roleConfigGroups/${roleConfigName}/config?view=summary" | tee -a ${OUTPUT_DIR}/roleConfigGroups/$(hostname -f)_${CM_CLUSTER_NAME}_${CLUSTER_SERIVCE_NAME}_${roleConfigName}_config.json
        done
    done
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
    export OUTPUT_DIR=/tmp/$(hostname -f)/$(date +"%Y%m%d%H%M%S")

    do_test_credentials

    if [[ ${CRED_VALIDATED} == 0 ]]
    then
        export CM_API_VERSION=$(curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/version")
    else
        exit 1
    fi

    if [[ -d ${OUTPUT_DIR} ]]
    then
      rm -rf ${OUTPUT_DIR}
      mkdir -p ${OUTPUT_DIR}/{ServiceConfigs,roleConfigGroups}
    else
      mkdir -p ${OUTPUT_DIR}/{ServiceConfigs,roleConfigGroups}
    fi

    do_get_roles_configs
}

ps -eo pid,user,command | grep $(systemctl status cloudera-scm-server | awk '/Main PID:/ {print $3}') | egrep -v "grep|proc_watcher" | fgrep 'com.cloudera.api.redaction' >/dev/null 2>&1
if [[ $? -eq 0 ]]
then
    main
    echo -e "\n\nPlease review the information at:\n"
    ls -lrdth ${OUTPUT_DIR}/{ServiceConfigs,roleConfigGroups}
    echo
    exit 0
else 
    clear
    echo -e "To get the values from Cloudera Manager configs please complete these steps first.\n"
    cat <<EOF
##############################################################################

    1) cp /etc/default/cloudera-scm-server /etc/default/cloudera-scm-server_\$(date +"%Y%m%d%H%M%S").orig
    2) Edit the /etc/default/cloudera-scm-server file by adding the following property <<-Dcom.cloudera.api.redaction=false>> (separate each property with a space) to the line that begins with export CMF_JAVA_OPTS.
    # Example: 
    # export CMF_JAVA_OPTS="-Xmx4G -XX:MaxPermSize=256m -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp -Dcom.sun.management.jmxremote.ssl.enabled.protocols=TLSv1.2 -Dcom.cloudera.api.redaction=false"
    3) Restart Cloudera Manager Server
    systemctl restart cloudera-scm-server; tail -f /var/log/cloudera-scm-server/cloudera-scm-server.log | grep -i 'started jetty server'
    4) Execute the script => $0 again

##############################################################################
EOF
echo
fi
