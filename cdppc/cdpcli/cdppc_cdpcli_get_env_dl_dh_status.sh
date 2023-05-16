#!/usr/bin/env bash
#
# Description: Script to get the status of an Environment, associated DL and DHs.
#              
# Use Case: (CDPPC) Execute before running a FreeIPA Upgrade. 
#              
# Date       Author               Description
# ---------- ------------------- ---------------------------------------------------------
# 05/15/2023 Jimmy Garagorry      Created
#==========================================================================================

# Function: do_check_arguments_required - Validate if required arguments are used {{{1
#-----------------------------------------------------------------------
function do_check_arguments_required () 
{
    if [[ $# -ne 1 ]]
    then
        echo -e "${RED}USAGE:${NC} $0 'EnvironmentName'\n"
        exit 1
    else
        export ENVIRONMENT_NAME=$1
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

# Function: do_get_cdp_valid_profile - Get a valid CDP Profile to query the Control Plane {{{1
#-----------------------------------------------------------------------
function do_get_cdp_valid_profile ()
{
    echo -en "\n${YELLOW}Give me the CDP Profile to use [Press Enter to use Default]: ${NC}"
    read CDP_PROFILE_ANSWER

    do_spin &
    SPIN_PID=$!

    if [[ -z ${CDP_PROFILE_ANSWER} ]]
    then
        export CDP_PROFILE_ANSWER=default
        #echo -e "\nUsing CDP CLI with ${GREEN}<< ${CDP_PROFILE_ANSWER} >>${NC} profile"
        cdp --profile ${CDP_PROFILE_ANSWER} iam get-user > /dev/null 2>&1
        if [[ $? -eq 0 ]]
        then
            echo -e "\nUsing CDP CLI with ${GREEN}<< ${CDP_PROFILE_ANSWER} >>${NC} profile"
        else
            echo -e "\n${RED}Something went wrong with ${NC}<< ${PROFILE} >>${RED} profile. Please confirm if this is a valid CDP Profile${NC}"
            echo -e "Please review you CDP Client configurations << \$HOME/.cdp/credentials >>\n${RED}$(grep --color '^\[.*\]$' ~/.cdp/credentials)${NC}"
            echo -e "CLI client setup at: ${BLUE}https://docs.cloudera.com/cdp-public-cloud/cloud/cli/topics/mc-installing-cdp-client.html${NC}\n"
            exit 1
        fi
    else
        cdp --profile ${CDP_PROFILE_ANSWER} iam get-user > /dev/null 2>&1
        if [[ $? -eq 0 ]]
        then
            echo -e "\nUsing CDP CLI with ${GREEN}<< ${CDP_PROFILE_ANSWER} >>${NC} profile"
        else
            echo -e "\n${RED}Something went wrong with ${NC}<< default >>${RED} profile. Please confirm if this is a valid CDP Profile${NC}"
            echo -e "Please review you CDP Client configurations << \$HOME/.cdp/credentials >>\n${RED}$(grep --color '^\[.*\]$' ~/.cdp/credentials)${NC}"
            echo -e "CLI client setup at: ${BLUE}https://docs.cloudera.com/cdp-public-cloud/cloud/cli/topics/mc-installing-cdp-client.html${NC}\n"
            exit 1
        fi
    fi

    kill -9 $SPIN_PID 2>/dev/null
    wait $SPIN_PID >/dev/null 2>&1
}

# Function: do_env_freeipa_status - Get the Environment/FreeIPA status  {{{1
#-----------------------------------------------------------------------
function do_env_freeipa_status () 
{
    do_get_cdp_valid_profile

    echo -e "\n###################################################################################################"
    echo -e "   ENVIRONMENT & FREEIPA STATUS"
    echo -e "###################################################################################################" 
    
    do_spin &
    SPIN_PID=$!

    ENVIRONMENT_NAME=$1
    PROFILE=${CDP_PROFILE_ANSWER}

    cdp --profile ${PROFILE} environments describe-environment --environment-name ${ENVIRONMENT_NAME} >/dev/null 2>&1

    if [[ $? -ne 0 ]]
    then
        echo -e "\n${RED}Something went wrong. Please confirm${NC} << ${ENVIRONMENT_NAME} >>${RED} is a valid Environment Name${NC}\n"
        exit 1
    else
        echo -e "\n${RED}==> Environment:${NC} $(cdp --profile ${PROFILE} environments describe-environment --environment-name ${ENVIRONMENT_NAME} 2>/dev/null | jq -r '.[] | "\(.environmentName) | STATUS => \(.status) | CLOUD PLATFORM => \(.cloudPlatform)"')"
        export ENVIRONMENT_CRN=$(cdp --profile ${PROFILE} environments describe-environment --environment-name ${ENVIRONMENT_NAME} 2>/dev/null | jq -r '.environment.crn')
        echo ${ENVIRONMENT_CRN}
        echo -e "\n${YELLOW}FreeIPA${NC}\n"
        cdp --profile ${PROFILE} environments get-freeipa-status --environment-name  ${ENVIRONMENT_NAME} 2>/dev/null | jq -r '.'
    fi

    kill -9 $SPIN_PID 2>/dev/null
    wait $SPIN_PID >/dev/null 2>&1
}

# Function: do_datalake_status - Get the Data Lake status  {{{1
#-----------------------------------------------------------------------
function do_datalake_status () 
{
    echo -e "\n###################################################################################################"
    echo -e "   DATALAKE STATUS"
    echo -e "###################################################################################################" 
    
    do_spin &
    SPIN_PID=$!
    
    if [[ $(echo "cdp --profile ${PROFILE} datalake list-datalakes 2>/dev/null | jq -r '.datalakes[] | select (.environmentCrn | contains(\"${ENVIRONMENT_CRN}\")) | \"\(.datalakeName)\"'" | bash | wc -l) -ne 0 ]]
    then
        DATALAKE_NAME=$(echo "cdp --profile ${PROFILE} datalake list-datalakes 2>/dev/null | jq -r '.datalakes[] | select (.environmentCrn | contains(\"${ENVIRONMENT_CRN}\")) | \"\(.datalakeName)\"'" | bash)
        echo -e "\n${YELLOW}==> Data Lake:${NC} $(cdp --profile ${PROFILE} datalake describe-datalake --datalake-name ${DATALAKE_NAME} 2>/dev/null | jq -r '.[] | "\(.datalakeName) | SHAPE => \(.shape) | STATUS => \(.status)"')"
        export DATALAKE_CRN=$(cdp --profile ${PROFILE}  datalake describe-datalake --datalake-name ${DATALAKE_NAME} 2>/dev/null | jq -r '.datalake.crn')
        echo ${DATALAKE_CRN}
        if [[ $(cdp --profile ${PROFILE}  datalake describe-datalake --datalake-name ${DATALAKE_NAME} 2>/dev/null | jq -r '.[].status') != "STOPPED" ]]
        then
            echo -e "${YELLOW}\nCluster service status${NC}\n"
            cdp --profile ${PROFILE} datalake get-cluster-service-status --cluster-name ${DATALAKE_NAME} | jq -r '.services[] | "SERVICE => \(.type) | STATE => \(.state) | HEALTH SUMMARY => \(.healthSummary)"'
            echo -e "\n${YELLOW}Hosts status${NC}\n"
            cdp --profile ${PROFILE} datalake get-cluster-host-status --cluster-name ${DATALAKE_NAME} | jq -r '.hosts[] | "\(.hostname) | HEALTH SUMMARY => \(.healthSummary)"'
        fi
    else
        echo -e "\n${YELLOW}No Data Lake on this Environment${NC}\n"
    fi

    kill -9 $SPIN_PID 2>/dev/null
    wait $SPIN_PID >/dev/null 2>&1
}

# Function: do_datahub_status - Get the Datahub status per Env  {{{1
#-----------------------------------------------------------------------
function do_datahub_status () 
{
    echo -e "\n###################################################################################################"
    echo -e "   DATAHUB STATUS"
    echo -e "###################################################################################################" 
        
    do_spin &
    SPIN_PID=$!
    
    if [[ $(echo "cdp --profile ${PROFILE} datahub list-clusters 2>/dev/null | jq -r '.clusters[] | select (.environmentCrn | contains(\"${ENVIRONMENT_CRN}\")) | \"\(.clusterName)\"'" | bash | wc -l) -ne 0 ]]
    then
        for DATAHUB_NAME in $(echo "cdp --profile ${PROFILE} datahub list-clusters 2>/dev/null | jq -r '.clusters[] | select (.environmentCrn | contains(\"${ENVIRONMENT_CRN}\")) | \"\(.clusterName)\"'" | bash)
        do
            echo -e "\n${BLUE}==> Datahub:${NC} $(cdp --profile ${PROFILE} datahub describe-cluster --cluster-name ${DATAHUB_NAME} 2>/dev/null | jq -r '.[] | "\(.clusterName) | STATUS => \(.status) | CLUSTER STATUS => \(.clusterStatus)"')"
            DATAHUB_CRN=$(cdp --profile ${PROFILE}  datahub describe-cluster --cluster-name ${DATAHUB_NAME} 2>/dev/null | jq -r '.cluster.crn')
            echo ${DATAHUB_CRN}

            if [[ $(cdp --profile ${PROFILE} datahub describe-cluster --cluster-name ${DATAHUB_NAME} 2>/dev/null | jq -r '.[].status') != "STOPPED" ]]
            then
                echo -e "\n${YELLOW}Cluster service status${NC}\n"
                cdp --profile ${PROFILE} datahub get-cluster-service-status --cluster-name ${DATAHUB_NAME} | jq -r '.services[] | "SERVICE => \(.type) | STATE => \(.state) | HEALTH SUMMARY =>  \(.healthSummary)"'
                echo -e "\n${YELLOW}Hosts status${NC}\n"
                cdp --profile ${PROFILE} datahub get-cluster-host-status --cluster-name ${DATAHUB_NAME} | jq -r '.hosts[] | "\(.hostname) | HEALTH SUMMARY => \(.healthSummary)"'
            fi
        done
    else
        echo -e "\n${YELLOW}No Datahubs on this Environment${NC}\n"
    fi

    kill -9 $SPIN_PID 2>/dev/null
    wait $SPIN_PID >/dev/null 2>&1
}

# Function: main - Run the required functions {{{1
#-----------------------------------------------------------------------
function main ()
{
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
    export YELLOW='\033[1;33m'
    export BLUE='\033[0;34m'
    export NC='\033[0m' # No Color
    do_check_arguments_required $1   
    do_env_freeipa_status $1 
    do_datalake_status
    do_datahub_status
}

clear
main $1