#!/usr/bin/env python3
"""
Simple entry point for CDP Environment Discovery.

This script can be run directly without package installation:
    python3 discover.py --environment-name my-env
"""

import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import and run main
from main import main

if __name__ == "__main__":
    sys.exit(main())
