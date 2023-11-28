#!/usr/bin/env bash
#
# ------------------------------------------------------------------
# Description:
# Function File
# ------------------------------------------------------------------

function az_create_rg ()
{
    RESOURCE_GROUP_NAME=$1
    LOCATION="$2"
    set -x
    az group create --name ${RESOURCE_GROUP_NAME} --location "${LOCATION}"
    set +x
}
# az_create_rg ${RESOURCE_GROUP_NAME} "${LOCATION}"

function az_create_vnet_subnets ()
{
    # https://learn.microsoft.com/en-us/azure/virtual-network/ip-services/default-outbound-access
    RESOURCE_GROUP_NAME=$1
    VNET_NAME=$2
    VNET_CIDR=$3
    SUBNET_PATTERN=$4
    shift  4
    SUBNET_CIDR="$@"
    SUBNET_COUNT=1

    set -x
    az network vnet create -g ${RESOURCE_GROUP_NAME}  --name ${VNET_NAME} --address-prefix ${VNET_CIDR}
    set +x

    for subNet in ${SUBNET_CIDR}
    do
      set -x
      az network vnet subnet create -g ${RESOURCE_GROUP_NAME} -n ${SUBNET_PATTERN}-subnet-${SUBNET_COUNT} --vnet-name ${VNET_NAME} --address-prefixes ${subNet}
      set +x
      (( SUBNET_COUNT += 1 ))
    done
}
# az_create_vnet_subnets ${RESOURCE_GROUP_NAME} ${VNET_NAME} ${VNET_CIDR} ${SUBNET_PATTERN} ${SUBNET_CIDR}

function az_create_az_nsg ()
{
  # vnetname-default-nsg
  # vnetname-knox-nsg
    RESOURCE_GROUP_NAME=$1
    VNET_NAME=$2
    LOCATION=$3
    shift 3
    SG_CIDR_LOCAL_ALLOWED=$@

    for NSG_NAME in knox default
    do
      az network nsg create -g ${RESOURCE_GROUP_NAME}  -n ${VNET_NAME}-${NSG_NAME}-nsg --location ${LOCATION}

      IFS="|"
      PRIORITY_SEQ=102
      for AVAIL_CIDR in ${SG_CIDR_LOCAL_ALLOWED}
      do
          CIDR_ITEM=$(echo ${AVAIL_CIDR} | awk -F "," '{print $1}' | sed 's|,||')
          CIDR_DESCRIPTION=$(echo ${AVAIL_CIDR} | awk -F "," '{print $2}')

          set -x
          az network nsg rule create -g ${RESOURCE_GROUP_NAME} --nsg-name ${VNET_NAME}-${NSG_NAME}-nsg -n ssh_cidr_${PRIORITY_SEQ} --priority ${PRIORITY_SEQ} --source-address-prefixes "${CIDR_ITEM}" --destination-address-prefixes '*'  --destination-port-ranges 22 --direction Inbound --access Allow --protocol Tcp --description ${CIDR_DESCRIPTION}
          set +x
          (( PRIORITY_SEQ += 1 ))
          set -x
          az network nsg rule create -g ${RESOURCE_GROUP_NAME} --nsg-name ${VNET_NAME}-${NSG_NAME}-nsg -n knox_gateway_${PRIORITY_SEQ} --priority ${PRIORITY_SEQ} --source-address-prefixes "${CIDR_ITEM}" --destination-address-prefixes '*'  --destination-port-ranges 443 --direction Inbound --access Allow --protocol Tcp --description ${CIDR_DESCRIPTION}
          set +x
          (( PRIORITY_SEQ += 1 ))
      done

      set -x
      az network nsg rule create -g ${RESOURCE_GROUP_NAME} --nsg-name ${VNET_NAME}-${NSG_NAME}-nsg -n outbound --priority 201 --source-address-prefixes '*' --destination-address-prefixes '*'  --destination-port-ranges '*' --direction Outbound --access Allow --protocol '*' --description "Allow outbound access."
      set +x
    done
}
# az_create_az_nsg ${RESOURCE_GROUP_NAME} ${VNET_NAME} ${LOCATION} ${SG_CIDR_LOCAL_ALLOWED}

