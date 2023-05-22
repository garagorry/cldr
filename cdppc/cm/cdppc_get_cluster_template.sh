#!/usr/bin/env bash
#
# Description: Script to Export the Cluster Configuration using CM API.
#              This script needs to run from the CM node as the root user (not using sudo).
#              Requires a Workload user and password.
#
# This script considers:
# Disable redaction: The JSON file will contain all the configurations, including sensitive information and can be used to restore the cluster configuration.
# https://docs.cloudera.com/cloudera-manager/7.9.0/configuring-clusters/topics/cdpdc-exporting-cluster-configuration.html
#
# Access API DOC (STATIC)
# https://<<CM_FQDN>>/static/apidocs/index.html
#
# Date       Author               Description
# ---------- ------------------- ---------------------------------------------------------
# 05/22/2023 Jimmy Garagorry      Created
#==========================================================================================

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

# Function: do_get_cm_cluster_template - To create a cluster template {{{1
#-----------------------------------------------------------------------
do_get_cm_cluster_template () {
    # ?exportAutoConfig=true parameter to the command above to include configurations made by Autoconfiguration. These configurations are included for reference only and are not used when you import the template into a new cluster. 
    curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/export?exportAutoConfig=true" | tee -a ${OUTPUT_DIR}/$(hostname -f)_${CM_CLUSTER_NAME}_clustertemplate_autoconfig.json
    curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/export" | tee -a ${OUTPUT_DIR}/$(hostname -f)_${CM_CLUSTER_NAME}_clustertemplate.json        
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
      mkdir -p ${OUTPUT_DIR}
    else
      mkdir -p ${OUTPUT_DIR}
    fi

    do_get_cm_cluster_template
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


ps -eo pid,user,command | grep $(systemctl status cloudera-scm-server | awk '/Main PID:/ {print $3}') | egrep -v "grep|proc_watcher" | fgrep 'com.cloudera.api.redaction' >/dev/null 2>&1
if [[ $? -eq 0 ]]
then
    main
    echo -e "\n\nPlease review the information at:\n"
    ls -lrdth ${OUTPUT_DIR}/*
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
    # export CMF_JAVA_OPTS="-Xmx4G -XX:MaxPermSize=256m -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp -Dcom.sun.management.jmxremote.ssl.enabled.protocols=TLSv1.2 -Dcom.cloudera.api.redaction=false")"
    3) Restart Cloudera Manager Server
    systemctl restart cloudera-scm-server; tail -f /var/log/cloudera-scm-server/cloudera-scm-server.log | grep -i 'started jetty server'
    4) Execute the script => $0 again

##############################################################################
EOF
echo
fi