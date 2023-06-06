#!/usr/bin/env bash
#
# Description: Script to control CM & CM MGMT Services using the CM API.
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

# Function: cluster_service_status - API Call to get a CM service status {{{1
#-----------------------------------------------------------------------
function cluster_service_status () 
{
    curl ${CURL_OPTIONS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERIVCE_NAME}"
}

# Function: cluster_service_stop - API Call to stop a CM service {{{1
#-----------------------------------------------------------------------
function cluster_service_stop () 
{
    curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERIVCE_NAME}/commands/stop"
}

# Function: cluster_service_start - API Call to start a CM service {{{1
#-----------------------------------------------------------------------
function cluster_service_start () 
{
    curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERIVCE_NAME}/commands/start"
}

# Function: cluster_service_restart - API Call to restart a CM service {{{1
#-----------------------------------------------------------------------
function cluster_service_restart () 
{
    curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERIVCE_NAME}/commands/restart"
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

# Function: cluster_service_rolling_restart_listOfServices - API Call to get all CM services payload {{{1
#-----------------------------------------------------------------------
function cluster_service_rolling_restart_listOfServices () 
{
    set -- $(curl ${CURL_OPTIONS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/services" | jq -r '.items[].name')
    cat <<EOF
    "restartServiceNames" : [
    $(while (( $# ))
    do
        if [[ $# -ne 1 ]]
        then
            echo -e "\t\"$1\","
            shift
        else
            echo -e "\t\"$1\""
            shift
        fi
    done)
    ]
EOF
}

# Function: cluster_service_rolling_restart - API Call to do a Rolling restart for all CM services {{{1
#-----------------------------------------------------------------------
function cluster_service_rolling_restart () 
{
    curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -d "{}" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/commands/rollingRestart"
    #{
    # "message" : "Please select at least one service from the cluster to restart."
    #}

    #set -- $(curl -s -L -k -u 'jg:sd2h^z@' --noproxy ''\''*'\''' -H 'accept: application/json' -H 'Content-Type: application/json' -X GET "https://sup-936620-repro-master0.sup-defa.lskx-pvue.a4.cloudera.site:7183/api/v51/clusters/sup-936620-repro/services" | jq -r '.items[].name')
    #cat > /tmp/rollingRestartAllServices <<EOF
    #{
    #"slaveBatchSize" : 1,
    #"sleepSeconds" : 30,
    #"staleConfigsOnly" : true,
    #"redeployClientConfiguration" : true,
    #"restartServiceNames" : [$(while (( $# ))
    #                        do
    #                            if [[ $# -ne 1 ]]
    #                            then
    #                                printf "%s" "\"$1\","
    #                                shift
    #                            else
    #                                printf "%s" "\"$1\""
    #                                shift
    #                            fi
    #                        done)]
    #}
#EOF
    #curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -d "$(jq . /tmp/rollingRestartAllServices)" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/commands/rollingRestart"
    #rm -rf /tmp/rollingRestartAllServices
}

# Function: cluster_service_full_restart - API Call to restart all CM services {{{1
#-----------------------------------------------------------------------
function cluster_service_full_restart () 
{
    curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/commands/restart"
}



# Function: cluster_control_services_mgmt - API Call to control CM MGMT Services {{{1
#-----------------------------------------------------------------------
function cluster_control_services_mgmt () 
{
    for MGMT_ROLE in $(curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleConfigGroups" | jq -r '.items[].name')
    do
        for MGMT_ROLE_TYPE in $(curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleConfigGroups/${MGMT_ROLE}" | jq -r '.roleType')
        do
            PS3=${PS3_MGMT_SRV}
            echo -e "\n#== CLUSTER: ${RED}${CM_CLUSTER_NAME}${NC} | SERVICE: ${RED}${MGMT_ROLE_TYPE^^}${NC} ==#\n"
            select ANSWER in "Start" "Stop" "Restart" "Next Service" "Exit"
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

# Function: cluster_mode_control_services - API Call to control All CM Services {{{1
#-----------------------------------------------------------------------
function cluster_mode_control_services () 
{
    PS3=${PS3_CLU_MOD}
    echo -e "Manage Cluster: [${RED}${CM_CLUSTER_NAME}${NC}]"
    select ANSWER in "Stop All" "Start All" "Go Back" "Exit"
    do
        case ${ANSWER} in
            "Stop All")
                cluster_service_full_stop
                ;;
            "Start All")
                cluster_service_full_start
                ;;
            "Go Back")
                PS3=${PS3_OP_MODE}
                clear
                echo -e "Manage Cluster: [${RED}${CM_CLUSTER_NAME}${NC}]"
                break
                ;;
            "Exit")
                exit 0
                ;;
            *) 
                echo -e "Invalid option, please try again. [${RED}-> To get the Menu Press Enter${NC}]:"
        esac
    done
}

# Function: cluster_service_mode_control - API Call to control CM Services {{{1
#-----------------------------------------------------------------------
function cluster_service_mode_control () 
{
    for CLUSTER_SERIVCE_NAME in $(curl ${CURL_OPTIONS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/services" | jq -r '.items[].name')
    do
        PS3=${PS3_SRV_MOD}
        echo -e "\n#== CLUSTER: ${RED}${CM_CLUSTER_NAME}${NC} | SERVICE: [${RED}${CLUSTER_SERIVCE_NAME}${NC}] ==#\n"
        select ANSWER in "Start" "Stop" "Status" "Restart" "Next Service" "Exit"
        do
            case ${ANSWER} in
                "Start")
                    cluster_service_start
                    ;;
                "Stop")
                    cluster_service_stop
                    ;;
                "Status")
                    cluster_service_status
                    ;;
                "Restart")
                    cluster_service_restart
                    ;;
                "Next Service")
                    break
                    ;;
                "Exit")
                    exit 0
                    ;;
                *) 
                    echo -e "Invalid option, please try again. [${RED}-> To get the Menu Press Enter${NC}]:"
            esac
        done
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
    export PS3_M_PPAL="What option would you like to try [-> To get the Menu Press Enter]: "
    export PS3_OP_MODE="How would you like to manage your cluster services [-> To get the Menu Press Enter]: "
    export PS3_CLU_MOD="Please select an option to manage all services in << ${CM_CLUSTER_NAME} >>: "
    export PS3_SRV_MOD="What action would you like to try for this Service? [-> To get the Menu Press Enter]: "
    export PS3_MGMT_SRV="What action would you like to try for this Service? [-> To get the Menu Press Enter]: "
    export PS3_MGMT_ALL="What action would you like to try for All Management Services? [-> To get the Menu Press Enter]: "
    export PS3_MGMT_PPAL="What option would you like to try [-> To get the Menu Press Enter]: "



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
    select ANSWER in "Cloudera Manager Service" "Cloudera Management Services" "Exit"
    do
        case ${ANSWER} in
            "Cloudera Manager Service")
                clear
                PS3=${PS3_OP_MODE}
                echo -e "Manage Services for Cluster: [${RED}${CM_CLUSTER_NAME}${NC}]\n"
                select ANSWER in "Cluster Mode" "Service Mode" "Go Back" "Exit"
                do
                    case ${ANSWER} in
                        "Cluster Mode")
                            clear
                            cluster_mode_control_services
                            ;;
                        "Service Mode")
                            clear
                            cluster_service_mode_control
                            ;;
                        "Go Back")
                            PS3=${PS3_M_PPAL}
                            clear
                            echo -e "Cluster: [${RED}${CM_CLUSTER_NAME}${NC}]"
                            break
                            ;;
                        "Exit")
                            exit 0
                            ;;
                        *) 
                            echo "Invalid option, please try again. [-> To get the Menu Press Enter]:"
                    esac
                done
                ;;
            "Cloudera Management Services")
                clear
                PS3=${PS3_MGMT_PPAL}
                echo -e "Cloudera Management Services for Cluster: [${RED}${CM_CLUSTER_NAME}${NC}]\n"
                select ANSWER in "Restart all MGMT Services" "Stop all MGMT Services" "Start all MGMT Services" "By MGMT Service" "Go Back" "Exit"
                do
                    case ${ANSWER} in
                        "Restart all MGMT Services")
                            clear
                            echo -e "\nRestarting:\n$(curl ${CURL_OPTIONS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleTypes"| jq -r '.[]')\n"
                            cluster_mgmt_service_restart_all
                        ;;
                        "Stop all MGMT Services")
                            clear
                            echo -e "\nStopping:\n$(curl ${CURL_OPTIONS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleTypes"| jq -r '.[]')\n"
                            cluster_mgmt_service_stop_all
                        ;;
                        "Start all MGMT Services")
                            clear
                            echo -e "\nStarting:\n$(curl ${CURL_OPTIONS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleTypes"| jq -r '.[]')\n"
                            cluster_mgmt_service_start_all
                        ;;
                        "By MGMT Service")
                            clear
                            cluster_control_services_mgmt
                            ;;
                        "Go Back")
                            PS3=${PS3_M_PPAL}
                            clear
                            echo -e "Cluster: [${RED}${CM_CLUSTER_NAME}${NC}]"
                            break
                            ;;
                        "Exit")
                            exit 0
                            ;;
                        *) 
                            echo "Invalid option, please try again. [-> To get the Menu Press Enter]:"
                    esac
                done
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