function az_create_private_dnszones ()
{
  RESOURCE_GROUP_NAME=${1}
  SUBSCRIPTION_ID=${2}

  privDnsZoneCount=0
  linkNamesCount=0

  for pvdz in $(echo $3 | sed 's|,| |g')
  do
    PRIVATE_DNS_ZONES[${privDnsZoneCount}]=${pvdz}
    (( privDnsZoneCount += 1 ))
  done

  for lns in $(echo $4 | sed 's|,| |g')
  do
    LINK_NAMES[${linkNamesCount}]=${lns}
    (( linkNamesCount += 1 ))
  done

  shift 4
  CUSTOM_TAGS="$@"

  echo -e "Configure the Private DNS Zone for: ${PRIVATE_DNS_ZONES[*]}"

  # Create a Private DNS Zone for PostgreSQL server/Storage Account (DFS) domain and create an association link with ${VNET_NAME}

  for i in $( seq 0 $(( ${#PRIVATE_DNS_ZONES[@]} - 1 )) )
  do
    zone_name="${PRIVATE_DNS_ZONES[${i}]}"
    link_name="${LINK_NAMES[${i}]}"
    
    echo -e "create private DNS zone ${zone_name}"

    set -x
    az network private-dns zone create \
        --name ${zone_name} \
        --resource-group ${RESOURCE_GROUP_NAME} \
        --subscription  ${SUBSCRIPTION_ID} \
        --tags ${CUSTOM_TAGS}
    set +x
    
    echo -e "create link to existing network ${link_name}"

    set -x
    az network private-dns link vnet create \
        --name ${link_name} \
        --resource-group ${RESOURCE_GROUP_NAME} \
        --registration-enabled false \
        --zone-name ${zone_name} \
        --virtual-network ${VNET_NAME} \
        --subscription  ${SUBSCRIPTION_ID} \
        --tags ${CUSTOM_TAGS}
    set +x
  done
}
# az_create_private_dnszones  "${RESOURCE_GROUP_NAME}" "${SUBSCRIPTION_ID}" "privatelink.postgres.database.azure.com,privatelink.dfs.core.windows.net" "dnslink-postgres-${VNET_NAME},dnslink-dfs-${VNET_NAME}" "${CUSTOM_TAGS}"

function az_enable_service_endpoints () 
{
    RESOURCE_GROUP_NAME=$1
    VNET_NAME=$2
    VNET_CIDR=$3
    SUBNET_PATTERN=$4
    shift  4
    SUBNET_CIDR="$@"
    SUBNET_COUNT=1

    for subNet in ${SUBNET_CIDR}
    do
      echo -e "Enabling Service Endpoints for subnet ${SUBNET_PATTERN}-subnet-${SUBNET_COUNT}"
      set -x
      az network vnet subnet update -g ${RESOURCE_GROUP_NAME} -n ${SUBNET_PATTERN}-subnet-${SUBNET_COUNT} --vnet-name ${VNET_NAME} --service-endpoints "Microsoft.Sql" "Microsoft.Storage"
      set +x
      (( SUBNET_COUNT += 1 ))
    done
}
# az_enable_service_endpoints ${RESOURCE_GROUP_NAME} ${VNET_NAME} ${VNET_CIDR} ${SUBNET_PATTERN} ${SUBNET_CIDR}

function az_disable_private_endpoint_network_policies ()
{
    RESOURCE_GROUP_NAME=$1
    VNET_NAME=$2
    VNET_CIDR=$3
    SUBNET_PATTERN=$4
    shift  4
    SUBNET_CIDR="$@"
    SUBNET_COUNT=1

    for subNet in ${SUBNET_CIDR}
    do
      echo -e "Disable subnet private endpoint policies for subnet ${SUBNET_PATTERN}-subnet-${SUBNET_COUNT}"
      set -x
      az network vnet subnet update --name ${SUBNET_PATTERN}-subnet-${SUBNET_COUNT} --resource-group ${RESOURCE_GROUP_NAME} --vnet-name ${VNET_NAME} --disable-private-endpoint-network-policies true
      set +x
      (( SUBNET_COUNT += 1 ))
    done
}
# az_disable_private_endpoint_network_policies ${RESOURCE_GROUP_NAME} ${VNET_NAME} ${VNET_CIDR} ${SUBNET_PATTERN} ${SUBNET_CIDR}

function az_create_postgres_private_dnszone ()
{
  RESOURCE_GROUP_NAME=${1}
  SUBSCRIPTION_ID=${2}
  PRIVATE_DNS_ZONE=${3}
  PRIVATE_LINK_NAME=${4}
  shift 4
  CUSTOM_TAGS="$@"

  # Create a Private DNS Zone for PostgreSQL server domain and create an association link with ${VNET_NAME}

  echo -e "create private DNS zone ${PRIVATE_DNS_ZONE}"
  
  set -x
  az network private-dns zone create \
      --name ${PRIVATE_DNS_ZONE} \
      --resource-group ${RESOURCE_GROUP_NAME} \
      --subscription  ${SUBSCRIPTION_ID} \
      --tags ${CUSTOM_TAGS}
  set +x

  echo -e "create link to existing network ${PRIVATE_LINK_NAME}"
  
  set -x
  az network private-dns link vnet create \
      --name ${PRIVATE_LINK_NAME} \
      --resource-group ${RESOURCE_GROUP_NAME} \
      --registration-enabled false \
      --zone-name ${PRIVATE_DNS_ZONE} \
      --virtual-network ${VNET_NAME} \
      --subscription  ${SUBSCRIPTION_ID} \
      --tags ${CUSTOM_TAGS}
  set +x
}
# az_create_postgres_private_dnszone "${RESOURCE_GROUP_NAME}" "${SUBSCRIPTION_ID}" "privatelink.postgres.database.azure.com" "dnslink-postgres-${VNET_NAME}" "${CUSTOM_TAGS}"

function az_create_sa_with_containers ()
{
  # The storage account SKU.  Allowed values: Premium_LRS, Premium_ZRS, Standard_GRS, Standard_GZRS, Standard_LRS, Standard_RAGRS, Standard_RAGZRS, Standard_ZRS. Default: Standard_RAGRS.
  # kind: Indicate the type of storage account. Allowed values: BlobStorage, BlockBlobStorage, FileStorage, Storage, StorageV2.  Default: StorageV2.
  # --enable-hierarchical-namespace --hns for kind=StorageV2.
  STORAGE_ACCOUNT_NAME=$1
  RESOURCE_GROUP_NAME=$2
  LOCATION="$3"
  STORAGE_ACCOUNT_SKU=$4
  STORAGE_ACCOUNT_KIND=$5
  STORAGE_ACCOUNT_CONTAINER_DATA=$6
  STORAGE_ACCOUNT_CONTAINER_LOG=$7
  STORAGE_ACCOUNT_CONTAINER_BACKUP=$8
  set -x
  az storage account create --name ${STORAGE_ACCOUNT_NAME} --resource-group ${RESOURCE_GROUP_NAME} --location "${LOCATION}" --sku ${STORAGE_ACCOUNT_SKU} --kind ${STORAGE_ACCOUNT_KIND} --hns
  set +x

  # Create three containers in storage account
  for Storage_Container in ${STORAGE_ACCOUNT_CONTAINER_DATA} ${STORAGE_ACCOUNT_CONTAINER_LOG} ${STORAGE_ACCOUNT_CONTAINER_BACKUP}
  do
    set -x
    az storage container create --name ${Storage_Container} --account-name ${STORAGE_ACCOUNT_NAME} --auth-mode login
    set +x
  done
}
# az_create_sa_with_containers ${STORAGE_ACCOUNT_NAME} ${RESOURCE_GROUP_NAME} "${LOCATION}" ${STORAGE_ACCOUNT_SKU} ${STORAGE_ACCOUNT_KIND} ${STORAGE_ACCOUNT_CONTAINER_DATA} ${STORAGE_ACCOUNT_CONTAINER_LOG} ${STORAGE_ACCOUNT_CONTAINER_BACKUP}

function az_create_dfs_privatelink ()
{
  # Steps & Requirements:
  # 1) An Storage Account
  # 2) A subnet
  # 3) Disable Private endpoint network policies
  # 4) Create the Private EP
  # 5) Create a Private DNS zone
  # 6) Link the private DNS zone
  # 7) Update the Private DNS zone with an IP (A record)
  # 8) If required add firewall rules
  RESOURCE_GROUP_NAME=$1
  STORAGE_ACCOUNT_NAME=$2
  VNET_NAME=$3  
  SUBSCRIPTION_ID=$4
  PRIVATE_DNS_ZONE=$5
  PRIVATE_LINK_NAME=$6
  shift 6
  CUSTOM_TAGS="$@"

  set -x
  STORAGE_ACCOUNT_ID=$(az storage account show --name ${STORAGE_ACCOUNT_NAME} --resource-group ${RESOURCE_GROUP_NAME} --query id --output tsv)
  set +x

  echo -e "Create a private endpoint for Azure Storage (dfs) in ${VNET_NAME}"
  # plsc=private link service connection
  # pep=Private EndPoint  

  set -x
  az network private-endpoint create \
  --name ${STORAGE_ACCOUNT_NAME}-cdp-dfs-pep \
  --resource-group ${RESOURCE_GROUP_NAME} \
  --vnet-name ${VNET_NAME} \
  --subnet $(az network vnet subnet list -g ${RESOURCE_GROUP_NAME} --vnet-name ${VNET_NAME} | jq -r '.[].name' | head -n1) \
  --connection-name ${STORAGE_ACCOUNT_NAME}-cdp-dfs-plsc \
  --private-connection-resource-id ${STORAGE_ACCOUNT_ID} \
  --group-id dfs 
  set +x
  
  # Create a Private DNS Zone for Storage Account (Target DFS) server domain and create an association link with ${VNET_NAME}

  echo -e "create private DNS zone ${PRIVATE_DNS_ZONE}"
  set -x
  az network private-dns zone create \
      --name ${PRIVATE_DNS_ZONE} \
      --resource-group ${RESOURCE_GROUP_NAME} \
      --subscription  ${SUBSCRIPTION_ID} \
      --tags ${CUSTOM_TAGS}

  set +x
  
  echo -e "create link to existing network ${PRIVATE_LINK_NAME}"

  set -x
  az network private-dns link vnet create \
      --name ${PRIVATE_LINK_NAME} \
      --resource-group ${RESOURCE_GROUP_NAME} \
      --registration-enabled false \
      --zone-name ${PRIVATE_DNS_ZONE} \
      --virtual-network ${VNET_NAME} \
      --subscription  ${SUBSCRIPTION_ID} \
      --tags ${CUSTOM_TAGS}

  # Get the ID of the azure storage NIC
  STORAGE_NIC_ID=$(az network private-endpoint show --name ${STORAGE_ACCOUNT_NAME}-cdp-dfs-pep  -g  ${RESOURCE_GROUP_NAME} --query 'networkInterfaces[0].id' -o tsv)
  # Get the IP of the azure storage NIC
  STORAGE_ACCOUNT_PRIVATE_IP=$(az resource show --ids ${STORAGE_NIC_ID} --query 'properties.ipConfigurations[0].properties.privateIPAddress' --output tsv)

  az network private-dns record-set a create \
  --name ${STORAGE_ACCOUNT_NAME} \
  --zone-name ${PRIVATE_DNS_ZONE} \
  --resource-group ${RESOURCE_GROUP_NAME}
  
  az network private-dns record-set a add-record \
  --record-set-name ${STORAGE_ACCOUNT_NAME} \
  --zone-name ${PRIVATE_DNS_ZONE} \
  --resource-group ${RESOURCE_GROUP_NAME} \
  -a ${STORAGE_ACCOUNT_PRIVATE_IP}
  set +x
}
# az_create_dfs_privatelink "${RESOURCE_GROUP_NAME}" "${STORAGE_ACCOUNT_NAME}" "${VNET_NAME}" "${SUBSCRIPTION_ID}" "privatelink.dfs.core.windows.net" "dnslink-dfs-${VNET_NAME}" "${CUSTOM_TAGS}"

function az_create_identity()
{
   RESOURCE_GROUP_NAME=$1
   IDENTITY="$2"
   MSI_ID="$3"
   echo "Creating user-assigned MSI for ${IDENTITY}..."
   RESULT=$(az identity create -g ${RESOURCE_GROUP_NAME} -n ${IDENTITY})
   ID=$(echo ${RESULT} | jq -r '.id')
   PRINCIPALID=$(echo ${RESULT} | jq -r '.principalId')
   echo "Created user-assigned MSI with id: ${ID} and principal id: ${PRINCIPALID}"
   echo "Please wait a minute" && sleep 60
}

function az_create_assumer_identity ()
{
  # Assumer identity - Assign the Virtual Machine Contributor role and the Managed Identity Operator role to the Assumer managed identity on subscription level and then assign the Storage Blob Data Contributor on the scope of the container created earlier for Logs Location Base.
  RESOURCE_GROUP_NAME=${1}
  ASSUMER_IDENTITY=${2}
  ASSUMER_MSI_ID=${3}
  SUBSCRIPTION_ID=${4}
  AZURE_MANAGED_IDENTITY_OPERATOR_GUID=${5}
  AZURE_VM_CONTRIBUTOR_GUID=${6}
  AZURE_STORAGE_CONTRIBUTOR_GUID=${7}
  STORAGE_ACCOUNT_NAME=${8}
  LOGS_LOCATION_BASE=${9}
  BACKUP_LOCATION_BASE=${10}

  set -x
  az_create_identity "${RESOURCE_GROUP_NAME}" "${ASSUMER_IDENTITY}" "${ASSUMER_MSI_ID}"
  ASSUMER_OBJECTID=$(echo "az identity list -g ${RESOURCE_GROUP_NAME}|jq '.[]|{\"name\":.name,\"principalId\":.principalId}|select(.name | test(\"${ASSUMER_IDENTITY}\"))|.principalId'| tr -d '\"'" |bash)
  echo ${ASSUMER_OBJECTID}  
  az role assignment create --assignee ${ASSUMER_OBJECTID} --role ${AZURE_MANAGED_IDENTITY_OPERATOR_GUID} --scope "/subscriptions/${SUBSCRIPTION_ID}"
  az role assignment create --assignee ${ASSUMER_OBJECTID} --role ${AZURE_VM_CONTRIBUTOR_GUID} --scope "/subscriptions/${SUBSCRIPTION_ID}"
  az role assignment create --assignee ${ASSUMER_OBJECTID} --role ${AZURE_STORAGE_CONTRIBUTOR_GUID} --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT_NAME}/blobServices/default/containers/${LOGS_LOCATION_BASE}"
  az role assignment create --assignee ${ASSUMER_OBJECTID} --role ${AZURE_STORAGE_CONTRIBUTOR_GUID} --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT_NAME}/blobServices/default/containers/${BACKUP_LOCATION_BASE}"
  set +x
}
# az_create_assumer_identity "${RESOURCE_GROUP_NAME}" "${ASSUMER_IDENTITY}" "ASSUMER_MSI_ID" "${SUBSCRIPTION_ID}" "${AZURE_MANAGED_IDENTITY_OPERATOR_GUID}" "${AZURE_VM_CONTRIBUTOR_GUID}" "${AZURE_STORAGE_CONTRIBUTOR_GUID}" "${STORAGE_ACCOUNT_NAME}" "${LOGS_LOCATION_BASE}" "${BACKUP_LOCATION_BASE}"

function az_create_data_lake_admin_identity ()
{
  # Assign the Storage Blob Data Owner role to the Data Lake Admin managed identity on the scope of the two containers created earlier for Storage Location Base and Logs Location Base, and to the Backup Location Base container if it exists. You need to do this separately for each of the containers.
  RESOURCE_GROUP_NAME=${1}
  ADMIN_IDENTITY=$2
  ADMIN_MSI_ID=$3
  SUBSCRIPTION_ID=${4}
  AZURE_STORAGE_OWNER_GUID=$5
  STORAGE_ACCOUNT_NAME=$6
  STORAGE_LOCATION_BASE=$7
  LOGS_LOCATION_BASE=$8

  set -x
  az_create_identity  "${RESOURCE_GROUP_NAME}" "${ADMIN_IDENTITY}" ${ADMIN_MSI_ID}
  ADMIN_OBJECTID=$(echo "az identity list -g ${RESOURCE_GROUP_NAME}|jq '.[]|{\"name\":.name,\"principalId\":.principalId}|select(.name | test(\"${ADMIN_IDENTITY}\"))|.principalId'| tr -d '\"'" |bash)
  echo ${ADMIN_OBJECTID}
  az role assignment create --assignee ${ADMIN_OBJECTID} --role ${AZURE_STORAGE_OWNER_GUID} --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT_NAME}/blobServices/default/containers/${STORAGE_LOCATION_BASE}"
  az role assignment create --assignee $ADMIN_OBJECTID --role ${AZURE_STORAGE_OWNER_GUID} --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT_NAME}/blobServices/default/containers/${LOGS_LOCATION_BASE}"
  az role assignment create --assignee $ADMIN_OBJECTID --role ${AZURE_STORAGE_OWNER_GUID} --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT_NAME}/blobServices/default/containers/${BACKUP_LOCATION_BASE}"
  set +x
}
#create_data_lake_admin_identity "${RESOURCE_GROUP_NAME}" "${ADMIN_IDENTITY}" "ADMIN_MSI_ID" "${SUBSCRIPTION_ID}" "${AZURE_STORAGE_OWNER_GUID}" "${STORAGE_ACCOUNT_NAME}" "${STORAGE_LOCATION_BASE}" "${LOGS_LOCATION_BASE}"

