#!/usr/bin/env bash
#
# ------------------------------------------------------------------
# Description:
# - Main script to create CDP Environments with specific details
# ------------------------------------------------------------------

# Load Properties
source cdppc-az-poc-property-file.txt
# Load Functions
source cdppc-az-poc-function-file.sh

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

if (( $# != 2 ))
then
  echo -e "\nThe valid arguments are:
             For \$1 => default | minimal | def1 | def2 | def3 | contributor
             For \$2 => pre | cred | freeipa-no-custom-img | freeipa-pep-no-custom-img | freeipa-no-custom-img-priv | freeipa-pep-no-custom-img-priv | dl-raz-runtime | dl-no-raz-runtime | dh-runtime
            
           Example: ${0} def2 pre\n"
  exit 52
else
  case $1 in
    default)
      export ROLE_DEFINITION=default
      ;;
    minimal) 
      export ROLE_DEFINITION=minimal
      ;;
    def1) 
      export ROLE_DEFINITION=def1
      ;;
    def2) 
      export ROLE_DEFINITION=def2
      ;;
    def3)
      export ROLE_DEFINITION=def3
      ;;
    contributor)
      export ROLE_DEFINITION=contributor
      ;;
    *)
      echo -e "The value of \${1} should be one of the following: default | minimal | def1 | def2 | def3 | contributor"
      exit 53
      ;;
  esac

  case $2 in
  pre)
    echo -e "\nCreating Azure Pre-requisites for CDP Public Cloud\n"
    cat <<EOF
    #########################
    RAZ on Azure environments
    #########################

    Shared Data Experience (SDX) in CDP Public Cloud provides Ranger Authorization Server (RAZ) service for fine grained access control and auditing of various services and workloads running in Enterprise Data Cloud. To use RAZ server capabilities, you must first enable RAZ in an Azure environment in CDP Public Cloud.

    Supported use cases for RAZ in Azure environments
    =================================================
      Many of the use cases that RAZ for Azure enables are cases where access control on files or directories is needed. Some examples include:
        - Per-user home directories.
        - Data engineering (Spark) efforts that require access to cloud storage objects and directories.
        - Data warehouse queries (Hive/Impala) that use external tables.
        - Access to Ranger's rich access control policies such as date-based access revocation, user/group/role-based controls, along with corresponding audit.
        - Tag-based access control using the classification propagation feature that originates from directories.
      The core RAZ for Azure for Data Lakes and several Data Hub templates are available for production use. The following Data Hub cluster types are supported:
        - Data Engineering
        - Data Engineering HA
        - Data Engineering Spark3
        - Operational Database with SQL
      Specifically, Hive, Spark, HBase, and Oozie are supported.
      RAZ is fully integrated with the following CDP data services:
        - Cloudera Data Flow (CDF)
        - Cloudera Data Engineering (CDE)
        - Cloudera Machine Learning (CML)
        - Cloudera Operational Database (COD)
