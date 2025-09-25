#!/usr/bin/env python3
"""
Custom Certificate Authority Generator

This script creates a complete PKI infrastructure including:
- Root Certificate Authority (CA)
- Intermediate Certificate Authority
- Server certificates for internal applications

The script generates all necessary certificates, private keys, and keystores
for secure internal communication within an organization.

Author: Generated for internal use
Version: 1.0.0
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend
import tempfile
import subprocess
import base64
import shutil


class CertificateAuthority:
    """
    A comprehensive Certificate Authority implementation for generating
    Root CA, Intermediate CA, and server certificates.
    """
    
    def __init__(self, output_dir: str, fqdn: str, verbose: bool = False):
        """
        Initialize the Certificate Authority.
        
        Args:
            output_dir (str): Base directory to store all generated certificates and keys
            fqdn (str): Fully Qualified Domain Name for folder naming
            verbose (bool): Enable verbose logging
        """
        self.base_output_dir = Path(output_dir)
        self.fqdn = fqdn
        self.verbose = verbose
        self.setup_logging()
        self.setup_directories()
        
    def setup_logging(self):
        """Configure logging based on verbosity level."""
        level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_directories(self):
        """Create necessary directories for certificate storage."""
        # Create FQDN + timestamp folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_fqdn = self.fqdn.replace(".", "_").replace("*", "wildcard")
        folder_name = f"{safe_fqdn}_{timestamp}"
        self.output_dir = self.base_output_dir / folder_name
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Base output directory: {self.base_output_dir}")
        self.logger.info(f"Certificate folder: {self.output_dir}")
        
        # Create subdirectories for different formats
        self.formats_dir = self.output_dir / "formats"
        self.formats_dir.mkdir(exist_ok=True)
        
        self.logger.info(f"Formats directory: {self.formats_dir}")
        
    def generate_private_key(self, key_size: int = 2048) -> rsa.RSAPrivateKey:
        """
        Generate a new RSA private key.
        
        Args:
            key_size (int): Size of the RSA key in bits
            
        Returns:
            rsa.RSAPrivateKey: Generated private key
        """
        self.logger.debug(f"Generating {key_size}-bit RSA private key")
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        self.logger.info(f"Generated {key_size}-bit RSA private key")
        return private_key
        
    def generate_csr(self, private_key: rsa.RSAPrivateKey, fqdn: str, 
                    common_name: str = None) -> x509.CertificateSigningRequest:
        """
        Generate a Certificate Signing Request (CSR).
        
        Args:
            private_key: Private key for the CSR
            fqdn (str): Fully Qualified Domain Name
            common_name (str): Common name (defaults to fqdn)
            
        Returns:
            x509.CertificateSigningRequest: Generated CSR
        """
        if common_name is None:
            common_name = fqdn
            
        self.logger.debug(f"Generating CSR for: {fqdn}")
        
        # Create certificate subject
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Internal Application"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "IT Security"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        
        # Create CSR
        csr = x509.CertificateSigningRequestBuilder().subject_name(
            subject
        ).add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True
        ).add_extension(
            x509.KeyUsage(
                key_cert_sign=False,
                crl_sign=False,
                digital_signature=True,
                key_encipherment=True,
                data_encipherment=True,
                key_agreement=False,
                content_commitment=False,
                encipher_only=False,
                decipher_only=False
            ), critical=True
        ).add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH,
                ExtendedKeyUsageOID.CLIENT_AUTH
            ]), critical=True
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(fqdn),
                x509.DNSName(f"*.{fqdn.split('.', 1)[1] if '.' in fqdn else fqdn}")
            ]), critical=False
        ).sign(private_key, hashes.SHA256(), default_backend())
        
        self.logger.info(f"CSR generated for: {fqdn}")
        return csr
        
    def create_root_ca(self, common_name: str = "Root CA", validity_days: int = 3650):
        """
        Create a Root Certificate Authority.
        
        Args:
            common_name (str): Common name for the Root CA
            validity_days (int): Validity period in days
            
        Returns:
            tuple: (private_key, certificate)
        """
        self.logger.info("=" * 60)
        self.logger.info("Creating Root Certificate Authority")
        self.logger.info("=" * 60)
        
        # Generate private key
        private_key = self.generate_private_key()
        
        # Create certificate subject
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Internal Root CA"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "IT Security"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        
        # Create certificate
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=validity_days)
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        ).add_extension(
            x509.KeyUsage(
                key_cert_sign=True,
                crl_sign=True,
                digital_signature=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                content_commitment=False,
                encipher_only=False,
                decipher_only=False
            ), critical=True
        ).sign(private_key, hashes.SHA256(), default_backend())
        
        self.logger.info(f"Root CA certificate created: {common_name}")
        self.logger.info(f"Validity: {validity_days} days")
        
        return private_key, cert
        
    def create_intermediate_ca(self, root_private_key, root_cert, 
                             common_name: str = "Intermediate CA", 
                             validity_days: int = 1825):
        """
        Create an Intermediate Certificate Authority signed by the Root CA.
        
        Args:
            root_private_key: Root CA private key
            root_cert: Root CA certificate
            common_name (str): Common name for the Intermediate CA
            validity_days (int): Validity period in days
            
        Returns:
            tuple: (private_key, certificate)
        """
        self.logger.info("=" * 60)
        self.logger.info("Creating Intermediate Certificate Authority")
        self.logger.info("=" * 60)
        
        # Generate private key
        private_key = self.generate_private_key()
        
        # Create certificate subject
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Internal Intermediate CA"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "IT Security"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        
        # Create certificate
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            root_cert.subject
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=validity_days)
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=0), critical=True
        ).add_extension(
            x509.KeyUsage(
                key_cert_sign=True,
                crl_sign=True,
                digital_signature=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                content_commitment=False,
                encipher_only=False,
                decipher_only=False
            ), critical=True
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(common_name)
            ]), critical=False
        ).sign(root_private_key, hashes.SHA256(), default_backend())
        
        self.logger.info(f"Intermediate CA certificate created: {common_name}")
        self.logger.info(f"Validity: {validity_days} days")
        
        return private_key, cert
        
    def create_server_certificate(self, intermediate_private_key, intermediate_cert,
                                fqdn: str, validity_days: int = 365):
        """
        Create a server certificate signed by the Intermediate CA.
        
        Args:
            intermediate_private_key: Intermediate CA private key
            intermediate_cert: Intermediate CA certificate
            fqdn (str): Fully Qualified Domain Name for the server
            validity_days (int): Validity period in days
            
        Returns:
            tuple: (private_key, certificate)
        """
        self.logger.info("=" * 60)
        self.logger.info(f"Creating Server Certificate for: {fqdn}")
        self.logger.info("=" * 60)
        
        # Generate private key
        private_key = self.generate_private_key()
        
        # Create certificate subject
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Internal Application"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "IT Security"),
            x509.NameAttribute(NameOID.COMMON_NAME, fqdn),
        ])
        
        # Create certificate
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            intermediate_cert.subject
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=validity_days)
        ).add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True
        ).add_extension(
            x509.KeyUsage(
                key_cert_sign=False,
                crl_sign=False,
                digital_signature=True,
                key_encipherment=True,
                data_encipherment=True,
                key_agreement=False,
                content_commitment=False,
                encipher_only=False,
                decipher_only=False
            ), critical=True
        ).add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH,
                ExtendedKeyUsageOID.CLIENT_AUTH
            ]), critical=True
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(fqdn),
                x509.DNSName(f"*.{fqdn.split('.', 1)[1] if '.' in fqdn else fqdn}")
            ]), critical=False
        ).sign(intermediate_private_key, hashes.SHA256(), default_backend())
        
        self.logger.info(f"Server certificate created for: {fqdn}")
        self.logger.info(f"Validity: {validity_days} days")
        
        return private_key, cert
        
    def create_jks_keystore(self, private_key, server_cert, intermediate_cert, 
                           root_cert, fqdn: str, keystore_password: str = "changeit"):
        """
        Create a JKS keystore using keytool.
        
        Args:
            private_key: Server private key
            server_cert: Server certificate
            intermediate_cert: Intermediate CA certificate
            root_cert: Root CA certificate
            fqdn (str): Server FQDN
            keystore_password (str): Keystore password
        """
        self.logger.info("=" * 60)
        self.logger.info("Creating JKS Keystore")
        self.logger.info("=" * 60)
        
        keystore_path = self.formats_dir / f"{fqdn.replace('.', '_').replace('*', 'wildcard')}.jks"
        
        try:
            # Create temporary files for keytool operations
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Save private key and certificate in PEM format
                key_file = temp_path / "server.key"
                cert_file = temp_path / "server.crt"
                root_cert_file = temp_path / "root.crt"
                intermediate_cert_file = temp_path / "intermediate.crt"
                
                # Write private key
                with open(key_file, 'wb') as f:
                    f.write(private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    ))
                
                # Write certificates
                with open(cert_file, 'wb') as f:
                    f.write(server_cert.public_bytes(serialization.Encoding.PEM))
                with open(root_cert_file, 'wb') as f:
                    f.write(root_cert.public_bytes(serialization.Encoding.PEM))
                with open(intermediate_cert_file, 'wb') as f:
                    f.write(intermediate_cert.public_bytes(serialization.Encoding.PEM))
                
                # Convert PEM to PKCS12 first (keytool works better with PKCS12)
                p12_file = temp_path / "server.p12"
                self._create_pkcs12_keystore(private_key, server_cert, intermediate_cert, 
                                           root_cert, str(p12_file), fqdn)
                
                # Convert PKCS12 to JKS using keytool
                cmd = [
                    'keytool', '-importkeystore',
                    '-srckeystore', str(p12_file),
                    '-srcstoretype', 'PKCS12',
                    '-srcstorepass', '',
                    '-destkeystore', str(keystore_path),
                    '-deststoretype', 'JKS',
                    '-deststorepass', keystore_password,
                    '-noprompt'
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    self.logger.info(f"JKS keystore created: {keystore_path}")
                else:
                    self.logger.warning(f"JKS creation failed: {result.stderr}")
                    # Fallback: create empty JKS and import certificates
                    self._create_jks_fallback(keystore_path, private_key, server_cert, 
                                            intermediate_cert, root_cert, fqdn, keystore_password)
                    
        except Exception as e:
            self.logger.error(f"Error creating JKS keystore: {e}")
            # Fallback method
            self._create_jks_fallback(keystore_path, private_key, server_cert, 
                                    intermediate_cert, root_cert, fqdn, keystore_password)
    
    def _create_jks_fallback(self, keystore_path, private_key, server_cert, 
                           intermediate_cert, root_cert, fqdn, password):
        """Fallback method to create JKS keystore."""
        try:
            # Create empty JKS
            cmd = ['keytool', '-genkey', '-alias', 'dummy', '-dname', 'CN=dummy', 
                   '-keystore', str(keystore_path), '-storepass', password, '-keypass', password, '-noprompt']
            subprocess.run(cmd, capture_output=True)
            
            # Delete dummy entry
            cmd = ['keytool', '-delete', '-alias', 'dummy', '-keystore', str(keystore_path), 
                   '-storepass', password, '-noprompt']
            subprocess.run(cmd, capture_output=True)
            
            # Import certificates
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Save certificates as PEM files
                root_file = temp_path / "root.pem"
                intermediate_file = temp_path / "intermediate.pem"
                server_file = temp_path / "server.pem"
                
                with open(root_file, 'wb') as f:
                    f.write(root_cert.public_bytes(serialization.Encoding.PEM))
                with open(intermediate_file, 'wb') as f:
                    f.write(intermediate_cert.public_bytes(serialization.Encoding.PEM))
                with open(server_file, 'wb') as f:
                    f.write(server_cert.public_bytes(serialization.Encoding.PEM))
                
                # Import root CA
                cmd = ['keytool', '-import', '-alias', 'root', '-file', str(root_file),
                       '-keystore', str(keystore_path), '-storepass', password, '-noprompt']
                subprocess.run(cmd, capture_output=True)
                
                # Import intermediate CA
                cmd = ['keytool', '-import', '-alias', 'intermediate', '-file', str(intermediate_file),
                       '-keystore', str(keystore_path), '-storepass', password, '-noprompt']
                subprocess.run(cmd, capture_output=True)
                
                # Import server certificate
                cmd = ['keytool', '-import', '-alias', 'server', '-file', str(server_file),
                       '-keystore', str(keystore_path), '-storepass', password, '-noprompt']
                subprocess.run(cmd, capture_output=True)
                
            self.logger.info(f"JKS keystore created (fallback method): {keystore_path}")
            
        except Exception as e:
            self.logger.error(f"Fallback JKS creation failed: {e}")
    
    def convert_pkcs12_to_pem(self, pkcs12_path: str, output_dir: Path, fqdn: str):
        """
        Convert PKCS12 keystore to PEM format.
        
        Args:
            pkcs12_path (str): Path to PKCS12 file
            output_dir (Path): Output directory
            fqdn (str): Server FQDN
        """
        self.logger.info("Converting PKCS12 to PEM format")
        
        try:
            with open(pkcs12_path, 'rb') as f:
                p12_data = f.read()
            
            # Load PKCS12
            private_key, cert, additional_certificates = pkcs12.load_key_and_certificates(
                p12_data, None, default_backend()
            )
            
            # Save private key
            key_file = output_dir / f"{fqdn.replace('.', '_').replace('*', 'wildcard')}_key.pem"
            with open(key_file, 'wb') as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            
            # Save certificate
            cert_file = output_dir / f"{fqdn.replace('.', '_').replace('*', 'wildcard')}.pem"
            with open(cert_file, 'wb') as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            
            # Save certificate chain
            chain_file = output_dir / f"{fqdn.replace('.', '_').replace('*', 'wildcard')}_chain.pem"
            with open(chain_file, 'wb') as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
                for additional_cert in additional_certificates:
                    f.write(additional_cert.public_bytes(serialization.Encoding.PEM))
            
            self.logger.info(f"PKCS12 converted to PEM: {key_file}, {cert_file}, {chain_file}")
            
        except Exception as e:
            self.logger.error(f"Error converting PKCS12 to PEM: {e}")
    
    def convert_pem_to_der(self, pem_path: str, output_dir: Path, fqdn: str):
        """
        Convert PEM certificate to DER format.
        
        Args:
            pem_path (str): Path to PEM file
            output_dir (Path): Output directory
            fqdn (str): Server FQDN
        """
        self.logger.info("Converting PEM to DER format")
        
        try:
            with open(pem_path, 'rb') as f:
                pem_data = f.read()
            
            # Load certificate
            cert = x509.load_pem_x509_certificate(pem_data, default_backend())
            
            # Convert to DER
            der_data = cert.public_bytes(serialization.Encoding.DER)
            
            # Save DER file
            der_file = output_dir / f"{fqdn.replace('.', '_').replace('*', 'wildcard')}.der"
            with open(der_file, 'wb') as f:
                f.write(der_data)
            
            self.logger.info(f"PEM converted to DER: {der_file}")
            
        except Exception as e:
            self.logger.error(f"Error converting PEM to DER: {e}")
    
    def create_openssl_config(self, fqdn: str, output_dir: Path):
        """
        Create OpenSSL configuration file for certificate generation.
        
        Args:
            fqdn (str): Server FQDN
            output_dir (Path): Output directory
        """
        self.logger.info("Creating OpenSSL configuration file")
        
        config_content = f"""[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = v3_req

[dn]
C=US
ST=California
L=San Francisco
O=Internal Application
OU=IT Security
CN={fqdn}

[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = {fqdn}
DNS.2 = *.{fqdn.split('.', 1)[1] if '.' in fqdn else fqdn}
"""
        
        config_file = output_dir / "openssl.conf"
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        self.logger.info(f"OpenSSL config created: {config_file}")
    
    def create_certificate_bundle(self, root_cert, intermediate_cert, server_cert, fqdn: str):
        """
        Create various certificate bundles and formats.
        
        Args:
            root_cert: Root CA certificate
            intermediate_cert: Intermediate CA certificate
            server_cert: Server certificate
            fqdn (str): Server FQDN
        """
        self.logger.info("=" * 60)
        self.logger.info("Creating Certificate Bundles and Formats")
        self.logger.info("=" * 60)
        
        safe_fqdn = fqdn.replace(".", "_").replace("*", "wildcard")
        
        # Create certificate chain (server -> intermediate -> root)
        chain_content = (
            server_cert.public_bytes(serialization.Encoding.PEM).decode() +
            intermediate_cert.public_bytes(serialization.Encoding.PEM).decode() +
            root_cert.public_bytes(serialization.Encoding.PEM).decode()
        )
        
        # Save certificate chain
        chain_file = self.formats_dir / f"{safe_fqdn}_full_chain.pem"
        with open(chain_file, 'w') as f:
            f.write(chain_content)
        
        # Create CA bundle (intermediate -> root)
        ca_bundle_content = (
            intermediate_cert.public_bytes(serialization.Encoding.PEM).decode() +
            root_cert.public_bytes(serialization.Encoding.PEM).decode()
        )
        
        ca_bundle_file = self.formats_dir / f"{safe_fqdn}_ca_bundle.pem"
        with open(ca_bundle_file, 'w') as f:
            f.write(ca_bundle_content)
        
        # Create root CA bundle
        root_bundle_file = self.formats_dir / f"{safe_fqdn}_root_bundle.pem"
        with open(root_bundle_file, 'w') as f:
            f.write(root_cert.public_bytes(serialization.Encoding.PEM).decode())
        
        self.logger.info(f"Certificate bundles created:")
        self.logger.info(f"  - Full chain: {chain_file}")
        self.logger.info(f"  - CA bundle: {ca_bundle_file}")
        self.logger.info(f"  - Root bundle: {root_bundle_file}")
    
    def create_truststore_jks(self, root_cert, intermediate_cert, server_cert, fqdn: str):
        """
        Create JKS truststore with all certificates.
        
        Args:
            root_cert: Root CA certificate
            intermediate_cert: Intermediate CA certificate
            server_cert: Server certificate
            fqdn (str): Server FQDN
        """
        self.logger.info("Creating JKS Truststore")
        
        truststore_path = self.formats_dir / f"{fqdn.replace('.', '_').replace('*', 'wildcard')}_truststore.jks"
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Save certificates as PEM files
                root_file = temp_path / "root.pem"
                intermediate_file = temp_path / "intermediate.pem"
                server_file = temp_path / "server.pem"
                
                with open(root_file, 'wb') as f:
                    f.write(root_cert.public_bytes(serialization.Encoding.PEM))
                with open(intermediate_file, 'wb') as f:
                    f.write(intermediate_cert.public_bytes(serialization.Encoding.PEM))
                with open(server_file, 'wb') as f:
                    f.write(server_cert.public_bytes(serialization.Encoding.PEM))
                
                # Create truststore
                cmd = ['keytool', '-import', '-alias', 'root', '-file', str(root_file),
                       '-keystore', str(truststore_path), '-storepass', 'changeit', '-noprompt']
                subprocess.run(cmd, capture_output=True)
                
                cmd = ['keytool', '-import', '-alias', 'intermediate', '-file', str(intermediate_file),
                       '-keystore', str(truststore_path), '-storepass', 'changeit', '-noprompt']
                subprocess.run(cmd, capture_output=True)
                
                cmd = ['keytool', '-import', '-alias', 'server', '-file', str(server_file),
                       '-keystore', str(truststore_path), '-storepass', 'changeit', '-noprompt']
                subprocess.run(cmd, capture_output=True)
                
            self.logger.info(f"JKS truststore created: {truststore_path}")
            
        except Exception as e:
            self.logger.error(f"Error creating JKS truststore: {e}")
        
    def save_certificate_chain(self, root_cert, intermediate_cert, server_cert,
                             root_key, intermediate_key, server_key, fqdn: str):
        """
        Save all certificates and keys to files with comprehensive format support.
        
        Args:
            root_cert: Root CA certificate
            intermediate_cert: Intermediate CA certificate
            server_cert: Server certificate
            root_key: Root CA private key
            intermediate_key: Intermediate CA private key
            server_key: Server private key
            fqdn (str): Server FQDN for naming files
        """
        self.logger.info("=" * 60)
        self.logger.info("Saving Certificate Chain and Keys")
        self.logger.info("=" * 60)
        
        server_filename = fqdn.replace(".", "_").replace("*", "wildcard")
        
        # Save Root CA
        self._save_pem_file("root_ca.pem", root_cert.public_bytes(serialization.Encoding.PEM))
        self._save_pem_file("root_ca_key.pem", root_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
        
        # Save Intermediate CA
        self._save_pem_file("intermediate_ca.pem", intermediate_cert.public_bytes(serialization.Encoding.PEM))
        self._save_pem_file("intermediate_ca_key.pem", intermediate_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
        
        # Save Server Certificate
        self._save_pem_file(f"{server_filename}.pem", server_cert.public_bytes(serialization.Encoding.PEM))
        self._save_pem_file(f"{server_filename}_key.pem", server_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
        
        # Generate and save CSR
        csr = self.generate_csr(server_key, fqdn)
        self._save_pem_file(f"{server_filename}.csr", csr.public_bytes(serialization.Encoding.PEM))
        
        # Save certificate chain
        chain_content = (
            server_cert.public_bytes(serialization.Encoding.PEM).decode() +
            intermediate_cert.public_bytes(serialization.Encoding.PEM).decode() +
            root_cert.public_bytes(serialization.Encoding.PEM).decode()
        )
        self._save_pem_file(f"{server_filename}_chain.pem", chain_content.encode())
        
        # Create PKCS#12 keystore
        pkcs12_path = self.output_dir / f"{server_filename}.p12"
        self._create_pkcs12_keystore(server_key, server_cert, intermediate_cert, 
                                   root_cert, str(pkcs12_path), fqdn)
        
        # Create truststore
        self._create_truststore(root_cert, intermediate_cert, server_cert)
        
        # Create comprehensive format conversions
        self.logger.info("=" * 60)
        self.logger.info("Creating Additional Certificate Formats")
        self.logger.info("=" * 60)
        
        # Create JKS keystore
        self.create_jks_keystore(server_key, server_cert, intermediate_cert, 
                               root_cert, fqdn)
        
        # Create JKS truststore
        self.create_truststore_jks(root_cert, intermediate_cert, server_cert, fqdn)
        
        # Convert PKCS12 to PEM (in formats directory)
        self.convert_pkcs12_to_pem(str(pkcs12_path), self.formats_dir, fqdn)
        
        # Convert PEM to DER
        server_cert_path = self.output_dir / f"{server_filename}.pem"
        self.convert_pem_to_der(str(server_cert_path), self.formats_dir, fqdn)
        
        # Create certificate bundles
        self.create_certificate_bundle(root_cert, intermediate_cert, server_cert, fqdn)
        
        # Create OpenSSL configuration
        self.create_openssl_config(fqdn, self.formats_dir)
        
        # Create summary file
        self._create_summary_file(fqdn, server_filename)
        
    def _save_pem_file(self, filename: str, content: bytes):
        """Save content to a PEM file."""
        filepath = self.output_dir / filename
        with open(filepath, 'wb') as f:
            f.write(content)
        self.logger.info(f"Saved: {filepath}")
        
    def _create_pkcs12_keystore(self, private_key, server_cert, intermediate_cert, 
                               root_cert, filename: str, fqdn: str):
        """Create a PKCS#12 keystore file."""
        filepath = Path(filename)
        
        # Create PKCS#12 bundle
        p12 = pkcs12.serialize_key_and_certificates(
            name=fqdn.encode(),
            key=private_key,
            cert=server_cert,
            cas=[intermediate_cert, root_cert],
            encryption_algorithm=serialization.NoEncryption()
        )
        
        with open(filepath, 'wb') as f:
            f.write(p12)
        self.logger.info(f"Created PKCS#12 keystore: {filepath}")
        
    def _create_truststore(self, root_cert, intermediate_cert, server_cert):
        """Create a truststore containing all certificates."""
        truststore_content = (
            root_cert.public_bytes(serialization.Encoding.PEM).decode() +
            intermediate_cert.public_bytes(serialization.Encoding.PEM).decode() +
            server_cert.public_bytes(serialization.Encoding.PEM).decode()
        )
        
        filepath = self.output_dir / "truststore.pem"
        with open(filepath, 'w') as f:
            f.write(truststore_content)
        self.logger.info(f"Created truststore: {filepath}")
        
    def _create_summary_file(self, fqdn: str, server_filename: str):
        """Create a summary file with all generated files and their purposes."""
        summary_content = f"""# Certificate Authority Generation Summary

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
FQDN: {fqdn}
Server Filename: {server_filename}

## Root Certificate Authority
- root_ca.pem - Root CA certificate (10 years validity)
- root_ca_key.pem - Root CA private key

## Intermediate Certificate Authority  
- intermediate_ca.pem - Intermediate CA certificate (5 years validity)
- intermediate_ca_key.pem - Intermediate CA private key

## Server Certificate
- {server_filename}.pem - Server certificate (1 year validity)
- {server_filename}_key.pem - Server private key
- {server_filename}.csr - Certificate Signing Request
- {server_filename}_chain.pem - Complete certificate chain (server -> intermediate -> root)

## Keystores and Truststores
- {server_filename}.p12 - PKCS#12 keystore (contains server cert + chain)
- truststore.pem - PEM truststore with all certificates

## Additional Formats (in formats/ directory)
- {server_filename}.jks - Java KeyStore (JKS) format
- {server_filename}_truststore.jks - JKS truststore
- {server_filename}.der - DER format certificate
- {server_filename}_full_chain.pem - Full certificate chain
- {server_filename}_ca_bundle.pem - CA bundle (intermediate + root)
- {server_filename}_root_bundle.pem - Root CA only
- openssl.conf - OpenSSL configuration file

## Usage Examples

### For Java Applications
- Use {server_filename}.jks as keystore
- Use {server_filename}_truststore.jks as truststore
- Default passwords: changeit

### For Web Servers (Apache/Nginx)
- Certificate: {server_filename}.pem
- Private Key: {server_filename}_key.pem
- CA Bundle: {server_filename}_ca_bundle.pem

### For Load Balancers
- Full Chain: {server_filename}_full_chain.pem
- Private Key: {server_filename}_key.pem

### For PKCS#12 Applications
- Keystore: {server_filename}.p12
- Password: (empty)

## Certificate Details
- Key Algorithm: RSA 2048-bit
- Signature Algorithm: SHA-256
- Validity: 1 year (server), 5 years (intermediate), 10 years (root)
- Subject Alternative Names: {fqdn}, *.{fqdn.split('.', 1)[1] if '.' in fqdn else fqdn}

## Security Notes
- Store private keys securely
- Monitor certificate expiration dates
- Implement proper access controls
- Regular key rotation recommended
"""
        
        summary_file = self.output_dir / "CERTIFICATE_SUMMARY.md"
        with open(summary_file, 'w') as f:
            f.write(summary_content)
        
        self.logger.info(f"Summary file created: {summary_file}")
        
    def generate_certificate_authority(self, fqdn: str):
        """
        Generate complete certificate authority infrastructure.
        
        Args:
            fqdn (str): Fully Qualified Domain Name for the server certificate
        """
        self.logger.info("Starting Certificate Authority Generation")
        self.logger.info(f"Target FQDN: {fqdn}")
        
        try:
            # Create Root CA
            root_key, root_cert = self.create_root_ca()
            
            # Create Intermediate CA
            intermediate_key, intermediate_cert = self.create_intermediate_ca(
                root_key, root_cert
            )
            
            # Create Server Certificate
            server_key, server_cert = self.create_server_certificate(
                intermediate_key, intermediate_cert, fqdn
            )
            
            # Save everything
            self.save_certificate_chain(
                root_cert, intermediate_cert, server_cert,
                root_key, intermediate_key, server_key, fqdn
            )
            
            self.logger.info("=" * 60)
            self.logger.info("Certificate Authority Generation Complete!")
            self.logger.info("=" * 60)
            self.logger.info(f"All files saved to: {self.output_dir}")
            self.logger.info("Files generated:")
            self.logger.info("  - root_ca.pem (Root CA certificate)")
            self.logger.info("  - root_ca_key.pem (Root CA private key)")
            self.logger.info("  - intermediate_ca.pem (Intermediate CA certificate)")
            self.logger.info("  - intermediate_ca_key.pem (Intermediate CA private key)")
            self.logger.info(f"  - {fqdn.replace('.', '_').replace('*', 'wildcard')}.pem (Server certificate)")
            self.logger.info(f"  - {fqdn.replace('.', '_').replace('*', 'wildcard')}_key.pem (Server private key)")
            self.logger.info(f"  - {fqdn.replace('.', '_').replace('*', 'wildcard')}_chain.pem (Complete certificate chain)")
            self.logger.info(f"  - {fqdn.replace('.', '_').replace('*', 'wildcard')}.p12 (PKCS#12 keystore)")
            self.logger.info("  - truststore.pem (Truststore with all certificates)")
            
        except Exception as e:
            self.logger.error(f"Error generating certificate authority: {e}")
            raise


def main():
    """Main function to handle command line arguments and execute the CA generation."""
    parser = argparse.ArgumentParser(
        description="Generate a complete Certificate Authority infrastructure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python certificate_authority.py internal-app.company.com
  python certificate_authority.py *.internal.company.com --verbose
  python certificate_authority.py api.internal.company.com --output-dir /path/to/certs
        """
    )
    
    parser.add_argument(
        'fqdn',
        help='Fully Qualified Domain Name for the server certificate'
    )
    
    parser.add_argument(
        '--output-dir',
        default='./certs',
        help='Output directory for certificates (default: ./certs)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Create Certificate Authority instance
    ca = CertificateAuthority(args.output_dir, args.fqdn, args.verbose)
    
    # Generate the certificate authority
    ca.generate_certificate_authority(args.fqdn)


if __name__ == "__main__":
    main()