function az_create_logger_identity ()
{
  # Assign the Storage Blob Data Contributor role to the Logger managed identity on the scope of the container created earlier for Logs Location Base. If you created a separate container for Backup Location Base, you should also assign the same role to the same managed identity on the scope of the container created earlier for Backup Location Base.
  RESOURCE_GROUP_NAME=${1}
  LOGGER_IDENTITY=$2
  LOGGER_MSI_ID=$3
  AZURE_STORAGE_CONTRIBUTOR_GUID=$4
  SUBSCRIPTION_ID=$5
  STORAGE_ACCOUNT_NAME=$6
  LOGS_LOCATION_BASE=$7
  BACKUP_LOCATION_BASE=$8

  set -x
  az_create_identity "${RESOURCE_GROUP_NAME}" "${LOGGER_IDENTITY}" "${LOGGER_MSI_ID}"
  LOGGER_OBJECTID=$(echo "az identity list -g ${RESOURCE_GROUP_NAME}|jq '.[]|{\"name\":.name,\"principalId\":.principalId}|select(.name | test(\"${LOGGER_IDENTITY}\"))|.principalId'| tr -d '\"'" |bash)
  echo ${LOGGER_OBJECTID}
  az role assignment create --assignee ${LOGGER_OBJECTID} --role ${AZURE_STORAGE_CONTRIBUTOR_GUID} --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT_NAME}/blobServices/default/containers/${LOGS_LOCATION_BASE}"
  az role assignment create --assignee ${LOGGER_OBJECTID} --role ${AZURE_STORAGE_CONTRIBUTOR_GUID} --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT_NAME}/blobServices/default/containers/${BACKUP_LOCATION_BASE}"
  set +x
}
#az_create_logger_identity "${RESOURCE_GROUP_NAME}" "${LOGGER_IDENTITY}" "LOGGER_MSI_ID" ${AZURE_STORAGE_CONTRIBUTOR_GUID} ${SUBSCRIPTION_ID} ${STORAGE_ACCOUNT_NAME} ${LOGS_LOCATION_BASE} ${BACKUP_LOCATION_BASE}

