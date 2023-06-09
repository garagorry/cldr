#!/usr/bin/env bash
# Description: Script to get a keytab for a Regular/Machine user from Cloudera Management Console
#              This script needs to run from a node where CDP CLI is installed.
# ./cdppc_umgmt_getkeytab.sh jgaragorry aws-jdga-cdp-env aws-jdga-cdp-dl-gateway1.aws-jdga.a465-9q4k.cloudera.site ~/.ssh/repro.pem
# ./cdppc_umgmt_getkeytab.sh srv_jgaragorry aws-jdga-cdp-env aws-jdga-cdp-dl-gateway1.aws-jdga.a465-9q4k.cloudera.site ~/.ssh/repro.pem

# Function: do_check_arguments_required - Validate if required arguments are used {{{1
#-----------------------------------------------------------------------
function do_check_arguments_required () 
{
    if [[ $# -ne 4 ]]
    then
        echo -e "${RED}USAGE:${NC} ${0} UserName EnvName RemoteHost PrivateKey\n"
        cat <<EOF
Where:

UserName => The regular workload user (user1) or the machine user (srv_user1).
EnvName => The Environment name (You can get this from the Management Console).
RemoteHost => The IP or FQDN of the host where you would like to copy the keytab.
PrivateKey => The location for your Cloudbreak Private key.
EOF
        echo
        exit 1
    fi
}

# Function: do_check_cdp_installed - Validate if cdp cli is installed {{{1
#-----------------------------------------------------------------------
function do_check_cdp_installed () 
{
    cdp >/dev/null 2>&1
    if [[ $? -ne 0 ]]
    then
        echo -e "\n${RED}Something went wrong${NC}"
        echo -e "Please review your CDP Client Installation."
        echo -e "CLI client setup at: ${BLUE}https://docs.cloudera.com/cdp-public-cloud/cloud/cli/topics/mc-installing-cdp-client.html${NC}\n"
        echo -e "CDP Control Plane regions at: ${BLUE}https://docs.cloudera.com/cdp-public-cloud/cloud/requirements-aws/topics/cdp-control-plane-regions.html${NC}\n"
        cat <<EOF
##############################################################################
CDP CLI | Example of a CDP CLI installation using Python's Virtual Environment
##############################################################################

mkdir -p ~/cdpcli/{cdpcli-beta,cdpclienv}

=========================
# Public CDP CLI client #
=========================
virtualenv ~/cdpcli/cdpclienv
source ~/cdpcli/cdpclienv/bin/activate
pip install cdpcli
pip install --upgrade cdpcli
deactivate

================
# Beta CDP CLI #
================
virtualenv ~/cdpcli/cdpcli-beta
source ~/cdpcli/cdpcli-beta/bin/activate
pip3 install cdpcli-beta
pip3 install cdpcli-beta --upgrade
EOF
        echo
        exit 1
    fi
}

# Function: get_user_keytab - Get a keytab for a regular user {{{1
#-----------------------------------------------------------------------
function get_user_keytab ()
{
    echo "Extracting the ${UserName} keytab for ${EnvName}"
    #UserCRN=$(cdp iam list-users --max-items 1500 | jq -r --arg WL_USER_NAME ${UserName} '.users[]|select(.workloadUsername == $WL_USER_NAME)|(.crn)') 
    UserCRN=$(echo "cdp iam list-users --max-items 1500 | jq -r '.users[]|select(.workloadUsername == \"${UserName}\")|(.crn)'" | bash)     
    cdp environments get-keytab --environment ${EnvName} --actor-crn "${UserCRN}"| jq -r '.contents'| base64 --decode > ${Temporal_keytab}
}

# Function: get_machine_user_keytab - Get a keytab for a machine user {{{1
#-----------------------------------------------------------------------
function get_machine_user_keytab ()
{
    echo "Extracting the ${UserName} keytab for ${EnvName}"
    #UserCRN=$(cdp iam list-machine-users --max-items 1500 | jq -r --arg WL_USER_NAME ${UserName} '.users[]|select(.workloadUsername == $WL_USER_NAME)|(.crn)') 
    UserCRN=$(echo "cdp iam list-machine-users --max-items 1500 | jq -r '.machineUsers[]|select(.workloadUsername == \"${UserName}\")|(.crn)'" | bash)         
    cdp environments get-keytab --environment ${EnvName} --actor-crn "${UserCRN}"| jq -r '.contents'| base64 --decode > ${Temporal_keytab}
}

# Function: move_keytab_to_vm - Copy the keytab to a remote host {{{1
#-----------------------------------------------------------------------
function move_keytab_to_vm ()
{
    echo "Moving ${Temporal_keytab} to ${RemoteHost}"
    scp -q -i ${PrivateKey} -o "UserKnownHostsFile=/dev/null" -o "StrictHostKeyChecking=no" ${Temporal_keytab} cloudbreak@${RemoteHost}:~/
    rm -rf ${Temporal_keytab}
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

    do_check_arguments_required $1 $2 $3 $4
    do_check_cdp_installed

    UserName=$1
    EnvName=$2
    RemoteHost=$3
    PrivateKey=$4
    Temporal_keytab=/tmp/${UserName}-${EnvName}.keytab

    if [[ ${UserName} == srv* ]]
    then
        get_machine_user_keytab
        move_keytab_to_vm
    else
        get_user_keytab
        move_keytab_to_vm
    fi

}

clear
main $1 $2 $3 $4
exit 0