#!/bin/bash -e

# Recipe: Configure Hive Compactor Worker Threads
# Description: Sets hive_compactor_worker_threads to 0 during cluster creation
# Author: Jimmy Garagorry
# Version: 1.0

set -euo pipefail

# Configuration variables using Cloudera recipe template variables
CM_HOST="{{{ general.primaryGatewayInstanceDiscoveryFQDN }}}"
CM_PORT="7183"
CM_USERNAME="{{{ general.cmUserName }}}"
CM_PASSWORD="{{{ general.cmPassword }}}"
CLUSTER_NAME="{{{ general.clusterName }}}"
HIVE_COMPACTOR_WORKER_THREADS="0"

# Set up curl options following Cloudera recipe format
CM_SERVER="https://${CM_HOST}:${CM_PORT}"
CURL_OPTIONS="-s -L -k -u ${CM_USERNAME}:${CM_PASSWORD} --noproxy '*'"

# Dynamic API version - will be set after CM accessibility check
CM_API_VERSION=""

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >&2
}

# Error handling function
handle_error() {
    log "ERROR: $1"
    exit 1
}

# Function to check if CM is accessible and get API version
check_cm_accessibility() {
    log "Checking Cloudera Manager accessibility and retrieving API version..."
    
    # Get API version dynamically
    local api_version_response
    api_version_response=$(curl ${CURL_OPTIONS} -X GET "${CM_SERVER}/api/version" 2>/dev/null)
    
    if [[ -z "$api_version_response" ]]; then
        handle_error "Cannot access Cloudera Manager at ${CM_HOST}:${CM_PORT} or retrieve API version"
    fi
    
    # Extract API version from response
    # Check if response is JSON format or plain version
    if echo "$api_version_response" | grep -q '"version"'; then
        # JSON format: {"version":"v53"}
        CM_API_VERSION=$(echo "$api_version_response" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
    else
        # Plain format: v53
        CM_API_VERSION=$(echo "$api_version_response" | tr -d '\n\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    fi
    
    if [[ -z "$CM_API_VERSION" ]]; then
        handle_error "Failed to extract API version from response: $api_version_response"
    fi
    
    log "Cloudera Manager is accessible"
    log "API Version: ${CM_API_VERSION}"
}

# Function to check if cluster exists
check_cluster_exists() {
    log "Checking if cluster '${CLUSTER_NAME}' exists..."
    if ! curl ${CURL_OPTIONS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CLUSTER_NAME}" > /dev/null 2>&1; then
        handle_error "Cluster '${CLUSTER_NAME}' does not exist or is not accessible"
    fi
    log "Cluster '${CLUSTER_NAME}' exists"
}

# Function to check if Hive service exists using dynamic service discovery
check_hive_service() {
    log "Checking if Hive service exists in cluster '${CLUSTER_NAME}'..."
    
    # Get list of services using the same pattern as cdppc_cm_services_api_control.sh
    local services
    services=$(curl ${CURL_OPTIONS} -X GET "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CLUSTER_NAME}/services" | jq -r '.items[].name')
    
    if ! echo "$services" | grep -q "hive_on_tez"; then
        handle_error "Hive service (hive_on_tez) does not exist in cluster '${CLUSTER_NAME}'. Available services: $(echo "$services" | tr '\n' ' ')"
    fi
    log "Hive service (hive_on_tez) exists in cluster"
}

# Function to configure hive_compactor_worker_threads
configure_hive_compactor() {
    log "Configuring hive_compactor_worker_threads to ${HIVE_COMPACTOR_WORKER_THREADS}..."
    
    local response
    local http_code
    
    response=$(curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -w "\n%{http_code}" -X PUT \
        "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CLUSTER_NAME}/services/hive_on_tez/config" \
        -d "{
            \"items\": [
                {
                    \"name\": \"hive_compactor_worker_threads\",
                    \"value\": ${HIVE_COMPACTOR_WORKER_THREADS}
                }
            ]
        }")
    
    http_code=$(echo "$response" | tail -n1)
    response_body=$(echo "$response" | head -n -1)
    
    if [[ "$http_code" -eq 200 ]]; then
        log "Successfully configured hive_compactor_worker_threads to ${HIVE_COMPACTOR_WORKER_THREADS}"
        log "Response: $response_body"
    else
        handle_error "Failed to configure hive_compactor_worker_threads. HTTP Code: $http_code, Response: $response_body"
    fi
}

# Function to restart Hive service if needed
restart_hive_service() {
    log "Restarting Hive service to apply configuration changes..."
    
    local response
    local http_code
    
    curl ${CURL_OPTIONS} -H "accept: application/json" -H "Content-Type: application/json" -X POST "${CM_SERVER}/api/${CM_API_VERSION}/clusters/${CLUSTER_NAME}/services/hive_on_tez/commands/restart"
    
    log "Successfully initiated Hive service restart"
}

# Main execution
main() {
    log "Starting Hive Compactor configuration recipe..."
    log "Configuration:"
    log "  CM Host: ${CM_HOST}:${CM_PORT}"
    log "  Cluster Name: ${CLUSTER_NAME}"
    log "  Hive Compactor Worker Threads: ${HIVE_COMPACTOR_WORKER_THREADS}"
    
    # Validate required parameters
    if [[ -z "${CLUSTER_NAME}" || "${CLUSTER_NAME}" =~ \{\{\{.*\}\}\} ]]; then
        handle_error "CLUSTER_NAME must be set and cannot be a template placeholder"
    fi
    
    # Execute configuration steps
    check_cm_accessibility
    check_cluster_exists
    check_hive_service
    configure_hive_compactor
    
    # Restart service to apply configuration changes
    restart_hive_service
    
    log "Hive Compactor configuration recipe completed successfully"
}

# Execute main function
main "$@"