function az_create_ranger_audit_logger_identity ()
{
  #Assign the Storage Blob Data Contributor role to the Ranger Audit Logger managed identity on the scope of the container created earlier for Storage Location Base. If you created a separate container for Backup Location Base, you should also repeat these steps on the container created earlier for Backup Location Base. Otherwise, they should be repeated on the Logs Location Base container.
  RESOURCE_GROUP_NAME=${1}
  RANGER_AUDIT_LOGGER_IDENTITY=$2
  RANGER_AUDIT_LOGGER_MSI_ID=$3
  AZURE_STORAGE_CONTRIBUTOR_GUID=$4
  SUBSCRIPTION_ID=$5
  STORAGE_ACCOUNT_NAME=$6
  STORAGE_LOCATION_BASE=$7
  LOGS_LOCATION_BASE=$8

  set -x
  az_create_identity "${RESOURCE_GROUP_NAME}" "${RANGER_AUDIT_LOGGER_IDENTITY}" "${RANGER_AUDIT_LOGGER_MSI_ID}"
  RANGER_OBJECTID=$(echo "az identity list -g ${RESOURCE_GROUP_NAME}|jq '.[]|{\"name\":.name,\"principalId\":.principalId}|select(.name | test(\"${RANGER_AUDIT_LOGGER_IDENTITY}\"))|.principalId'| tr -d '\"'" |bash)
  echo ${RANGER_OBJECTID}
  az role assignment create --assignee ${RANGER_OBJECTID} --role ${AZURE_STORAGE_CONTRIBUTOR_GUID} --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT_NAME}/blobServices/default/containers/${STORAGE_LOCATION_BASE}"
  az role assignment create --assignee ${RANGER_OBJECTID} --role ${AZURE_STORAGE_CONTRIBUTOR_GUID} --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT_NAME}/blobServices/default/containers/${LOGS_LOCATION_BASE}"
  az role assignment create --assignee ${RANGER_OBJECTID} --role ${AZURE_STORAGE_CONTRIBUTOR_GUID} --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT_NAME}/blobServices/default/containers/${BACKUP_LOCATION_BASE}"
  set +x
}
#az_create_ranger_audit_logger_identity "${RESOURCE_GROUP_NAME}" "${RANGER_AUDIT_LOGGER_IDENTITY}" "RANGER_AUDIT_LOGGER_MSI_ID" ${AZURE_STORAGE_CONTRIBUTOR_GUID} ${SUBSCRIPTION_ID} ${STORAGE_ACCOUNT_NAME} ${STORAGE_LOCATION_BASE} ${LOGS_LOCATION_BASE}

