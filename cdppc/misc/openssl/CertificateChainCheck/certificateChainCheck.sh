#!/bin/bash

# Enable strict error handling and debugging (uncomment as needed)
# set -x          # Debug mode - shows each command before execution
# set -euo pipefail  # Exit on error, undefined variables, pipe failures

# --- Usage & Argument Parsing ---
usage() {
    echo "Usage: $0 <endpoint>[:port]"
    echo "  Example: $0 s3.us-east-1.amazonaws.com:443"
    exit 1
}

if [[ $# -lt 1 ]]; then
    usage
fi

# Parse endpoint and optional port from command line argument
ENDPOINT_PORT="$1"
if [[ "${ENDPOINT_PORT}" == *:* ]]; then
    # Extract FQDN and port if port is specified (e.g., "example.com:8443")
    SERVER_FQDN="${ENDPOINT_PORT%%:*}"
    SERVER_SSL_PORT="${ENDPOINT_PORT##*:}"
else
    # Use default HTTPS port 443 if no port specified
    SERVER_FQDN="${ENDPOINT_PORT}"
    SERVER_SSL_PORT=443
fi

# Create unique working directory with timestamp
WORKDIR="/tmp/ssl_$(date +"%Y%m%d%H%M%S")"
TRUSTSTORE_PATH="${WORKDIR}/truststore.jks"
TRUSTSTORE_PASSWORD="changeit"

# --- Preparation ---
# Create and navigate to working directory
mkdir -p "${WORKDIR}"
cd "${WORKDIR}"
echo "Working directory: ${WORKDIR}"

# --- Step 1: Capture Certificate Chain ---
# Fetch the complete certificate chain from the endpoint using OpenSSL
echo "Fetching certificate chain from ${SERVER_FQDN}:${SERVER_SSL_PORT}..."
openssl s_client -showcerts -connect "${SERVER_FQDN}:${SERVER_SSL_PORT}" < /dev/null 2>/dev/null \
| awk 'BEGIN{c=0}/BEGIN CERTIFICATE/{c++}{ if (c>0) print > ("cert" c ".crt") }'

# --- Step 2: Identify Chain Order and Rename Certificates ---
# Extract subject and issuer information from each certificate and rename files
echo "Renaming certificates based on subject value..."

CERT_INDEX=1
for cert in cert*.crt; do
    # Extract subject and issuer information from certificate
    SUBJECT=$(openssl x509 -in "${cert}" -noout -subject | sed 's/^subject= //')
    ISSUER=$(openssl x509 -in "${cert}" -noout -issuer | sed 's/^issuer= //')
    
    # Create sanitized filename from subject (replace special chars with underscores)
    SAFE_NAME=$(echo "${SUBJECT}" | sed -E 's/[^A-Za-z0-9._-]+/_/g; s/^_+|_+$//g')
    FILENAME="${SAFE_NAME}.pem"
    
    # Rename certificate file
    mv "${cert}" "${FILENAME}"
    
    echo "Renamed cert${CERT_INDEX} to ${FILENAME}"
    ((CERT_INDEX++))
done

# --- Step 3: Certificate Renaming Complete ---


# --- Helper Function: Extract CA Flag from Basic Constraints ---
# Determines if a certificate is a CA (Certificate Authority) by parsing the Basic Constraints extension
get_ca_flag() {
    local cert_file="$1"
    local result
    
    # Parse the certificate text output to find Basic Constraints
    # Look for the line after "X509v3 Basic Constraints:" and extract CA:TRUE or CA:FALSE
    result=$(openssl x509 -in "${cert_file}" -noout -text 2>/dev/null | awk '
        /^[[:space:]]*X509v3 Basic Constraints:/ { 
            getline
            if ($0 ~ /CA:[[:space:]]*TRUE/)  { print "TRUE";  exit }
            if ($0 ~ /CA:[[:space:]]*FALSE/) { print "FALSE"; exit }
        }
        END {
            if (NR == 0) print "ERROR"
        }
    ')
    
    # Return ERROR if no result found, otherwise return the CA flag
    if [[ -z "$result" ]]; then
        echo "ERROR"
    else
        echo "$result"
    fi
}

# --- Step 4: Detailed Certificate Analysis with Pretty Output ---
# Analyze each certificate in the chain and display detailed information
echo -e "\n=== Detailed Certificate Information ==="
LEAF_COUNT=0

for cert in *.pem; do
    echo "📄 Analyzing: ${cert}"
    
    # Display certificate information in a formatted, readable way
    echo "🔐 Certificate Details"
    echo "----------------------"
    
    # Extract and display Subject (who the certificate is for)
    SUBJECT=$(openssl x509 -in "${cert}" -noout -subject | sed 's/^subject= */Subject: /')
    echo "${SUBJECT}"
    
    # Extract and display Issuer (who signed the certificate)
    ISSUER=$(openssl x509 -in "${cert}" -noout -issuer | sed 's/^issuer= */Issuer:  /')
    echo "${ISSUER}"
    
    # Determine if this certificate is a CA (Certificate Authority)
    CA_FLAG=$(get_ca_flag "${cert}")
    echo "CA Flag      : ${CA_FLAG}"
    
    # Determine certificate type based on CA flag and self-signed status
    SUBJECT_VALUE=$(echo "${SUBJECT}" | awk -F': ' '{print $2}')
    ISSUER_VALUE=$(echo "${ISSUER}" | awk -F': ' '{print $2}')
    
    if [[ "${CA_FLAG}" == "FALSE" ]]; then
        CERT_TYPE="Leaf Certificate"
    elif [[ "${SUBJECT_VALUE}" == "${ISSUER_VALUE}" && "${CA_FLAG}" == "TRUE" ]]; then
        CERT_TYPE="Root Certificate"
    else
        CERT_TYPE="Intermediate Certificate"
    fi
    
    echo "Type         : ${CERT_TYPE}"
    
    # Count leaf certificates for validation (should be exactly 1)
    if [[ "${CA_FLAG}" == "FALSE" ]]; then
        ((LEAF_COUNT++))
    fi
    
    echo
done

# Validate that we have exactly one leaf certificate (end-entity certificate)
if [[ ${LEAF_COUNT} -ne 1 ]]; then
    echo "⚠️  Warning: Expected exactly 1 leaf certificate, found ${LEAF_COUNT}."
fi

# --- Step 5: Backup Existing Truststore ---
# Create backup of existing truststore if it exists to prevent data loss
if [[ -f "${TRUSTSTORE_PATH}" ]]; then
    BACKUP_PATH="${TRUSTSTORE_PATH}.bak_$(date +%s)"
    cp "${TRUSTSTORE_PATH}" "${BACKUP_PATH}"
    echo "Backed up existing truststore to ${BACKUP_PATH}"
fi

# --- Step 6: Import CA Certificates to Truststore ---
# Import only CA certificates (skip leaf certificates) to establish trust chain
echo -e "Importing CA certificates into truststore...\n"
for cert in *.pem; do
    # Check if this certificate is a CA (skip leaf certificates)
    CA_FLAG=$(get_ca_flag "${cert}")
    if [[ "${CA_FLAG}" == "FALSE" ]]; then
        echo -e "⏭️  Skipping leaf certificate: ${cert}"
        continue
    fi
    
    # Create alias from filename and import certificate
    CERT_ALIAS=$(basename "${cert}" .pem)
    echo -e "📥 Importing ${cert} with alias ${CERT_ALIAS}..."
    keytool -importcert -noprompt \
        -alias "${CERT_ALIAS}" \
        -file "${cert}" \
        -keystore "${TRUSTSTORE_PATH}" \
        -storepass "${TRUSTSTORE_PASSWORD}" > /dev/null 2>&1
done

# --- Step 7: Verification and Summary ---
# Display summary of imported certificates and verify truststore contents
echo -e "\n✅ Done. Trusted CA certificates for ${SERVER_FQDN} added to ${TRUSTSTORE_PATH}"
keytool -list -keystore "${TRUSTSTORE_PATH}" -storepass "${TRUSTSTORE_PASSWORD}" | grep '^subject'
echo

