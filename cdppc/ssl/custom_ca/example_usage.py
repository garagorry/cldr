#!/usr/bin/env python3
"""
Example usage of the Certificate Authority Generator

This script demonstrates how to use the CertificateAuthority class
programmatically instead of using the command line interface.
"""

import sys
import os
from pathlib import Path

# Add the current directory to the path so we can import our module
sys.path.insert(0, str(Path(__file__).parent))

try:
    from certificate_authority import CertificateAuthority
except ImportError as e:
    print(f"Error importing CertificateAuthority: {e}")
    print("Make sure you're in the correct directory and have installed dependencies.")
    sys.exit(1)


def main():
    """Example usage of the CertificateAuthority class."""
    
    # Configuration
    fqdn = "api.internal.example.com"
    output_dir = "./example_certs"
    verbose = True
    
    print("Custom Certificate Authority - Example Usage")
    print("=" * 50)
    print(f"FQDN: {fqdn}")
    print(f"Output Directory: {output_dir}")
    print(f"Verbose: {verbose}")
    print()
    
    try:
        # Create Certificate Authority instance
        ca = CertificateAuthority(output_dir, verbose)
        
        # Generate the certificate authority
        ca.generate_certificate_authority(fqdn)
        
        print("\nExample completed successfully!")
        print(f"Check the '{output_dir}' directory for generated files.")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
