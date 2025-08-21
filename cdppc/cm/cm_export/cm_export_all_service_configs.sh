#!/usr/bin/env bash

# Function: Check for required tools
do_check_dependencies() {
    local missing=0
    for cmd in xmlstarlet jq curl; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            echo "❌ Error: Required command '$cmd' is not installed."
            missing=1
        fi
    done
    if [[ $missing -eq 1 ]]; then
        echo "🔧 Please install the missing packages and re-run the script."
        echo "Example on RHEL: sudo dnf install xmlstarlet jq curl -y"
        exit 1
    fi
}

# Function: Spinner (optional)
do_spin () {
  spinner="/|\\-/|\\-"
  while :
  do
    for i in $(seq 0 7); do
      echo -n "${spinner:$i:1}"
      echo -en "\010"
      sleep 1
    done
  done
}

# Function: Check root user
run_as_root_check () {
    if [[ $(id -u) -ne 0 ]]; then
        echo -e "❌ This script must be run as root. Please use: sudo -i"
        exit 1
    fi
}

# Function: Validate Cloudera credentials
do_test_credentials () {
    curl -s -L -k -u ${WORKLOAD_USER}:${WORKLOAD_USER_PASS} -X GET "${CM_SERVER}/api/version" > /tmp/null 2>&1
    if grep -q "Bad credentials" /tmp/null; then
        echo -e "\n❌ Invalid credentials. Please double-check."
        rm -f /tmp/null
        exit 1
    fi
    rm -f /tmp/null
}

# Helper: Check if property is sensitive
is_sensitive_property() {
    local prop="$1"
    for keyword in password secret token key credential passphrase; do
        if [[ "$prop" =~ $keyword ]]; then
            return 0
        fi
    done
    return 1
}

# Helper: Clean up AUTO_TLS references and escape quotes
sanitize_value() {
    local val="$1"
    echo "$val" | sed 's/{{CM_AUTO_TLS}}/****/g' | tr -d '\n' | sed 's/"/""/g'
}

# Helper: Clean up AUTO_TLS references and escape quotes for role configs (convert newlines to \n for JSON)
sanitize_role_value() {
    local val="$1"
    # Use printf to preserve the value exactly, then replace newlines with \n
    # Use jq to properly escape the value for JSON (this handles newlines correctly)
    # Remove the outer quotes that jq adds since we're building JSON manually
    printf '%s' "$val" | sed 's/{{CM_AUTO_TLS}}/****/g' | sed 's/"/""/g' | jq -Rs . | sed 's/^"//;s/"$//'
}

