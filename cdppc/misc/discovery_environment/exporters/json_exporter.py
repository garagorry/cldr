#!/usr/bin/env python3
"""JSON exporter for CDP discovery data."""

import json
from pathlib import Path

# Handle both direct execution and module import
try:
    from ..common.utils import log
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from common.utils import log


class JSONExporter:
    """Export discovery data to JSON format."""
    
    def __init__(self, indent=2):
        """
        Initialize JSON exporter.
        
        Args:
            indent: JSON indentation level
        """
        self.indent = indent
    
    def save(self, data, filepath):
        """
        Save data to JSON file.
        
        Args:
            data: Data to save (dict or list)
            filepath: Output file path
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=self.indent)
        
        log(f"✅ Saved JSON: {filepath}")
    
    def save_pretty(self, data, filepath):
        """
        Save data to JSON file with pretty formatting.
        
        Args:
            data: Data to save
            filepath: Output file path
        """
        self.save(data, filepath)
    
    def save_compact(self, data, filepath):
        """
        Save data to JSON file in compact format.
        
        Args:
            data: Data to save
            filepath: Output file path
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, separators=(',', ':'))
        
        log(f"✅ Saved compact JSON: {filepath}")

