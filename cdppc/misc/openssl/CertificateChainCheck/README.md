# Certificate Chain Check Script

A comprehensive bash script for analyzing SSL/TLS certificate chains, extracting certificate information, and importing CA certificates into a Java truststore.

## 🎯 Purpose

This script automates the process of:

- Fetching complete certificate chains from SSL/TLS endpoints
- Analyzing and displaying detailed certificate information
- Identifying certificate types (Leaf, Intermediate, Root)
- Importing CA certificates into a Java truststore for secure connections

## ✨ Features

- **🔍 Certificate Chain Analysis**: Automatically fetches and analyzes complete certificate chains
- **📊 Detailed Information Display**: Shows Subject, Issuer, CA Flag, and Certificate Type for each certificate
- **🎨 Pretty Output Format**: Clean, organized display with emojis and clear formatting
- **🔐 Truststore Management**: Automatically imports CA certificates into a Java truststore
- **🛡️ Safety Features**: Creates backups of existing truststores before modifications
- **📁 Smart File Naming**: Renames certificate files based on subject information for easy identification

## 📋 Prerequisites

### Required Software

- **OpenSSL**: For certificate chain fetching and analysis
- **Java Keytool**: For truststore management
- **Bash**: Version 4.0 or higher (for associative arrays)

### System Requirements

- Unix-like operating system (Linux, macOS, WSL)
- Bash shell with associative array support
- Sufficient permissions to create temporary directories and files

## 🚀 Usage

### Basic Usage

```bash
./certificateChainCheck.sh <endpoint>[:port]
```

### Examples

```bash
# Check HTTPS endpoint (default port 443)
./certificateChainCheck.sh s3.us-east-1.amazonaws.com

# Check custom port
./certificateChainCheck.sh example.com:8443

# Check internal service
./certificateChainCheck.sh internal-service.company.local:9443
```

## 📖 Output Description

### Certificate Chain Information

The script provides comprehensive analysis including:

1. **Working Directory**: Temporary directory where certificates are processed
2. **Certificate Files**: List of all certificates found in the chain
3. **Detailed Analysis**: For each certificate:
   - 📄 File being analyzed
   - 🔐 Certificate details with Subject, Issuer, CA Flag, and Type
4. **Truststore Import**: Status of CA certificate imports
5. **Final Summary**: List of imported certificates with fingerprints

### Certificate Types Identified

- **Leaf Certificate**: End-entity certificate (CA:FALSE)
- **Intermediate Certificate**: CA certificate that's not self-signed
- **Root Certificate**: Self-signed CA certificate (CA:TRUE + self-signed)

## 🔧 How It Works

### Step-by-Step Process

1. **Endpoint Parsing**: Extracts FQDN and port from input
2. **Certificate Fetching**: Uses OpenSSL to retrieve the complete certificate chain
3. **File Renaming**: Renames certificates based on subject information for clarity
4. **Analysis**: Extracts and displays detailed information for each certificate
5. **Truststore Import**: Imports CA certificates (skips leaf certificates)
6. **Verification**: Displays final truststore contents

### Technical Details

- **OpenSSL Commands**: Uses `s_client` for connection and `x509` for certificate parsing
- **AWK Processing**: Parses certificate text output for Basic Constraints
- **Java Keytool**: Manages truststore operations with automatic backup
- **Temporary Files**: Creates timestamped working directories for isolation

## 📁 File Structure

```
misc/openssl/CertificateChainCheck/
├── certificateChainCheck.sh    # Main script
├── README.md                   # This documentation
└── examples/                   # Example outputs (if any)
```

## ⚠️ Important Notes

### Security Considerations

- **Temporary Files**: Script creates temporary directories that should be cleaned up
- **Truststore Modifications**: Always backs up existing truststores before changes
- **Certificate Validation**: Script displays information but doesn't validate certificate authenticity

### Limitations

- **Single Endpoint**: Processes one endpoint at a time
- **Java Truststore**: Output is specifically for Java applications
- **OpenSSL Dependency**: Requires OpenSSL to be installed and accessible

## 🔄 Script Customization

### Modifying Default Values

- **Truststore Password**: Change `TRUSTSTORE_PASSWORD` variable
- **Working Directory**: Modify `WORKDIR` path if needed
- **Output Format**: Customize echo statements and formatting