# Function: Fetch service and role config values and write to master CSV
do_get_roles_configs () {
    # CSV file is now created in main() function, so we just use the global variable
    # Use static API version v53 as per instruction
    local API_VERSION="v53"
    
    # Subfolder for control files
    CONTROL_SUBFOLDER="${OUTPUT_DIR}/api_control_files"
    mkdir -p "${CONTROL_SUBFOLDER}/service_configs"
    mkdir -p "${CONTROL_SUBFOLDER}/role_configs"

    # Create separate subfolders for Cluster and MGMT services
    mkdir -p "${OUTPUT_DIR}/ServiceConfigs/ClusterServices"
    mkdir -p "${OUTPUT_DIR}/ServiceConfigs/MGMT_Services"
    mkdir -p "${OUTPUT_DIR}/roleConfigGroups/ClusterServices"
    mkdir -p "${OUTPUT_DIR}/roleConfigGroups/MGMT_Services"

    # Control files for GET and PUT (apply) calls - SEPARATE for Cluster vs MGMT
    # Cluster Services
    CLUSTER_SERVICE_GET_CONTROL="${CONTROL_SUBFOLDER}/service_configs/get_cluster_service_config_calls.csv"
    CLUSTER_SERVICE_PUT_CONTROL="${CONTROL_SUBFOLDER}/service_configs/put_cluster_service_config_calls.csv"
    CLUSTER_ROLE_GET_CONTROL="${CONTROL_SUBFOLDER}/role_configs/get_cluster_role_config_calls.csv"
    CLUSTER_ROLE_PUT_CONTROL="${CONTROL_SUBFOLDER}/role_configs/put_cluster_role_config_calls.csv"
    
    # MGMT Services
    MGMT_SERVICE_GET_CONTROL="${CONTROL_SUBFOLDER}/service_configs/get_mgmt_service_config_calls.csv"
    MGMT_SERVICE_PUT_CONTROL="${CONTROL_SUBFOLDER}/service_configs/put_mgmt_service_config_calls.csv"
    MGMT_ROLE_GET_CONTROL="${CONTROL_SUBFOLDER}/role_configs/get_mgmt_role_config_calls.csv"
    MGMT_ROLE_PUT_CONTROL="${CONTROL_SUBFOLDER}/role_configs/put_mgmt_role_config_calls.csv"

    # Write headers for all control files
    echo "service_name,api_get_call" > "$CLUSTER_SERVICE_GET_CONTROL"
    echo "service_name,property,api_put_call" > "$CLUSTER_SERVICE_PUT_CONTROL"
    echo "service_name,role_name,api_get_call" > "$CLUSTER_ROLE_GET_CONTROL"
    echo "service_name,role_name,property,api_put_call" > "$CLUSTER_ROLE_PUT_CONTROL"
    
    echo "service_name,api_get_call" > "$MGMT_SERVICE_GET_CONTROL"
    echo "service_name,property,api_put_call" > "$MGMT_SERVICE_PUT_CONTROL"
    echo "service_name,role_name,api_get_call" > "$MGMT_ROLE_GET_CONTROL"
    echo "service_name,role_name,property,api_put_call" > "$MGMT_ROLE_PUT_CONTROL"

    # ---- CLUSTER SERVICES ----
    echo -e "\n=== Processing Cluster Services ==="
    
    # Get cluster services
    CLUSTER_SERVICES_RESPONSE=$(curl -s -L -k -u "${WORKLOAD_USER}:${WORKLOAD_USER_PASS}" \
        -X GET "${CM_SERVER}/api/${API_VERSION}/clusters/${CM_CLUSTER_NAME}/services")
    
    # Check if we got a valid response with items
    if [[ $(echo "$CLUSTER_SERVICES_RESPONSE" | jq -r '.items // empty' | wc -l) -gt 0 ]]; then
        for CLUSTER_SERVICE_NAME in $(echo "$CLUSTER_SERVICES_RESPONSE" | jq -r '.items[].name'); do

            echo -e "\n--- Processing Cluster Service: ${CLUSTER_SERVICE_NAME} ---"

            SERVICE_JSON_FILE="${OUTPUT_DIR}/ServiceConfigs/ClusterServices/${HOSTNAME_FQDN}_${CM_CLUSTER_NAME}_${CLUSTER_SERVICE_NAME}_config.json"
            SERVICE_API_URI="${CM_SERVER}/api/${API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERVICE_NAME}/config?view=summary"

            # Write GET API call for service config
            SERVICE_GET_CMD="curl -s -L -k -u \"\${WORKLOAD_USER}:*****\" -X GET \"${SERVICE_API_URI}\""
            echo "${CLUSTER_SERVICE_NAME},${SERVICE_GET_CMD}" >> "$CLUSTER_SERVICE_GET_CONTROL"

            # ---- SERVICE CONFIGS ----
            curl -s -L -k -u "${WORKLOAD_USER}:${WORKLOAD_USER_PASS}" \
                -X GET "$SERVICE_API_URI" \
                | tee "$SERVICE_JSON_FILE" \
                | jq -c '.items[]' \
                | while IFS= read -r item; do
                    key=$(echo "$item" | jq -r '.name')
                    val=$(echo "$item" | jq -r '.value')
                    val_cleaned=$(sanitize_value "$val")

                    if [[ "$val_cleaned" == \<property* ]]; then
                        while IFS='|' read -r sub_key sub_val; do
                            is_sensitive_property "$sub_key" && sub_val="****"
                            
                            echo "service,${CLUSTER_SERVICE_NAME},${sub_key},\"${sub_val}\",\"${SERVICE_API_URI}\"" >> "$MASTER_CSV_FILE"
                            
                            # Write PUT API call for service config property
                            # Generate properly formatted, multi-line JSON payload
                            SERVICE_PUT_CMD="curl -s -L -k -u \"\${WORKLOAD_USER}:*****\" -X PUT \"${CM_SERVER}/api/${API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERVICE_NAME}/config\" -H 'content-type:application/json' -d '{
  \"items\": [
    {
      \"name\": \"${sub_key}\",
      \"value\": \"${sub_val}\"
    }
  ]
}'"
                            echo "${CLUSTER_SERVICE_NAME},${sub_key},${SERVICE_PUT_CMD}" >> "$CLUSTER_SERVICE_PUT_CONTROL"
                        done < <(echo "<configuration>${val_cleaned}</configuration>" \
                            | xmlstarlet sel -t -m "//property" -v "concat(name,'|',value)" -n)
                    else
                        is_sensitive_property "$key" && val_cleaned="****"
                        echo "service,${CLUSTER_SERVICE_NAME},${key},\"${val_cleaned}\",\"${SERVICE_API_URI}\"" >> "$MASTER_CSV_FILE"
                        # Write PUT API call for service config property
                        # Generate properly formatted, multi-line JSON payload
                        SERVICE_PUT_CMD="curl -s -L -k -u \"\${WORKLOAD_USER}:*****\" -X PUT \"${CM_SERVER}/api/${API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERVICE_NAME}/config\" -H 'content-type:application/json' -d '{
  \"items\": [
    {
      \"name\": \"${key}\",
      \"value\": \"${val_cleaned}\"
    }
  ]
}'"
                        echo "${CLUSTER_SERVICE_NAME},${key},${SERVICE_PUT_CMD}" >> "$CLUSTER_SERVICE_PUT_CONTROL"
                    fi
                done

            # ---- ROLE CONFIG GROUPS ----
            for ROLE in $(curl -s -L -k -u "${WORKLOAD_USER}:${WORKLOAD_USER_PASS}" \
                -X GET "${CM_SERVER}/api/${API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERVICE_NAME}/roleConfigGroups" \
                | jq -r '.items[]?.name // empty'); do

                ROLE_JSON_FILE="${OUTPUT_DIR}/roleConfigGroups/ClusterServices/${HOSTNAME_FQDN}_${CM_CLUSTER_NAME}_${CLUSTER_SERVICE_NAME}_${ROLE}_config.json"
                ROLE_API_URI="${CM_SERVER}/api/${API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERVICE_NAME}/roleConfigGroups/${ROLE}/config?view=summary"
                ROLE_GET_CMD="curl -s -L -k -u \"\${WORKLOAD_USER}:*****\" -X GET \"${ROLE_API_URI}\""
                echo "${CLUSTER_SERVICE_NAME},${ROLE},${ROLE_GET_CMD}" >> "$CLUSTER_ROLE_GET_CONTROL"

                curl -s -L -k -u "${WORKLOAD_USER}:${WORKLOAD_USER_PASS}" \
                    -X GET "$ROLE_API_URI" \
                    | tee "$ROLE_JSON_FILE" \
                    | jq -c '.items[]' \
                    | while IFS= read -r item; do
                        key=$(echo "$item" | jq -r '.name')
                        val=$(echo "$item" | jq -r '.value')
                        val_cleaned=$(sanitize_role_value "$val")
                        
                        # For role configs, treat all properties as single properties with their complete values
                        is_sensitive_property "$key" && val_cleaned="****"
                        echo "role,${ROLE},${key},\"${val_cleaned}\",\"${ROLE_API_URI}\"" >> "$MASTER_CSV_FILE"
                        
                        # Write PUT API call for role config property - single payload per property
                        # Generate properly formatted, multi-line JSON payload
                        ROLE_PUT_CMD="curl -s -L -k -u \"\${WORKLOAD_USER}:*****\" -X PUT \"${CM_SERVER}/api/${API_VERSION}/clusters/${CM_CLUSTER_NAME}/services/${CLUSTER_SERVICE_NAME}/roleConfigGroups/${ROLE}/config\" -H 'content-type:application/json' -d '{
  \"items\": [
    {
      \"name\": \"${key}\",
      \"value\": \"${val_cleaned}\"
    }
  ]
}'"
                        echo "${CLUSTER_SERVICE_NAME},${ROLE},${key},${ROLE_PUT_CMD}" >> "$CLUSTER_ROLE_PUT_CONTROL"
                    done
            done
        done
    else
        echo -e "\n--- No cluster services found or API returned null response ---"
    fi

    # ---- MGMT SERVICES ----
    echo -e "\n=== Processing MGMT Services ==="
    
    # Get MGMT role config groups (this gives us the actual configs)
    MGMT_ROLE_CONFIG_GROUPS_RESPONSE=$(curl -s -L -k -u "${WORKLOAD_USER}:${WORKLOAD_USER_PASS}" \
        -X GET "${CM_SERVER}/api/${API_VERSION}/cm/service/roleConfigGroups")
    
    # Check if we got a valid response with items
    if [[ $(echo "$MGMT_ROLE_CONFIG_GROUPS_RESPONSE" | jq -r '.items // empty' | wc -l) -gt 0 ]]; then
        for MGMT_ROLE_CONFIG_GROUP in $(echo "$MGMT_ROLE_CONFIG_GROUPS_RESPONSE" | jq -r '.items[].name'); do

            # ---- MGMT ROLE CONFIG GROUPS (using /cm/service/roleConfigGroups/{GROUP}/config) ----
            MGMT_ROLE_CONFIG_URI="${CM_SERVER}/api/${API_VERSION}/cm/service/roleConfigGroups/${MGMT_ROLE_CONFIG_GROUP}/config"
            
            # Write GET API call for MGMT role config group
            MGMT_ROLE_GET_CMD="curl -s -L -k -u \"\${WORKLOAD_USER}:*****\" -X GET \"${MGMT_ROLE_CONFIG_URI}\""
            echo "${MGMT_ROLE_CONFIG_GROUP},${MGMT_ROLE_CONFIG_GROUP},${MGMT_ROLE_GET_CMD}" >> "$MGMT_ROLE_GET_CONTROL"

            # Get MGMT role config group config
            MGMT_ROLE_CONFIG_RESPONSE=$(curl -s -L -k -u "${WORKLOAD_USER}:${WORKLOAD_USER_PASS}" \
                -X GET "$MGMT_ROLE_CONFIG_URI")
            
            if [[ $(echo "$MGMT_ROLE_CONFIG_RESPONSE" | jq -r '.items // empty' | wc -l) -gt 0 ]]; then
                MGMT_ROLE_JSON_FILE="${OUTPUT_DIR}/roleConfigGroups/MGMT_Services/${HOSTNAME_FQDN}_MGMT_${MGMT_ROLE_CONFIG_GROUP}_role_config.json"
                
                echo "$MGMT_ROLE_CONFIG_RESPONSE" | tee "$MGMT_ROLE_JSON_FILE" \
                    | jq -c '.items[]' \
                    | while IFS= read -r item; do
                        key=$(echo "$item" | jq -r '.name')
                        val=$(echo "$item" | jq -r '.value')
                        val_cleaned=$(sanitize_role_value "$val")
                        
                        # For MGMT role configs, treat all properties as single properties with their complete values
                        is_sensitive_property "$key" && val_cleaned="****"
                        echo "mgmt_role,${MGMT_ROLE_CONFIG_GROUP},${key},\"${val_cleaned}\",\"${MGMT_ROLE_CONFIG_URI}\"" >> "$MASTER_CSV_FILE"
                        
                        # Write PUT API call for MGMT role config property - single payload per property
                        # Generate properly formatted, multi-line JSON payload
                        MGMT_ROLE_PUT_CMD="curl -s -L -k -u \"\${WORKLOAD_USER}:*****\" -X PUT \"${MGMT_ROLE_CONFIG_URI}\" -H 'content-type:application/json' -d '{
  \"items\": [
    {
      \"name\": \"${key}\",
      \"value\": \"${val_cleaned}\"
    }
  ]
}'"
                        echo "${MGMT_ROLE_CONFIG_GROUP},${MGMT_ROLE_CONFIG_GROUP},${key},${MGMT_ROLE_PUT_CMD}" >> "$MGMT_ROLE_PUT_CONTROL"
                    done
            else
                echo "  --- No config items found for MGMT role config group: ${MGMT_ROLE_CONFIG_GROUP} ---"
            fi
        done
    else
        echo -e "\n--- No MGMT role config groups found or API returned null response ---"
    fi

    # Also get MGMT service configs (these are the service-level configs)
    echo -e "\n--- Processing MGMT Service Configs ---"
    
    # Get MGMT service configs using /cm/service/config
    MGMT_SERVICE_CONFIG_URI="${CM_SERVER}/api/${API_VERSION}/cm/service/config"
    
    # Write GET API call for MGMT service config
    MGMT_SERVICE_GET_CMD="curl -s -L -k -u \"\${WORKLOAD_USER}:*****\" -X GET \"${MGMT_SERVICE_CONFIG_URI}\""
    echo "MGMT,${MGMT_SERVICE_GET_CMD}" >> "$MGMT_SERVICE_GET_CONTROL"

    # Get MGMT service config
    MGMT_SERVICE_RESPONSE=$(curl -s -L -k -u "${WORKLOAD_USER}:${WORKLOAD_USER_PASS}" \
        -X GET "$MGMT_SERVICE_CONFIG_URI")
    
    if [[ $(echo "$MGMT_SERVICE_RESPONSE" | jq -r '.items // empty' | wc -l) -gt 0 ]]; then
        MGMT_SERVICE_JSON_FILE="${OUTPUT_DIR}/ServiceConfigs/MGMT_Services/${HOSTNAME_FQDN}_MGMT_service_config.json"
        
        echo "$MGMT_SERVICE_RESPONSE" | tee "$MGMT_SERVICE_JSON_FILE" \
            | jq -c '.items[]' \
            | while IFS= read -r item; do
                key=$(echo "$item" | jq -r '.name')
                val=$(echo "$item" | jq -r '.value')
                val_cleaned=$(sanitize_value "$val")

                if [[ "$val_cleaned" == \<property* ]]; then
                    while IFS='|' read -r sub_key sub_val; do
                        is_sensitive_property "$sub_key" && sub_val="****"
                        echo "mgmt_service,MGMT,${sub_key},\"${sub_val}\",\"${MGMT_SERVICE_CONFIG_URI}\"" >> "$MASTER_CSV_FILE"
                        # Write PUT API call for MGMT service config property
                        # Generate properly formatted, multi-line JSON payload
                        MGMT_SERVICE_PUT_CMD="curl -s -L -k -u \"\${WORKLOAD_USER}:*****\" -X PUT \"${MGMT_SERVICE_CONFIG_URI}\" -H 'content-type:application/json' -d '{
  \"items\": [
    {
      \"name\": \"${sub_key}\",
      \"value\": \"${sub_val}\"
    }
  ]
}'"
                        echo "MGMT,${sub_key},${MGMT_SERVICE_PUT_CMD}" >> "$MGMT_SERVICE_PUT_CONTROL"
                    done < <(echo "<configuration>${val_cleaned}</configuration>" \
                        | xmlstarlet sel -t -m "//property" -v "concat(name,'|',value)" -n)
                else
                    is_sensitive_property "$key" && val_cleaned="****"
                    echo "mgmt_service,MGMT,${key},\"${val_cleaned}\",\"${MGMT_SERVICE_CONFIG_URI}\"" >> "$MASTER_CSV_FILE"
                    # Write PUT API call for MGMT service config property
                    # Generate properly formatted, multi-line JSON payload
                    MGMT_SERVICE_PUT_CMD="curl -s -L -k -u \"\${WORKLOAD_USER}:*****\" -X PUT \"${MGMT_SERVICE_CONFIG_URI}\" -H 'content-type:application/json' -d '{
  \"items\": [
    {
      \"name\": \"${key}\",
      \"value\": \"${val_cleaned}\"
    }
  ]
}'"
                    echo "MGMT,${key},${MGMT_SERVICE_PUT_CMD}" >> "$MGMT_SERVICE_PUT_CONTROL"
                fi
            done
    else
        echo "--- No MGMT service config items found ---"
    fi

    # Save the master CSV file path for later use
    MASTER_CSV_FILE_PATH="$MASTER_CSV_FILE"

    # Print API doc reference
    echo -e "\nAccess API DOC (STATIC):"
    echo "https://$(hostname -f)/static/apidocs/index.html"
    
    # Create the tar archive here where we have access to the CSV file
    echo -e "\n🎯 Output directory: ${OUTPUT_DIR}"
    echo "📦 Creating archive..."
    
    if [[ -n "$MASTER_CSV_FILE_PATH" && -f "$MASTER_CSV_FILE_PATH" ]]; then
        CSV_FILENAME=$(basename "$MASTER_CSV_FILE_PATH")
        tar czf "${OUTPUT_DIR}/ServiceConfigs_roleConfigGroups_$(date +"%Y%m%d%H%M%S").tgz" \
            -C "${OUTPUT_DIR}" ServiceConfigs roleConfigGroups api_control_files "$CSV_FILENAME"
        echo -e "\n✅ Archive created successfully:"
        ls -lh "${OUTPUT_DIR}/ServiceConfigs_roleConfigGroups_"*.tgz
    else
        echo -e "\n⚠️  Warning: CSV file not found. Creating archive without CSV."
        tar czf "${OUTPUT_DIR}/ServiceConfigs_roleConfigGroups_$(date +"%Y%m%d%H%M%S").tgz" \
            -C "${OUTPUT_DIR}" ServiceConfigs roleConfigGroups api_control_files
        echo -e "\n✅ Archive created (without CSV):"
        ls -lh "${OUTPUT_DIR}/ServiceConfigs_roleConfigGroups_"*.tgz
    fi
}