function az_create_ranger_raz_identity ()
{
  # If you would like to use Fine-grained access control, you should create the Ranger RAZ managed identity. Assign the Storage Blob Data Owner role and the Storage Blob Delegator role to the Ranger RAZ managed identity on the scope of the storage account that you created earlier (which contains the Storage Location Base and Logs Location Base).
  RESOURCE_GROUP_NAME=${1}
  RANGER_RAZ_IDENTITY=$2
  RANGER_RAZ_MSI_ID=$3
  AZURE_STORAGE_OWNER_GUID=$4
  SUBSCRIPTION_ID=$5
  STORAGE_ACCOUNT_NAME=$6
  AZURE_STORAGE_BLOB_DELEGATOR_GUID=$7

  set x
  az_create_identity "${RESOURCE_GROUP_NAME}" "${RANGER_RAZ_IDENTITY}" "${RANGER_RAZ_MSI_ID}"
  RANGER_RAZ_OBJECTID=$(echo "az identity list -g ${RESOURCE_GROUP_NAME}|jq '.[]|{\"name\":.name,\"principalId\":.principalId}|select(.name | test(\"${RANGER_RAZ_IDENTITY}\"))|.principalId'| tr -d '\"'" |bash)
  echo ${RANGER_RAZ_OBJECTID}
  az role assignment create --assignee ${RANGER_RAZ_OBJECTID} --role ${AZURE_STORAGE_OWNER_GUID} --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT_NAME}"
  az role assignment create --assignee ${RANGER_RAZ_OBJECTID} --role ${AZURE_STORAGE_BLOB_DELEGATOR_GUID} --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT_NAME}"
  set +x
}
# az_create_ranger_raz_identity "${RESOURCE_GROUP_NAME}" "${RANGER_RAZ_IDENTITY}" "RANGER_RAZ_MSI_ID" ${AZURE_STORAGE_OWNER_GUID} ${SUBSCRIPTION_ID} ${STORAGE_ACCOUNT_NAME} ${AZURE_STORAGE_BLOB_DELEGATOR_GUID}

function az_create_custom_role_app_registration ()
{
  RESOURCE_GROUP_NAME=${1}
  PREFIX=${2}
  SUBSCRIPTION_ID=${3}
  ROLE_DEFINITION=${4}

  case ${ROLE_DEFINITION} in
    default)
      echo -e "Using: roles/default.json to create a custom role 'Cloudera Management Console Azure Operator'"
      sed -e "s|Cloudera Management Console Azure Operator|${PREFIX}-${RESOURCE_GROUP_NAME}-custom-default Cloudera Management Console Azure Operator|" -e "s|{subscriptionId}|${SUBSCRIPTION_ID}|" roles/default-template.json > roles/default.json
      set -x
      az role definition create --role-definition @roles/default.json
      az ad sp create-for-rbac --name http://${PREFIX}-${RESOURCE_GROUP_NAME}-az-app \
      --role "${PREFIX}-${RESOURCE_GROUP_NAME}-custom-default Cloudera Management Console Azure Operator" \
      --scopes /subscriptions/${SUBSCRIPTION_ID} > /tmp/${PREFIX}-${RESOURCE_GROUP_NAME}-az-create-for-rbac.out
      set +x
      ;;
    minimal)
      echo -e "Using: roles/minimal.json to create a custom role 'Cloudera Management Console Azure Operator'"
      sed -e "s|Cloudera Management Console Azure Operator|${PREFIX}-${RESOURCE_GROUP_NAME}-custom-minimal Cloudera Management Console Azure Operator|" -e "s|{subscriptionId}|${SUBSCRIPTION_ID}|" roles/minimal-template.json > roles/minimal.json
      set -x
      az role definition create --role-definition @roles/minimal.json
      az ad sp create-for-rbac --name http://${PREFIX}-${RESOURCE_GROUP_NAME}-az-app \
      --role "${PREFIX}-${RESOURCE_GROUP_NAME}-custom-minimal Cloudera Management Console Azure Operator" \
      --scopes /subscriptions/${SUBSCRIPTION_ID} > /tmp/${PREFIX}-${RESOURCE_GROUP_NAME}-az-create-for-rbac.out
      set +x
      ;;
    def1)
      echo -e "Using: roles/role_definition_1.json to create a custom role 'Cloudera Management Console Azure Operator'"
      sed -e "s|Cloudera Management Console Azure Operator For Single Resource Group|${PREFIX}-${RESOURCE_GROUP_NAME}-custom-def1 Cloudera Management Console Azure Operator For Single Resource Group|" -e "s|{SUBSCRIPTION-ID}|${SUBSCRIPTION_ID}|" -e "s|{RESOURCE-GROUP-NAME}|${RESOURCE_GROUP_NAME}|" roles/role_definition_1-template.json >  roles/role_definition_1.json
      set -x
      az role definition create --role-definition @roles/role_definition_1.json
      az ad sp create-for-rbac --name http://${PREFIX}-${RESOURCE_GROUP_NAME}-az-app \
      --role "${PREFIX}-${RESOURCE_GROUP_NAME}-custom-def1 Cloudera Management Console Azure Operator For Single Resource Group" \
      --scopes /subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME} > /tmp/${PREFIX}-${RESOURCE_GROUP_NAME}-az-create-for-rbac.out
      set +x
      ;;
    def2)
      echo -e "Using: roles/role_definition_2.json to create a custom role 'Cloudera Management Console Azure Operator'"
      sed -e "s|Cloudera Management Console Azure Operator for Single Resource Group|${PREFIX}-${RESOURCE_GROUP_NAME}-custom-def2 Cloudera Management Console Azure Operator for Single Resource Group|" -e "s|{SUBSCRIPTION-ID}|${SUBSCRIPTION_ID}|" -e "s|{RESOURCE-GROUP-NAME}|${RESOURCE_GROUP_NAME}|" roles/role_definition_2-template.json >  roles/role_definition_2.json
      set -x
      az role definition create --role-definition @roles/role_definition_2.json
      az ad sp create-for-rbac --name http://${PREFIX}-${RESOURCE_GROUP_NAME}-az-app \
      --role "${PREFIX}-${RESOURCE_GROUP_NAME}-custom-def2 Cloudera Management Console Azure Operator for Single Resource Group" \
      --scopes /subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME} > /tmp/${PREFIX}-${RESOURCE_GROUP_NAME}-az-create-for-rbac.out
      set +x
      ;;
    def3)
      echo -e "Using: roles/role_definition_3.json to create a custom role 'Cloudera Management Console Azure Operator'"
      sed -e "s|Cloudera Management Console Azure Operator|${PREFIX}-${RESOURCE_GROUP_NAME}-custom-def3 Cloudera Management Console Azure Operator|" -e "s|{SUBSCRIPTION-ID}|${SUBSCRIPTION_ID}|" roles/role_definition_3-template.json > roles/role_definition_3.json
      set -x
      az role definition create --role-definition @roles/role_definition_3.json
      az ad sp create-for-rbac --name http://${PREFIX}-${RESOURCE_GROUP_NAME}-az-app \
      --role "${PREFIX}-${RESOURCE_GROUP_NAME}-custom-def3 Cloudera Management Console Azure Operator" \
      --scopes /subscriptions/${SUBSCRIPTION_ID} > /tmp/${PREFIX}-${RESOURCE_GROUP_NAME}-az-create-for-rbac.out
      set +x
      ;;
    contributor)
      echo -e "Using built-in contributor role"
      set -x
      az ad sp create-for-rbac \
      --name http://${PREFIX}-${RESOURCE_GROUP_NAME}-az-app \
      --role Contributor \
      --scopes /subscriptions/${SUBSCRIPTION_ID} > /tmp/${PREFIX}-${RESOURCE_GROUP_NAME}-az-create-for-rbac.out
      set +x
      ;;
    *)
      echo -e "Usage: ${0} 'default|minimal|def1|def2|def3|contributor'"
      ;;
  esac  
}
# az_create_custom_role_app_registration  "${RESOURCE_GROUP_NAME}" ${PREFIX} "${SUBSCRIPTION_ID}" "default|minimal|def1|def2|def3|contributor"

