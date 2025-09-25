# Custom Certificate Authority Generator

A robust Python script for generating a complete PKI (Public Key Infrastructure) including Root CA, Intermediate CA, and server certificates for internal applications.

## Features

- **Root Certificate Authority**: Creates a self-signed root CA certificate
- **Intermediate Certificate Authority**: Creates an intermediate CA signed by the root CA
- **Server Certificates**: Generates server certificates signed by the intermediate CA
- **Multiple Output Formats**: PEM certificates, PKCS#12 keystores, and truststores
- **Comprehensive Logging**: Detailed logging with verbose mode
- **Error Handling**: Robust error handling and validation
- **Command Line Interface**: Easy-to-use CLI with argument parsing

## Prerequisites

- Python 3.7 or higher
- cryptography library

## Installation

1. Navigate to the script directory:

   ```bash
   cd /Users/jgaragorry/OneDrive/02-CLDR/00-SUPPORT/10-REPOS/cldr/cdppc/ssl/custom_ca
   ```

2. Run the installation script (creates isolated virtual environment):

   ```bash
   ./install.sh
   ```

   This will:

   - Create a Python virtual environment in `venv/` directory
   - Install all dependencies in the isolated environment
   - Create convenient wrapper scripts
   - Ensure no impact on your system Python installation

### Installation Options

The installation script supports several options:

```bash
# Basic installation (default venv location)
./install.sh

# Clean existing venv and reinstall
./install.sh --clean

# Install venv in custom location
./install.sh --venv-dir /path/to/custom/venv

# Clean and install in custom location
./install.sh --clean --venv-dir /path/to/custom/venv

# Show help
./install.sh --help
```

### Cleanup

To remove the virtual environment and generated files:

```bash
# Clean virtual environment only
./cleanup.sh

# Clean venv and certificate directories
./cleanup.sh --clean-certs

# Clean specific venv location
./cleanup.sh --venv-dir /path/to/venv

# Show cleanup help
./cleanup.sh --help
```

## Usage

### Option 1: Using Wrapper Script (Recommended)

Generate certificates for a specific FQDN:

```bash
./run_ca.sh internal-app.company.com
```

Generate certificates with custom output directory and verbose logging:

```bash
./run_ca.sh api.internal.company.com --output-dir /path/to/certs --verbose
```

Generate wildcard certificates:

```bash
./run_ca.sh "*.internal.company.com"
```

### Option 2: Manual Virtual Environment Activation

Activate the virtual environment and run the script:

```bash
source venv/bin/activate
python certificate_authority.py internal-app.company.com
deactivate
```

### Option 3: Deactivate Environment

To deactivate the virtual environment:

```bash
./deactivate_env.sh
```

## Command Line Options

- `fqdn`: Fully Qualified Domain Name for the server certificate (required)
- `--output-dir`: Output directory for certificates (default: ./certs)
- `--verbose, -v`: Enable verbose logging
- `--help, -h`: Show help message

## Generated Files

The script generates the following files:

### Root CA Files

- `root_ca.pem`: Root CA certificate
- `root_ca_key.pem`: Root CA private key

### Intermediate CA Files

- `intermediate_ca.pem`: Intermediate CA certificate
- `intermediate_ca_key.pem`: Intermediate CA private key

### Server Certificate Files

- `{fqdn}.pem`: Server certificate (FQDN with dots replaced by underscores)
- `{fqdn}_key.pem`: Server private key
- `{fqdn}_chain.pem`: Complete certificate chain (server → intermediate → root)
- `{fqdn}.p12`: PKCS#12 keystore containing the complete chain

### Truststore

- `truststore.pem`: Truststore containing all certificates

## Certificate Details

### Root CA Certificate

- **Validity**: 10 years (3650 days)
- **Key Usage**: Certificate Sign, CRL Sign, Digital Signature
- **Basic Constraints**: CA=True, no path length restriction

### Intermediate CA Certificate

- **Validity**: 5 years (1825 days)
- **Key Usage**: Certificate Sign, CRL Sign, Digital Signature
- **Basic Constraints**: CA=True, path length=0
- **Subject Alternative Name**: DNS name matching the CA name

### Server Certificate

- **Validity**: 1 year (365 days)
- **Key Usage**: Digital Signature, Key Encipherment, Data Encipherment
- **Extended Key Usage**: Server Authentication, Client Authentication
- **Subject Alternative Name**: DNS name matching the FQDN and wildcard

## Security Considerations

1. **Private Key Security**: Store private keys securely and restrict access
2. **Certificate Validity**: Monitor certificate expiration dates
3. **Key Rotation**: Regularly rotate certificates and keys
4. **Access Control**: Implement proper access controls for CA operations
5. **Backup**: Maintain secure backups of CA private keys

## Troubleshooting

### Common Issues

1. **Permission Errors**: Ensure write permissions to the output directory
2. **Missing Dependencies**: Install required packages with `pip install -r requirements.txt`
3. **Invalid FQDN**: Ensure the FQDN is properly formatted

### Debug Mode

Use the `--verbose` flag to see detailed logging information:

```bash
python certificate_authority.py example.com --verbose
```

## Examples

### Example 1: Basic Internal Application

```bash
python certificate_authority.py app.internal.company.com
```

### Example 2: Wildcard Certificate

```bash
python certificate_authority.py "*.internal.company.com"
```

### Example 3: Custom Output Directory

```bash
python certificate_authority.py api.internal.company.com --output-dir /opt/certs
```

## File Structure

```
/Users/jgaragorry/OneDrive/02-CLDR/00-SUPPORT/10-REPOS/cldr/cdppc/ssl/custom_ca/
├── certificate_authority.py    # Main script
├── requirements.txt            # Python dependencies
├── install.sh                 # Installation script (creates venv)
├── cleanup.sh                 # Cleanup script (removes venv)
├── run_ca.sh                  # Wrapper script (auto-created)
├── deactivate_env.sh          # Deactivate script (auto-created)
├── README.md                  # This file
├── venv/                      # Python virtual environment (after install)
│   ├── bin/
│   ├── lib/
│   └── ...
└── certs/                     # Generated certificates (after running)
    └── {fqdn}_{timestamp}/    # FQDN + timestamp folders
        ├── CERTIFICATE_SUMMARY.md
        ├── root_ca.pem
        ├── root_ca_key.pem
        ├── intermediate_ca.pem
        ├── intermediate_ca_key.pem
        ├── {fqdn}.pem
        ├── {fqdn}_key.pem
        ├── {fqdn}.csr
        ├── {fqdn}_chain.pem
        ├── {fqdn}.p12
        ├── truststore.pem
        └── formats/           # Additional formats
            ├── {fqdn}.jks
            ├── {fqdn}_truststore.jks
            ├── {fqdn}.der
            ├── {fqdn}_full_chain.pem
            ├── {fqdn}_ca_bundle.pem
            ├── {fqdn}_root_bundle.pem
            └── openssl.conf
```

## License

This script is provided for internal use. Please ensure compliance with your organization's security policies and applicable regulations.
