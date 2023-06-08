#!/usr/bin/env bash
# ~/bin/cldr_getkeytab.sh jgaragorry aws-jdga-794178-cdp-env aws-jdga-794178-cdp-dl-gateway1.aws-jdga.a465-9q4k.cloudera.site ~/.ssh/repro-default-sup.pem

function get_user_keytab ()
{
    echo "Extracting the ${UserName} keytab for ${EnvName}"
    #UserCRN=$(cdp iam list-users --max-items 1500 | jq -r --arg WL_USER_NAME ${UserName} '.users[]|select(.workloadUsername == $WL_USER_NAME)|(.crn)') 
    UserCRN=$(echo "cdp iam list-users --max-items 1500 | jq -r '.users[]|select(.workloadUsername == \"${UserName}\")|(.crn)'" | bash)     
    cdp environments get-keytab --environment ${EnvName} --actor-crn "${UserCRN}"| jq -r '.contents'| base64 --decode > ${Temporal_keytab}
}

function get_machine_user_keytab ()
{
    echo "Extracting the ${UserName} keytab for ${EnvName}"
    #UserCRN=$(cdp iam list-machine-users --max-items 1500 | jq -r --arg WL_USER_NAME ${UserName} '.users[]|select(.workloadUsername == $WL_USER_NAME)|(.crn)') 
    UserCRN=$(echo "cdp iam list-machine-users --max-items 1500 | jq -r '.machineUsers[]|select(.workloadUsername == \"${UserName}\")|(.crn)'" | bash)         
    cdp environments get-keytab --environment ${EnvName} --actor-crn "${UserCRN}"| jq -r '.contents'| base64 --decode > ${Temporal_keytab}
}

function move_keytab_to_vm ()
{
    echo "Moving ${Temporal_keytab} to ${RemoteHost}"
    scp -q -i ${PrivateKey} -o "UserKnownHostsFile=/dev/null" -o "StrictHostKeyChecking=no" ${Temporal_keytab} cloudbreak@${RemoteHost}:~/
    rm -rf ${Temporal_keytab}
}

function main ()
{
    UserName=$1
    EnvName=$2
    RemoteHost=$3
    PrivateKey=$4
    Temporal_keytab=/tmp/${UserName}-${EnvName}.keytab

    if [[ $# -ne 4 ]]
    then
        echo "USAGE: ${0} UserName EnvName RemoteHost PrivateKey"
        exit 1
    else
        if [[ ${UserName} == srv* ]]
        then
            get_machine_user_keytab
            move_keytab_to_vm
        else
            get_user_keytab
            move_keytab_to_vm
        fi
    fi
}

main $1 $2 $3 $4