# Function: Main
main () {
    run_as_root_check
    do_check_dependencies
    clear

    read -p "What is your Workload username: " WORKLOAD_USER
    echo -n "Enter your Workload user Password: "
    unset WORKLOAD_USER_PASS
    unset CHARTCOUNT

    while IFS= read -r -n1 -s CHAR; do
        case "${CHAR}" in
        $'\0') break ;;
        $'\177') # backspace
            if [ ${#WORKLOAD_USER_PASS} -gt 0 ]; then
                echo -ne "\b \b"
                WORKLOAD_USER_PASS=${WORKLOAD_USER_PASS::-1}
            fi ;;
        *) echo -n '*' ; WORKLOAD_USER_PASS+="${CHAR}" ;;
        esac
    done
    echo

    export CM_SERVER_DB_FILE=/etc/cloudera-scm-server/db.properties
    export CM_DB_HOST=$(awk -F"=" '/db.host/ {print $NF}' ${CM_SERVER_DB_FILE})
    export CM_DB_NAME=$(awk -F"=" '/db.name/ {print $NF}' ${CM_SERVER_DB_FILE})
    export CM_DB_USER=$(awk -F"=" '/db.user/ {print $NF}' ${CM_SERVER_DB_FILE})
    export PGPASSWORD=$(awk -F"=" '/db.password/ {print $NF}' ${CM_SERVER_DB_FILE})

    export CM_CLUSTER_NAME=$(echo -e "SELECT name FROM clusters;" \
        | psql -h ${CM_DB_HOST} -U ${CM_DB_USER} -d ${CM_DB_NAME} \
        | grep -v Proxy | tail -n 3 | head -n1 | sed 's| ||g')

    export CM_SERVER="https://$(hostname -f):7183"
    export OUTPUT_DIR=/tmp/$(hostname -f)/$(date +"%Y%m%d%H%M%S")

    # Create the master CSV file here, before calling do_get_roles_configs
    timestamp=$(date +"%Y%m%d%H%M%S")
    export DATAHUBNAME="${CM_CLUSTER_NAME:-datahub}"
    export HOSTNAME_FQDN="$(hostname -f)"
    
    # Create the output directory FIRST, before trying to create files in it
    mkdir -p "$OUTPUT_DIR"
    
    # Create the master CSV file name and make it global
    export MASTER_CSV_FILE="${OUTPUT_DIR}/${HOSTNAME_FQDN}_${DATAHUBNAME}_all_services_config_${timestamp}.csv"
    
    # Create the CSV file
    echo "type,service_or_role,property,value,api_uri" > "$MASTER_CSV_FILE"
    
    do_test_credentials

    do_get_roles_configs
}

# Start
ps -eo pid,user,command | grep $(systemctl status cloudera-scm-server | awk '/Main PID:/ {print $3}') \
    | grep -v "grep" | grep 'com.cloudera.api.redaction' >/dev/null 2>&1

if [[ $? -eq 0 ]]; then
    main
else
    echo -e "🚫 Cloudera API redaction is enabled. Please disable it:\n"
    cat <<EOF
1. Backup and edit: /etc/default/cloudera-scm-server
2. Add to CMF_JAVA_OPTS:
   -Dcom.cloudera.api.redaction=false
3. Restart Cloudera Manager:
   systemctl restart cloudera-scm-server
4. Rerun this script.
EOF
    exit 1
fi