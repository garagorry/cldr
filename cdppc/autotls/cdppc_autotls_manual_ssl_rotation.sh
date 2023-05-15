#!/usr/bin/env bash
#
# --------------------------------------------------------------
# Description: 
# - Script to rotate expired AutoTLS certificates..
# - This script needs to run from the CM node as the root user.
# - Requires a Workload user and password.
# --------------------------------------------------------------
# Author: Jimmy Garagorry | jgaragorry@cloudera.com
# --------------------------------------------------------------
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
# --------------------------------------------------------------


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

function do_spinner () {
  spinner="/|\\-/|\\-"
  for i in $(seq 0 7)
  do
    echo -n "${spinner:$i:1}"
    echo -en "\010"
    sleep 1
  done
}

function do_check_cm_valid_cetificate () {
    CM_CERT_NOTAFTER=$(openssl s_client -connect $(hostname):7183 -showcerts </dev/null 2>/dev/null | openssl x509 -noout -subject -issuer -dates | awk -F"[=| ]" '/notAfter/ {print $2,$3,$4,$5}')
    CURRET_TIME=$(TZ=GMT date '+%b %d %H:%M:%S %Y')

    if [[ $(date +%s -d"${CM_CERT_NOTAFTER}") < $(date +%s -d"${CURRET_TIME}") ]]
    then
      echo "Coudera Manager has an expired certicate"
      echo "Starting a manual rotation"
      return 10
    else
      echo "Cloudera Manager has a valid Certificate expiring on: ${CM_CERT_NOTAFTER}"
      return 0
    fi
}

function do_cluster_service_restart () {
curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X POST "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERIVCE_NAME}/commands/restart"
}

function do_rotate_certificates () {
    # Create salt directory used to copy the certificate bundle per node
    if [[ -d ${REMOTE_DIR} ]]
    then
      rm -rf ${REMOTE_DIR}
      mkdir -p ${REMOTE_DIR}
    else
      mkdir -p ${REMOTE_DIR}
    fi
    
    # Create the certificate bundle for all the cluster nodes
    for FQDN in $(salt-key --out json 2>/dev/null | jq -r '.minions[]')
    do
      echo "Creating SSL certificate bundle for ${FQDN}:"
      /opt/cloudera/cm-agent/bin/certmanager --location /etc/cloudera-scm-server/certs gen_node_cert --rotate --output=${REMOTE_DIR}/cert-${FQDN}.tar ${FQDN}
      salt-cp --chunked --list ${FQDN} ${REMOTE_DIR}/cert-${FQDN}.tar /tmp/ssl/cert-${FQDN}.tar 
      salt --list ${FQDN} cmd.run "/opt/cloudera/cm-agent/bin/cm install_certs /tmp/ssl/cert-*.tar" 2>/dev/null
    done
    
    echo "Please wait, Cloudera Manager will back soon"
    do_spin &
    SPIN_PID=$!
    systemctl restart cloudera-scm-server
    ( tail -f -n0 /var/log/cloudera-scm-server/cloudera-scm-server.log  & ) | grep -q -i 'started jetty server'
    kill -9 $SPIN_PID > /dev/null 2>&1
     
    echo "Restarting Cloudera Manager Agents, Please Wait..."
    salt '*' cmd.run "systemctl restart cloudera-scm-agent" 2>/dev/null
    sleep 5
    salt '*' cmd.run "systemctl status cloudera-scm-agent" 2>/dev/null
    echo
}