function do_create_cdp_credential ()
{
  # Name must be between than 5 and 100 character long.
  PREFIX=${1}
  SUBSCRIPTION_ID=${2}
  APP_ID=$(jq -r '.appId' /tmp/${PREFIX}-${RESOURCE_GROUP_NAME}-az-create-for-rbac.out)
  APP_DISPLAY_NAME=$(jq -r '.displayName' /tmp/${PREFIX}-${RESOURCE_GROUP_NAME}-az-create-for-rbac.out)
  APP_PASSWORD=$(jq -r '.password' /tmp/${PREFIX}-${RESOURCE_GROUP_NAME}-az-create-for-rbac.out)
  APP_TENANT=$(jq -r '.tenant' /tmp/${PREFIX}-${RESOURCE_GROUP_NAME}-az-create-for-rbac.out)
  
  echo -e "Save this app-registration information in a secure location.
  This is the only time that the secret access key can be viewed. 
  You will not be able to retrieve this app-registration password after this step.\n
  $(cat /tmp/${PREFIX}-${RESOURCE_GROUP_NAME}-az-create-for-rbac.out)\n"

  cat > /tmp/${PREFIX}-${RESOURCE_GROUP_NAME}-az-cred-for-rbac.json <<EOF
  {
    "credentialName": "${PREFIX}-${RESOURCE_GROUP_NAME}-az-cred",
    "appBased": {
        "authenticationType": "SECRET",
        "applicationId": "${APP_ID}",
        "secretKey": "${APP_PASSWORD}"
    },
    "subscriptionId": "${SUBSCRIPTION_ID}",
    "tenantId": "${APP_TENANT}",
    "description": "${PREFIX}-${RESOURCE_GROUP_NAME} Credential for Azure"
  }
EOF

  set -x
  cdp environments create-azure-credential --cli-input-json "$(cat /tmp/${PREFIX}-${RESOURCE_GROUP_NAME}-az-cred-for-rbac.json)"
  set +x
  rm -rf /tmp/${PREFIX}-${RESOURCE_GROUP_NAME}-az-create-for-rbac.out
}
# do_create_cdp_credential ${PREFIX} ${SUBSCRIPTION_ID}

function do_activate_cdp_cli ()
{
  ## Creating a Python virtual environment in Linux
   #-> If pip is not in your system
    #) apt-get install python-pip
   #-> Then install virtualenv
    #) pip install virtualenv
   #-> Virtualenv Tree
    #) mkdir -p ~/cdpcli/{cdpcli-beta,cdpclienv}

  case $1 in
    std) 
      virtualenv ~/cdpcli/cdpclienv
      source ~/cdpcli/cdpclienv/bin/activate
      ;;
    beta) 
      virtualenv ~/cdpcli/cdpcli-beta
      source ~/cdpcli/cdpcli-beta/bin/activate
      ;;
    *) 
      echo "USAGE: $0 'std|beta'"
      exit 1
      ;;
  esac
}
# do_activate_cdp_cli std|beta