EOF
    while true
    do
      echo -ne "\nWould you like to enable Ranger RAZ for this environment? [y/n]: "
      read USE_RAZ_RESPONSE

      case ${USE_RAZ_RESPONSE} in
        "y")
          az_create_rg ${RESOURCE_GROUP_NAME} "${LOCATION}"
          az_create_vnet_subnets ${RESOURCE_GROUP_NAME} ${VNET_NAME} ${VNET_CIDR} ${SUBNET_PATTERN} ${SUBNET_CIDR}
          az_create_az_nsg ${RESOURCE_GROUP_NAME} ${VNET_NAME} ${LOCATION} ${SG_CIDR_LOCAL_ALLOWED}
          az_create_sa_with_containers ${STORAGE_ACCOUNT_NAME} ${RESOURCE_GROUP_NAME} "${LOCATION}" ${STORAGE_ACCOUNT_SKU} ${STORAGE_ACCOUNT_KIND} ${STORAGE_ACCOUNT_CONTAINER_DATA} ${STORAGE_ACCOUNT_CONTAINER_LOG} ${STORAGE_ACCOUNT_CONTAINER_BACKUP}
          az_create_assumer_identity "${RESOURCE_GROUP_NAME}" "${ASSUMER_IDENTITY}" "ASSUMER_MSI_ID" "${SUBSCRIPTION_ID}" "${AZURE_MANAGED_IDENTITY_OPERATOR_GUID}" "${AZURE_VM_CONTRIBUTOR_GUID}" "${AZURE_STORAGE_CONTRIBUTOR_GUID}" "${STORAGE_ACCOUNT_NAME}" "${LOGS_LOCATION_BASE}" "${BACKUP_LOCATION_BASE}"
          az_create_data_lake_admin_identity "${RESOURCE_GROUP_NAME}" "${ADMIN_IDENTITY}" "ADMIN_MSI_ID" "${SUBSCRIPTION_ID}" "${AZURE_STORAGE_OWNER_GUID}" "${STORAGE_ACCOUNT_NAME}" "${STORAGE_LOCATION_BASE}" "${LOGS_LOCATION_BASE}"
          az_create_logger_identity "${RESOURCE_GROUP_NAME}" "${LOGGER_IDENTITY}" "LOGGER_MSI_ID" ${AZURE_STORAGE_CONTRIBUTOR_GUID} ${SUBSCRIPTION_ID} ${STORAGE_ACCOUNT_NAME} ${LOGS_LOCATION_BASE} ${BACKUP_LOCATION_BASE}
          az_create_ranger_audit_logger_identity "${RESOURCE_GROUP_NAME}" "${RANGER_AUDIT_LOGGER_IDENTITY}" "RANGER_AUDIT_LOGGER_MSI_ID" ${AZURE_STORAGE_CONTRIBUTOR_GUID} ${SUBSCRIPTION_ID} ${STORAGE_ACCOUNT_NAME} ${STORAGE_LOCATION_BASE} ${LOGS_LOCATION_BASE}
          az_create_ranger_raz_identity "${RESOURCE_GROUP_NAME}" "${RANGER_RAZ_IDENTITY}" "RANGER_RAZ_MSI_ID" ${AZURE_STORAGE_OWNER_GUID} ${SUBSCRIPTION_ID} ${STORAGE_ACCOUNT_NAME} ${AZURE_STORAGE_BLOB_DELEGATOR_GUID}
          break
          ;;
        "n")
          az_create_rg ${RESOURCE_GROUP_NAME} "${LOCATION}"
          az_create_vnet_subnets ${RESOURCE_GROUP_NAME} ${VNET_NAME} ${VNET_CIDR} ${SUBNET_PATTERN} ${SUBNET_CIDR}
          az_create_az_nsg ${RESOURCE_GROUP_NAME} ${VNET_NAME} ${LOCATION} ${SG_CIDR_LOCAL_ALLOWED}
          az_create_sa_with_containers ${STORAGE_ACCOUNT_NAME} ${RESOURCE_GROUP_NAME} "${LOCATION}" ${STORAGE_ACCOUNT_SKU} ${STORAGE_ACCOUNT_KIND} ${STORAGE_ACCOUNT_CONTAINER_DATA} ${STORAGE_ACCOUNT_CONTAINER_LOG} ${STORAGE_ACCOUNT_CONTAINER_BACKUP}
          az_create_assumer_identity "${RESOURCE_GROUP_NAME}" "${ASSUMER_IDENTITY}" "ASSUMER_MSI_ID" "${SUBSCRIPTION_ID}" "${AZURE_MANAGED_IDENTITY_OPERATOR_GUID}" "${AZURE_VM_CONTRIBUTOR_GUID}" "${AZURE_STORAGE_CONTRIBUTOR_GUID}" "${STORAGE_ACCOUNT_NAME}" "${LOGS_LOCATION_BASE}" "${BACKUP_LOCATION_BASE}"
          az_create_data_lake_admin_identity "${RESOURCE_GROUP_NAME}" "${ADMIN_IDENTITY}" "ADMIN_MSI_ID" "${SUBSCRIPTION_ID}" "${AZURE_STORAGE_OWNER_GUID}" "${STORAGE_ACCOUNT_NAME}" "${STORAGE_LOCATION_BASE}" "${LOGS_LOCATION_BASE}"
          az_create_logger_identity "${RESOURCE_GROUP_NAME}" "${LOGGER_IDENTITY}" "LOGGER_MSI_ID" ${AZURE_STORAGE_CONTRIBUTOR_GUID} ${SUBSCRIPTION_ID} ${STORAGE_ACCOUNT_NAME} ${LOGS_LOCATION_BASE} ${BACKUP_LOCATION_BASE}
          az_create_ranger_audit_logger_identity "${RESOURCE_GROUP_NAME}" "${RANGER_AUDIT_LOGGER_IDENTITY}" "RANGER_AUDIT_LOGGER_MSI_ID" ${AZURE_STORAGE_CONTRIBUTOR_GUID} ${SUBSCRIPTION_ID} ${STORAGE_ACCOUNT_NAME} ${STORAGE_LOCATION_BASE} ${LOGS_LOCATION_BASE}
          break
          ;;
        *)
          echo -e "Ups.. Please provide a valid response. Valid reponses are Y or N"
          sleep 2
          ;;
      esac
    done
    
    ;;
  cred)
    echo -e "\nCreating CDP Azure Credential ${PREFIX}-${RESOURCE_GROUP_NAME}-az-cred\n"
    do_activate_cdp_cli std >/dev/null 2>&1
    az_create_custom_role_app_registration  "${RESOURCE_GROUP_NAME}" ${PREFIX} "${SUBSCRIPTION_ID}" "${ROLE_DEFINITION}"
    do_create_cdp_credential ${PREFIX} ${SUBSCRIPTION_ID}
    ;;
  tags)
    echo -e "\nPreparing CDP CLI Shorthand Syntax for: \n${CUSTOM_TAGS}\n"
    echo -e "CDP CLI Shorthand Syntax \n--tags $(cdp_flatten_tags "${CUSTOM_TAGS}")\n"
    ;;
  az_tags)
    echo -e "\nPreparing Azure CLI Shorthand Syntax for: \n${CUSTOM_TAGS}\n"
    echo -e "Azure CLI Shorthand Syntax \n$(az_flatten_tags "${CUSTOM_TAGS}")\n"
    # RESOURCE_GROUP_NAME_ID=$(az group show -n ${RESOURCE_GROUP_NAME} --query id --output tsv)
    # jq  '.tags[] | "\(.key)=\(.value)"' /tmp/${PREFIX}-${RESOURCE_GROUP_NAME}-tags.json | sed 's|=|\"=\"|' | sed "s|^|az tag update --resource-id ${RESOURCE_GROUP_NAME_ID} --operation Merge --tags |" | bash 
    ;;
  sep)
    echo -e "\nEnabling Azure Storage & PostgreSQL Service Endpoints on ${VNET_NAME}\n"
    az_enable_service_endpoints ${RESOURCE_GROUP_NAME} ${VNET_NAME} ${VNET_CIDR} ${SUBNET_PATTERN} ${SUBNET_CIDR}
    ;;
  pep)
    echo -e "\nEnabling PostgreSQL Private DNS Zone for Private Endpoints\n"
    az_disable_private_endpoint_network_policies ${RESOURCE_GROUP_NAME} ${VNET_NAME} ${VNET_CIDR} ${SUBNET_PATTERN} ${SUBNET_CIDR}
    az_create_postgres_private_dnszone "${RESOURCE_GROUP_NAME}" "${SUBSCRIPTION_ID}" "privatelink.postgres.database.azure.com" "dnslink-postgres-${VNET_NAME}" "${CUSTOM_TAGS}"
    echo -e "\nEnabling Storage Account (DFS) Private DNS Zone & Private Endpoints\n"
    az_create_dfs_privatelink "${RESOURCE_GROUP_NAME}" "${STORAGE_ACCOUNT_NAME}" "${VNET_NAME}" "${SUBSCRIPTION_ID}" "privatelink.dfs.core.windows.net" "dnslink-dfs-${VNET_NAME}" "${CUSTOM_TAGS}"
    ;;
  freeipa-no-custom-img)
    # Latest FreeIPA image with Service EndPoints & Public IPsjq -r 
    do_activate_cdp_cli std > /dev/null 2>&1
    az_enable_service_endpoints ${RESOURCE_GROUP_NAME} ${VNET_NAME} ${VNET_CIDR} ${SUBNET_PATTERN} ${SUBNET_CIDR}
    do_create_cdp_az_env freeipa-no-custom-img
    ;;
  freeipa-pep-no-custom-img)
    # Latest FreeIPA image with Private EndPoints & Public IPs
    do_activate_cdp_cli std > /dev/null 2>&1
    az_disable_private_endpoint_network_policies ${RESOURCE_GROUP_NAME} ${VNET_NAME} ${VNET_CIDR} ${SUBNET_PATTERN} ${SUBNET_CIDR}
    az_create_postgres_private_dnszone "${RESOURCE_GROUP_NAME}" "${SUBSCRIPTION_ID}" "privatelink.postgres.database.azure.com" "dnslink-postgres-${VNET_NAME}" "${CUSTOM_TAGS}"
    az_create_dfs_privatelink "${RESOURCE_GROUP_NAME}" "${STORAGE_ACCOUNT_NAME}" "${VNET_NAME}" "${SUBSCRIPTION_ID}" "privatelink.dfs.core.windows.net" "dnslink-dfs-${VNET_NAME}" "${CUSTOM_TAGS}"
    do_create_cdp_az_env freeipa-pep-no-custom-img
    ;;
  freeipa-no-custom-img-priv)
    # Latest FreeIPA image with Service EndPoints & Private IPs
    do_activate_cdp_cli std > /dev/null 2>&1
    az_enable_service_endpoints ${RESOURCE_GROUP_NAME} ${VNET_NAME} ${VNET_CIDR} ${SUBNET_PATTERN} ${SUBNET_CIDR}
    do_create_cdp_az_env freeipa-no-custom-img-priv
    ;;
  freeipa-pep-no-custom-img-priv)
    # Latest FreeIPA image with Private EndPoints & Private IPs
    do_activate_cdp_cli std > /dev/null 2>&1
    az_disable_private_endpoint_network_policies ${RESOURCE_GROUP_NAME} ${VNET_NAME} ${VNET_CIDR} ${SUBNET_PATTERN} ${SUBNET_CIDR}
    az_create_postgres_private_dnszone "${RESOURCE_GROUP_NAME}" "${SUBSCRIPTION_ID}" "privatelink.postgres.database.azure.com" "dnslink-postgres-${VNET_NAME}" "${CUSTOM_TAGS}"
    az_create_dfs_privatelink "${RESOURCE_GROUP_NAME}" "${STORAGE_ACCOUNT_NAME}" "${VNET_NAME}" "${SUBSCRIPTION_ID}" "privatelink.dfs.core.windows.net" "dnslink-dfs-${VNET_NAME}" "${CUSTOM_TAGS}"
    do_create_cdp_az_env freeipa-pep-no-custom-img-priv
    ;;    
  dl-raz-runtime)
    do_activate_cdp_cli std > /dev/null 2>&1
    do_create_cdp_sdx raz-runtime
    ;;
  dl-no-raz-runtime)
    do_activate_cdp_cli std > /dev/null 2>&1
    do_create_cdp_sdx no-raz-runtime
    ;;
  dh-runtime)
    do_activate_cdp_cli std > /dev/null 2>&1
    do_cdp_load_dh_default_templates
    do_create_dh_default_cluster "${PREFIX}" "${DEFAULT_DH_TEMPLATE_CHOOSEN}" "${DEFAULT_DH_DEFINITION_CHOOSEN}" "${CUSTOM_TAGS}"
    ;;    
  *)
    echo "The value of \${2} should be one of the following: 'pre | cred | tags | az_tags | sep | pep | freeipa-no-custom-img | freeipa-pep-no-custom-img | freeipa-no-custom-img-priv | freeipa-pep-no-custom-img-priv | dl-raz-runtime | dl-no-raz-runtime | dh-runtime'"
    exit 54
    ;;
  esac
fi