function do_restart_cm_mgmt () {
  echo "Restarting MGMT Services"
  for MGMT_ROLE in $(curl -s -L -k -u "${WORKLOAD_USER}:${WORKLOAD_USER_PASS}" --noproxy '*' -H "accept: application/json" -H "Content-Type: application/json" -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleConfigGroups" | jq -r '.items[].name')
  do
    MGMT_ROLE_TYPE=$(curl -s -L -k -u "${WORKLOAD_USER}:${WORKLOAD_USER_PASS}" --noproxy '*' -H "accept: application/json" -H "Content-Type: application/json" -X GET "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleConfigGroups/${MGMT_ROLE}" | jq -r '.roleType')
    curl -s -L -k -u "${WORKLOAD_USER}:${WORKLOAD_USER_PASS}" --noproxy '*' -H "accept: application/json" -H "Content-Type: application/json" -d "{\"items\":[\"${MGMT_ROLE_TYPE}\"]}" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/cm/service/roleCommands/restart"
  done
  
  echo -e "\nPlease wait while Cloudera Management Services are restarted\n"
  spinner="/|\\-/|\\-"
  until [[ $(echo exit | /opt/cloudera/cm-agent/bin/supervisorctl -c /var/run/cloudera-scm-agent/supervisor/supervisord.conf | awk '/cloudera-mgmt/ {print $2}' | sort -u) = "RUNNING" ]]
  do
    for i in $(seq 0 7)
    do
      echo -n "${spinner:$i:1}"
      echo -en "\010"
      sleep 1
    done
  done 
  
  echo -e "\nCloudera Management Services Started\n"
  echo exit | /opt/cloudera/cm-agent/bin/supervisorctl -c /var/run/cloudera-scm-agent/supervisor/supervisord.conf | awk '/cloudera-mgmt/'
  echo
  sleep 2
}

function do_restart_cm () {
  echo "Restarting ${CM_CLUSTER_NAME} Services"
  curl -s -L -k -u "${WORKLOAD_USER}:${WORKLOAD_USER_PASS}" --noproxy '*' -H "accept: application/json" -H "Content-Type: application/json" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/commands/restart"
  sleep 1
  echo -e "\nPlease wait while ${CM_CLUSTER_NAME} services are restarted\n"
  sleep 1
  spinner="/|\\-/|\\-"

  while [[ $(curl -s -L -k -u "${WORKLOAD_USER}:${WORKLOAD_USER_PASS}" --noproxy '*' -H "accept: application/json" -H "Content-Type: application/json" -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CM_CLUSTER_NAME}/commands" | jq -r '.items[].name') == "Restart" ]]
  do
    for i in $(seq 0 7)
    do
      echo -n "${spinner:$i:1}"
      echo -en "\010"
      sleep 1
    done
  done 
  
  echo -e "\n${CM_CLUSTER_NAME} services Started\n"
  echo exit | /opt/cloudera/cm-agent/bin/supervisorctl -c /var/run/cloudera-scm-agent/supervisor/supervisord.conf | egrep -v ' +$|cloudera-mgmt|status_server|flood|cmflistener'
  echo
}

export CM_SERVER_DB_FILE=/etc/cloudera-scm-server/db.properties
export CM_DB_HOST=$(awk -F"=" '/db.host/ {print $NF}' ${CM_SERVER_DB_FILE})
export CM_DB_NAME=$(awk -F"=" '/db.name/ {print $NF}' ${CM_SERVER_DB_FILE})
export CM_DB_USER=$(awk -F"=" '/db.user/ {print $NF}' ${CM_SERVER_DB_FILE})
export PGPASSWORD=$(awk -F"=" '/db.password/ {print $NF}' ${CM_SERVER_DB_FILE})
export CM_CLUSTER_NAME=$(echo -e "SELECT name FROM clusters;" | psql -h ${CM_DB_HOST} -U ${CM_DB_USER} -d ${CM_DB_NAME} | grep -v Proxy | tail -n 3 | head -n1| sed 's| ||g')
export CM_SERVER="https://$(hostname -f):7183"
export REMOTE_DIR="/srv/remote/ssl"
export RED='\033[0;31m'
export NC='\033[0m' # No Color

do_check_cm_valid_cetificate

if [[ $? == 10 ]]
then
  source activate_salt_env
  do_rotate_certificates
else
  exit 0
fi


read -p "What is your Workload username: "  WORKLOAD_USER

unset WORKLOAD_USER_PASS
unset CHARTCOUNT

echo -n "Enter your Workload user Password: "
#stty -echo

while IFS= read -r -n1 -s CHAR
do
  case "${CHAR}" in
  $'\0')
      break
      ;;
  $'\177')
      if [ ${#WORKLOAD_USER_PASS} -gt 0 ]
      then
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
curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/version" > /tmp/null 2>&1
if grep "Bad credentials" /tmp/null > /dev/null 2>&1
then
  CRED_VALIDATED=1
  echo -e "\n===> ${RED}Please double-check the credentials provided${NC} <===\n"
  rm -rf /tmp/null 
else
  CRED_VALIDATED=0
  rm -rf /tmp/null 
fi
if [[ ${CRED_VALIDATED} == 0 ]]
then
 export CM_API_VERSION=$(curl  -s -L -k -u "${WORKLOAD_USER}:${WORKLOAD_USER_PASS}" --noproxy '*' -H "accept: application/json" -H "Content-Type: application/json" -X GET "${CM_SERVER}/api/version")
else
 exit 1
fi

do_restart_cm_mgmt
do_restart_cm

salt '*' cmd.run "rm -rf /tmp/ssl" 
rm -rf ${REMOTE_DIR}