function do_create_cdp_az_env ()
{
  case $1 in
    freeipa-no-custom-img)
    # Latest FreeIPA image with Service EndPoints & Public IPs
      set -x
      cdp environments create-azure-environment \
        --environment-name ${PREFIX}-env \
        --credential-name "${CDP_CREDENTIAL_NAME}" \
        --region "${LOCATION}" \
        --resource-group-name ${RESOURCE_GROUP_NAME} \
        --free-ipa instanceCountByGroup=${FREEIPA_NODES} \
        --enable-tunnel \
        --use-public-ip \
        --workload-analytics \
        --report-deployment-logs \
        --endpoint-access-gateway-scheme PRIVATE \
        --no-create-private-endpoints \
        --existing-network-params networkId=${VNET_NAME},resourceGroupName=${RESOURCE_GROUP_NAME},subnetIds=$(set -- $(az network vnet subnet list -g ${RESOURCE_GROUP_NAME} --vnet-name ${VNET_NAME} | jq -r '.[].name') && while (( $# ));do if [[ $# -gt 1 ]];then printf "$1,"; shift; else printf "$1"; shift; fi; done) \
        --security-access defaultSecurityGroupId=/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Network/networkSecurityGroups/${VNET_NAME}-default-nsg,securityGroupIdForKnox=/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Network/networkSecurityGroups/${VNET_NAME}-knox-nsg \
        --public-key "${PUBLIC_KEY}" \
        --log-storage storageLocationBase=abfs://${LOGS_LOCATION_BASE}@${STORAGE_ACCOUNT_NAME}.dfs.core.windows.net,managedIdentity=/subscriptions/${SUBSCRIPTION_ID}/resourcegroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/${LOGGER_IDENTITY},backupStorageLocationBase=abfs://${BACKUP_LOCATION_BASE}@${STORAGE_ACCOUNT_NAME}.dfs.core.windows.net \
        --tags ${CUSTOM_TAGS} \
        --description "Description of the environment"
      set +x
      ;;
    freeipa-pep-no-custom-img)
    # Latest FreeIPA image with Private EndPoints & Public IPs
      set -x
      cdp environments create-azure-environment \
        --environment-name ${PREFIX}-env \
        --credential-name "${CDP_CREDENTIAL_NAME}" \
        --region "${LOCATION}" \
        --resource-group-name ${RESOURCE_GROUP_NAME} \
        --free-ipa instanceCountByGroup=${FREEIPA_NODES} \
        --enable-tunnel \
        --use-public-ip \
        --workload-analytics \
        --report-deployment-logs \
        --endpoint-access-gateway-scheme PRIVATE \
        --create-private-endpoints \
        --existing-network-params networkId=${VNET_NAME},resourceGroupName=${RESOURCE_GROUP_NAME},subnetIds=$(set -- $(az network vnet subnet list -g ${RESOURCE_GROUP_NAME} --vnet-name ${VNET_NAME} | jq -r '.[].name') && while (( $# ));do if [[ $# -gt 1 ]];then printf "$1,"; shift; else printf "$1"; shift; fi; done),databasePrivateDnsZoneId=/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Network/privateDnsZones/privatelink.postgres.database.azure.com \
        --security-access defaultSecurityGroupId=/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Network/networkSecurityGroups/${VNET_NAME}-default-nsg,securityGroupIdForKnox=/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Network/networkSecurityGroups/${VNET_NAME}-knox-nsg \
        --public-key "${PUBLIC_KEY}" \
        --log-storage storageLocationBase=abfs://${LOGS_LOCATION_BASE}@${STORAGE_ACCOUNT_NAME}.dfs.core.windows.net,managedIdentity=/subscriptions/${SUBSCRIPTION_ID}/resourcegroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/${LOGGER_IDENTITY},backupStorageLocationBase=abfs://${BACKUP_LOCATION_BASE}@${STORAGE_ACCOUNT_NAME}.dfs.core.windows.net \
        --tags ${CUSTOM_TAGS} \
        --description "Description of the environment"
      set +x
      ;;
    freeipa-no-custom-img-priv)
    # Latest FreeIPA image with Service EndPoints & Private IPs
      set -x
      cdp environments create-azure-environment \
        --environment-name ${PREFIX}-env \
        --credential-name "${CDP_CREDENTIAL_NAME}" \
        --region "${LOCATION}" \
        --resource-group-name ${RESOURCE_GROUP_NAME} \
        --free-ipa instanceCountByGroup=${FREEIPA_NODES} \
        --enable-tunnel \
        --no-use-public-ip \
        --workload-analytics \
        --report-deployment-logs \
        --endpoint-access-gateway-scheme PRIVATE \
        --no-create-private-endpoints \
        --existing-network-params networkId=${VNET_NAME},resourceGroupName=${RESOURCE_GROUP_NAME},subnetIds=$(set -- $(az network vnet subnet list -g ${RESOURCE_GROUP_NAME} --vnet-name ${VNET_NAME} | jq -r '.[].name') && while (( $# ));do if [[ $# -gt 1 ]];then printf "$1,"; shift; else printf "$1"; shift; fi; done) \
        --security-access defaultSecurityGroupId=/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Network/networkSecurityGroups/${VNET_NAME}-default-nsg,securityGroupIdForKnox=/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Network/networkSecurityGroups/${VNET_NAME}-knox-nsg \
        --public-key "${PUBLIC_KEY}" \
        --log-storage storageLocationBase=abfs://${LOGS_LOCATION_BASE}@${STORAGE_ACCOUNT_NAME}.dfs.core.windows.net,managedIdentity=/subscriptions/${SUBSCRIPTION_ID}/resourcegroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/${LOGGER_IDENTITY},backupStorageLocationBase=abfs://${BACKUP_LOCATION_BASE}@${STORAGE_ACCOUNT_NAME}.dfs.core.windows.net \
        --tags ${CUSTOM_TAGS} \
        --description "Description of the environment"
      set +x
      ;;
    freeipa-pep-no-custom-img-priv)
    # Latest FreeIPA image with Private EndPoints & Private IPs
      set -x
      cdp environments create-azure-environment \
        --environment-name ${PREFIX}-env \
        --credential-name "${CDP_CREDENTIAL_NAME}" \
        --region "${LOCATION}" \
        --resource-group-name ${RESOURCE_GROUP_NAME} \
        --free-ipa instanceCountByGroup=${FREEIPA_NODES} \
        --enable-tunnel \
        --no-use-public-ip \
        --workload-analytics \
        --report-deployment-logs \
        --endpoint-access-gateway-scheme PRIVATE \
        --create-private-endpoints \
        --existing-network-params networkId=${VNET_NAME},resourceGroupName=${RESOURCE_GROUP_NAME},subnetIds=$(set -- $(az network vnet subnet list -g ${RESOURCE_GROUP_NAME} --vnet-name ${VNET_NAME} | jq -r '.[].name') && while (( $# ));do if [[ $# -gt 1 ]];then printf "$1,"; shift; else printf "$1"; shift; fi; done),databasePrivateDnsZoneId=/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Network/privateDnsZones/privatelink.postgres.database.azure.com \
        --security-access defaultSecurityGroupId=/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Network/networkSecurityGroups/${VNET_NAME}-default-nsg,securityGroupIdForKnox=/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.Network/networkSecurityGroups/${VNET_NAME}-knox-nsg \
        --public-key "${PUBLIC_KEY}" \
        --log-storage storageLocationBase=abfs://${LOGS_LOCATION_BASE}@${STORAGE_ACCOUNT_NAME}.dfs.core.windows.net,managedIdentity=/subscriptions/${SUBSCRIPTION_ID}/resourcegroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/${LOGGER_IDENTITY},backupStorageLocationBase=abfs://${BACKUP_LOCATION_BASE}@${STORAGE_ACCOUNT_NAME}.dfs.core.windows.net \
        --tags ${CUSTOM_TAGS} \
        --description "Description of the environment"
      set +x
      ;;
    *) 
      echo "USAGE: $0 'freeipa-no-custom-img | freeipa-pep-no-custom-img | freeipa-no-custom-img-priv | freeipa-pep-no-custom-img-priv'"
      exit 1
      ;;
  esac
}
# do_create_cdp_az_env 'freeipa-no-custom-img | freeipa-pep-no-custom-img | freeipa-no-custom-img-priv | freeipa-pep-no-custom-img-priv'

function do_create_cdp_sdx ()
{
    case $1 in
    raz-runtime)
      # iDBroker mappings with RAZ
      set -x
      cdp environments set-id-broker-mappings \
      --environment-name ${PREFIX}-env \
      --data-access-role /subscriptions/${SUBSCRIPTION_ID}/resourcegroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/${ADMIN_IDENTITY} \
      --ranger-audit-role /subscriptions/${SUBSCRIPTION_ID}/resourcegroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/${RANGER_AUDIT_LOGGER_IDENTITY} \
      --ranger-cloud-access-authorizer-role /subscriptions/${SUBSCRIPTION_ID}/resourcegroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/${RANGER_RAZ_IDENTITY} \
      --set-empty-mappings

      # Create the Data Lake with RAZ
      cdp datalake create-azure-datalake \
      --datalake-name ${PREFIX}-dl \
      --environment-name ${PREFIX}-env \
      --cloud-provider-configuration managedIdentity=/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/${ASSUMER_IDENTITY},storageLocation=abfs://${STORAGE_LOCATION_BASE}@${STORAGE_ACCOUNT_NAME}.dfs.core.windows.net \
      --tags ${CUSTOM_TAGS} \
      --scale ${DL_SCALE} \
      --enable-ranger-raz \
      --runtime ${RUN_TIME}  
      set +x
      ;;
    no-raz-runtime)
      # idbroker mappings without RAZ
      set -x
      cdp environments set-id-broker-mappings \
      --environment-name ${PREFIX}-env \
      --data-access-role /subscriptions/${SUBSCRIPTION_ID}/resourcegroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/${ADMIN_IDENTITY} \
      --ranger-audit-role /subscriptions/${SUBSCRIPTION_ID}/resourcegroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/${RANGER_AUDIT_LOGGER_IDENTITY} \
      --set-empty-mappings
      
      # Create the Data Lake without RAZ
      cdp datalake create-azure-datalake \
      --datalake-name ${PREFIX}-dl \
      --environment-name ${PREFIX}-env \
      --cloud-provider-configuration managedIdentity=/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/${ASSUMER_IDENTITY},storageLocation=abfs://${STORAGE_LOCATION_BASE}@${STORAGE_ACCOUNT_NAME}.dfs.core.windows.net \
      --tags ${CUSTOM_TAGS} \
      --scale ${DL_SCALE} \
      --runtime ${RUN_TIME}    
      set +x
      ;;
    *) echo "USAGE: $0 'raz-runtime|no-raz-runtime'"
       exit 1
    ;;
  esac
}
# do_create_cdp_sdx no-raz-img

function do_cdp_load_dh_default_templates ()
{
  echo -e "\nUploading Datahub Default Cluster Templates & Definitions...\n"

  DEFAULT_DH_TEMPLATE_COUNT=0
  DEFAULT_DH_DEFINITION_COUNT=0
  oldIFS="${IFS}"
  IFS="|"
  # Load DH Cluster Templates
  for defaultTemplates in $(cdp datahub list-cluster-templates  | jq -r '.clusterTemplates[] | select( .status | contains("DEFAULT")) | "\(.clusterTemplateName)"' | grep "${RUN_TIME}" | grep -v SDX | sort -k2 | awk '{printf "%s %s", NR")", $0"|"}'| sed 's/|$//')
  do
    DEFAULT_DH_TEMPLATES[${DEFAULT_DH_TEMPLATE_COUNT}]=${defaultTemplates}
    (( DEFAULT_DH_TEMPLATE_COUNT += 1 ))
  done

  # Load DH Cluster Definitions
  for defaultDefinitions in $(cdp datahub list-cluster-definitions  | jq -r '.clusterDefinitions[].clusterDefinitionName'  | awk "/${RUN_TIME}/ && /Azure/" | sort -k2 | awk '{printf "%s %s", NR")", $0"|"}' | sed 's/|$//')
  do
    DEFAULT_DH_DEFINITIONS[${DEFAULT_DH_DEFINITION_COUNT}]=${defaultDefinitions}
    (( DEFAULT_DH_DEFINITION_COUNT += 1 ))
  done

  lastContInArrayForTemplates=${#DEFAULT_DH_TEMPLATES[*]}
  lastContArrayForTemplates=$((( lastContInArrayForTemplates - 1 )))

  lastContInArrayForDefinitions=${#DEFAULT_DH_DEFINITIONS[*]}
  lastContArrayForDefinitions=$((( lastContInArrayForDefinitions - 1 )))

  IFS="${oldIFS}"
  
  while true
  do
    echo -e "\nAvailable Datahub Templates for Run Time ${RUN_TIME}:\n"
    
    for val in $( seq 0 ${lastContArrayForTemplates} )
    do
      echo "${DEFAULT_DH_TEMPLATES[${val}]}"
    done
    
    echo -ne "\nSelect a DH template: "
    read DH_TO_INSTALL_OPTION

    if [[ -z ${DH_TO_INSTALL_OPTION} ]]
    then
      echo -e "We need a valid option"
      sleep 2
      continue
    else
      for val in $( seq 0 ${lastContArrayForTemplates} )
      do
        if echo "${DEFAULT_DH_TEMPLATES[${val}]}" | grep "^${DH_TO_INSTALL_OPTION})" > /dev/null 2>&1
        then
          export DEFAULT_DH_TEMPLATE_CHOOSEN="${DEFAULT_DH_TEMPLATES[${val}]}"

          # Definitions for a choosen Template
          while true
          do
            echo -e "\nAvailable Cluster Definitions for these Datahub Templates are:\n"
            for definitionNumber in $( seq 0 ${lastContArrayForDefinitions} )
            do
              echo "${DEFAULT_DH_DEFINITIONS[${definitionNumber}]}"
            done

            echo -ne "\nSelect a Cluster Definition that match with the Cluster Template choosen: "
            read DEFINITION_TO_INSTALL_OPTION

            if [[ -z ${DEFINITION_TO_INSTALL_OPTION} ]]
            then
              echo -e "We need a valid option"
              sleep 2
              continue
            else
              for definitionNumber in $( seq 0 ${lastContArrayForDefinitions} )
              do
                if echo "${DEFAULT_DH_DEFINITIONS[${definitionNumber}]}" | grep "^${DEFINITION_TO_INSTALL_OPTION})" > /dev/null 2>&1
                then
                  export DEFAULT_DH_DEFINITION_CHOOSEN="${DEFAULT_DH_DEFINITIONS[${definitionNumber}]}"
                  break
                fi
              done
              break
            fi
          done      
        fi
      done
      break
    fi    
  done
}

function do_create_dh_default_cluster () 
{

  PREFIX=$1
  # leading whitespace
  # DH_DEFAULT_TEMPLATE="${DH_DEFAULT_TEMPLATE#"${DH_DEFAULT_TEMPLATE%%[![:space:]]*}"}"
  # trailing whitespace
  # DH_DEFAULT_TEMPLATE="${DH_DEFAULT_TEMPLATE%"${DH_DEFAULT_TEMPLATE##*[![:space:]]}"}"
  DH_DEFAULT_TEMPLATE="$(echo $2 | sed 's|^[0-9]*)||')"
  DH_DEFAULT_TEMPLATE="${DH_DEFAULT_TEMPLATE#"${DH_DEFAULT_TEMPLATE%%[![:space:]]*}"}"
  DH_DEFAULT_TEMPLATE="${DH_DEFAULT_TEMPLATE%"${DH_DEFAULT_TEMPLATE##*[![:space:]]}"}"
  DH_DEFINITION_TEMPLATE="$(echo $3 | sed 's|^[0-9]*)||')"
  DH_DEFINITION_TEMPLATE="${DH_DEFINITION_TEMPLATE#"${DH_DEFINITION_TEMPLATE%%[![:space:]]*}"}"
  DH_DEFINITION_TEMPLATE="${DH_DEFINITION_TEMPLATE%"${DH_DEFINITION_TEMPLATE##*[![:space:]]}"}"
  shift 3
  CUSTOM_TAGS=$@

  while true
  do
    echo -ne "\nWhat is the DH Name: "
    read DH_NAME_RESPONSE

    if [[ -z ${DH_NAME_RESPONSE} ]]
    then
      echo -e "Enter a name for your cluster which:
      - Must start with a lowercase letter.
      - Must end with an alphanumeric character.
      - Must only contain lowercase alphanumeric characters and hyphens.
      - Must not exceed 40 Characters"
      sleep 2
      continue
    else
      DH_CLUSTER_NAME=${DH_NAME_RESPONSE}
      break
    fi
  done

  set -x
  cdp datahub create-azure-cluster \
  --cluster-name ${DH_CLUSTER_NAME} \
  --environment-name ${PREFIX}-env \
  --cluster-template-name "${DH_DEFAULT_TEMPLATE}" \
  --cluster-definition-name "${DH_DEFINITION_TEMPLATE}" \
  --tags "${CUSTOM_TAGS}"
  set +x
}
# do_create_dh_default_cluster "${PREFIX}" "${DEFAULT_DH_TEMPLATE_CHOOSEN}" "${DEFAULT_DH_DEFINITION_CHOOSEN}" "${CUSTOM_TAGS}"
