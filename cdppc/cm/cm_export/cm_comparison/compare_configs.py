#!/usr/bin/env python3
"""
Configuration Comparison Tool

This script compares two Cloudera Manager configuration directories and generates a CSV report
showing the differences that need to be applied to make the second config match the first.

Usage:
    python3 compare_configs.py --source <source_config_dir> --target <target_config_dir> --output-dir <output_dir>
    python3 compare_configs.py -s <source_config_dir> -t <target_config_dir> -o <output_dir>

Example:
    python3 compare_configs.py --source /tmp/old_configs --target /tmp/new_configs --output-dir /tmp/comparison_results
    python3 compare_configs.py -s /tmp/old_configs -t /tmp/new_configs -o /tmp/comparison_results

The script will:
1. Parse JSON configuration files from both directories
2. Compare configurations while ignoring expected changing properties
3. Generate a CSV with PUT commands to apply the differences
4. Focus on making the target config match the source config
5. Create output directory with timestamp suffix for organization
6. Generate CSV file named 'cluster_config_differences-YYYYMMDD_HHMMSS.csv'
"""

import json
import os
import sys
import csv
import argparse
import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
import re

# Properties to ignore during comparison (expected to change)
IGNORED_PROPERTIES = {
    'ssl_enabled',
    'keystore',
    'truststore', 
    'password',
    'canary'
}

# Patterns to ignore (case-insensitive)
IGNORED_PATTERNS = [
    r'.*ssl.*',
    r'.*keystore.*',
    r'.*truststore.*',
    r'.*password.*',
    r'.*canary.*',
    r'.*{{CM_AUTO_TLS}}.*',  # Auto-generated TLS values
    r'.*timestamp.*',
    r'.*date.*',
    r'.*host.*',
    r'.*fqdn.*'
]

class ConfigComparator:
    def __init__(self, source_dir: str, target_dir: str):
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.ignored_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in IGNORED_PATTERNS]
        self.discovered_services = set()
        self.discovered_roles = set()
        self.discovered_mgmt_roles = set()
        self.discovered_role_types = set()
        self.discovered_service_patterns = set()
        self.discovered_skip_words = set()
        self.api_version = "v53"  # Default fallback
        self._discover_services_and_roles()
    
    def _discover_services_and_roles(self):
        """Discover services and roles from the actual exported data."""
        print("Discovering services and roles from exported data...")
        
        # Discover API version first
        self._discover_api_version()
        
        # Discover from API control files if available
        self._discover_from_api_control_files()
        
        # Discover from configuration files (first pass - learn patterns)
        self._discover_from_config_files()
        
        # Second pass - extract services and roles using learned patterns
        self._extract_services_and_roles_from_files()
        
        print(f"Discovered API version: {self.api_version}")
        print(f"Discovered {len(self.discovered_services)} services: {sorted(self.discovered_services)}")
        print(f"Discovered {len(self.discovered_roles)} roles: {sorted(self.discovered_roles)}")
        print(f"Discovered {len(self.discovered_mgmt_roles)} MGMT roles: {sorted(self.discovered_mgmt_roles)}")
        print(f"Discovered {len(self.discovered_role_types)} role types: {sorted(self.discovered_role_types)}")
        print(f"Discovered {len(self.discovered_service_patterns)} service patterns: {sorted(self.discovered_service_patterns)}")
        print(f"Discovered {len(self.discovered_skip_words)} skip words: {sorted(self.discovered_skip_words)}")
    
    def _discover_api_version(self):
        """Discover API version from exported data."""
        # Look for API control files in source directory
        api_control_dir = self.source_dir / "api_control_files"
        if api_control_dir.exists():
            # Check any CSV file for API version pattern
            for csv_file in api_control_dir.rglob("*.csv"):
                try:
                    with open(csv_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Look for API version pattern like /api/v53/
                        import re
                        match = re.search(r'/api/v(\d+)/', content)
                        if match:
                            self.api_version = f"v{match.group(1)}"
                            print(f"Found API version: {self.api_version}")
                            return
                except Exception as e:
                    continue
    
    def _discover_from_api_control_files(self):
        """Discover services and roles from API control files."""
        # Look for API control files in source directory
        api_control_dir = self.source_dir / "api_control_files"
        if api_control_dir.exists():
            # Discover cluster services
            cluster_service_file = api_control_dir / "service_configs" / "get_cluster_service_config_calls.csv"
            if cluster_service_file.exists():
                try:
                    with open(cluster_service_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if 'service_name' in row and row['service_name']:
                                self.discovered_services.add(row['service_name'])
                except Exception as e:
                    print(f"Warning: Could not read cluster service file: {e}")
            
            # Discover cluster roles
            cluster_role_file = api_control_dir / "role_configs" / "get_cluster_role_config_calls.csv"
            if cluster_role_file.exists():
                try:
                    with open(cluster_role_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if 'role_name' in row and row['role_name']:
                                self.discovered_roles.add(row['role_name'])
                except Exception as e:
                    print(f"Warning: Could not read cluster role file: {e}")
            
            # Discover MGMT roles
            mgmt_role_file = api_control_dir / "role_configs" / "get_mgmt_role_config_calls.csv"
            if mgmt_role_file.exists():
                try:
                    with open(mgmt_role_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if 'role_name' in row and row['role_name']:
                                self.discovered_mgmt_roles.add(row['role_name'])
                except Exception as e:
                    print(f"Warning: Could not read MGMT role file: {e}")
    
    def _discover_from_config_files(self):
        """Discover services and roles from configuration file names."""
        # Discover from source directory
        for json_file in self.source_dir.rglob("*.json"):
            self._extract_service_role_from_filename(json_file.name)
        
        # Discover from target directory
        for json_file in self.target_dir.rglob("*.json"):
            self._extract_service_role_from_filename(json_file.name)
    
    def _extract_service_role_from_filename(self, filename: str):
        """Extract service and role information from filename using dynamic patterns."""
        # Remove .json extension
        name_without_ext = filename.replace('.json', '')
        
        # Split by underscores
        parts = name_without_ext.split('_')
        
        # First pass: learn patterns from this filename
        self._learn_patterns_from_filename(parts)
    
    def _extract_services_and_roles_from_files(self):
        """Second pass: extract services and roles using learned patterns."""
        # Extract from source directory
        for json_file in self.source_dir.rglob("*.json"):
            self._extract_from_filename_parts(json_file.name)
        
        # Extract from target directory
        for json_file in self.target_dir.rglob("*.json"):
            self._extract_from_filename_parts(json_file.name)
    
    def _extract_from_filename_parts(self, filename: str):
        """Extract services and roles from filename using learned patterns."""
        # Remove .json extension
        name_without_ext = filename.replace('.json', '')
        
        # Split by underscores
        parts = name_without_ext.split('_')
        
        # Extract services and roles using learned patterns
        self._extract_services_from_parts(parts)
        self._extract_roles_from_parts(parts)
    
    def _learn_patterns_from_filename(self, parts: list):
        """Learn patterns from filename parts to identify services and roles."""
        for i, part in enumerate(parts):
            # Learn skip words (common non-service words and cluster-specific patterns)
            if (len(part) <= 3 or 
                part.lower() in ['config', 'role', 'service', 'settings', 'context', 'core', 'data', 'for', 'all'] or
                part.isdigit() or
                '.' in part or  # Likely hostname or FQDN
                part.startswith('jdga-') or  # Cluster-specific patterns
                (len(part) > 8 and '-' in part and any(char.isdigit() for char in part) and not part.split('-')[0].islower())):  # Likely cluster-specific IDs, but not service names with IDs
                self.discovered_skip_words.add(part)
            
            # Learn service patterns (multi-part services) - but skip cluster-specific ones
            if i + 1 < len(parts):
                combined = f"{part}_{parts[i+1]}"
                # If it looks like a service name (lowercase, meaningful length, not cluster-specific)
                if (len(combined) > 5 and 
                    combined.islower() and 
                    '_' in combined and
                    not any(skip in combined.lower() for skip in ['config', 'role', 'service', 'settings']) and
                    not combined.startswith('jdga-') and  # Skip cluster-specific patterns
                    not any(char.isdigit() for char in combined.split('_')[0])):  # Skip patterns starting with cluster IDs
                    self.discovered_service_patterns.add(combined)
            
            # Learn role patterns (contain dashes and uppercase parts)
            if '-' in part:
                role_parts = part.split('-')
                for role_part in role_parts:
                    if role_part.isupper() and len(role_part) > 2:
                        self.discovered_role_types.add(role_part)
    
    def _extract_services_from_parts(self, parts: list):
        """Extract services from filename parts using learned patterns."""
        for i, part in enumerate(parts):
            # Skip known skip words and cluster-specific patterns
            if (part in self.discovered_skip_words or
                part.startswith('jdga-') or
                ('.' in part) or  # Skip FQDNs
                (len(part) > 3 and any(char.isdigit() for char in part) and '-' in part)):  # Skip cluster IDs
                continue
            
            # Check for multi-part service names
            if i + 1 < len(parts):
                combined = f"{part}_{parts[i+1]}"
                if (combined in self.discovered_service_patterns and
                    not combined.startswith('jdga-') and
                    not any(char.isdigit() for char in combined.split('_')[0])):
                    self.discovered_services.add(combined)
                    continue
            
            # Check for services with suffixes (extract base name)
            if '-' in part and not part.isupper():
                base_service = part.split('-')[0]
                # Check if this looks like a service name (not a cluster ID or role)
                if (len(base_service) > 2 and 
                    base_service.islower() and 
                    base_service not in self.discovered_skip_words and
                    not base_service.startswith('jdga-') and
                    not any(char.isdigit() for char in base_service) and
                    not base_service.isupper() and  # Not a role type
                    base_service not in self.discovered_role_types):  # Not a discovered role type
                    self.discovered_services.add(base_service)
                    continue
            
            # Check for single-word services
            if (len(part) > 2 and 
                part.islower() and 
                part not in self.discovered_skip_words and
                not any(role_type in part.upper() for role_type in self.discovered_role_types) and
                not part.startswith(('-', '_')) and
                not part.startswith('jdga-') and
                not any(char.isdigit() for char in part)):
                self.discovered_services.add(part)
    
    def _extract_roles_from_parts(self, parts: list):
        """Extract roles from filename parts using learned patterns."""
        for part in parts:
            if '-' in part:
                # Check if this looks like a role name using learned role types
                if any(role_type in part.upper() for role_type in self.discovered_role_types):
                    if part.startswith('MGMT-'):
                        self.discovered_mgmt_roles.add(part)
                    else:
                        self.discovered_roles.add(part)
        
    def should_ignore_property(self, property_name: str) -> bool:
        """Check if a property should be ignored during comparison."""
        # Check exact matches
        if property_name in IGNORED_PROPERTIES:
            return True
            
        # Check pattern matches
        for pattern in self.ignored_patterns:
            if pattern.match(property_name):
                return True
                
        return False
    
    def parse_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse a JSON configuration file and extract configuration items."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Extract items from the JSON structure
            if isinstance(data, dict) and 'items' in data:
                if not data['items']:
                    return {}
                return {item.get('name', ''): item.get('value', '') for item in data['items']}
            elif isinstance(data, list):
                if not data:
                    return {}
                return {item.get('name', ''): item.get('value', '') for item in data}
            else:
                return {}
        except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
            print(f"Warning: Could not parse {file_path}: {e}")
            return {}
    
    def find_config_files(self, directory: Path) -> Dict[str, Path]:
        """Find all JSON configuration files in a directory and its subdirectories."""
        config_files = {}
        
        for json_file in directory.rglob("*.json"):
            # Create a normalized key for matching files between source and target
            # Extract the meaningful part of the filename (service/role name)
            normalized_key = self.normalize_filename(json_file.name)
            if normalized_key:
                config_files[normalized_key] = json_file
                
        return config_files
    
    def normalize_filename(self, filename: str) -> str:
        """
        Normalize filename to create a matching key between source and target.
        This method extracts the service/role part while ignoring cluster-specific prefixes.
        
        Examples:
        - 'jdga-it1-aw-dl-gateway0.jdga-it1.a465-9q4k.cloudera.site_jdga-it1-aw-dl_hive_hive-WEBHCAT-BASE_config.json'
          -> 'hive_hive-WEBHCAT-BASE_config'
        - 'jdga-mg1-aw-dl-gateway0.jdga-mg1.a465-9q4k.cloudera.site_jdga-mg1-aw-dl_hive_hive-WEBHCAT-BASE_config.json'
          -> 'hive_hive-WEBHCAT-BASE_config'
        """
        # Remove file extension
        name_without_ext = filename.replace('.json', '')
        
        # Split by underscores
        parts = name_without_ext.split('_')
        
        # Skip cluster-specific parts (hostname and cluster name)
        # Look for the pattern: hostname_cluster_service_role_config
        # We want to extract: service_role_config (ignoring hostname and cluster)
        
        # Find the start of service/role information
        # Typically after the cluster name (second part)
        service_start_index = None
        
        for i, part in enumerate(parts):
            # Skip hostname (first part) and cluster name (second part)
            if i < 2:
                continue
            
            # Look for service patterns
            if (part in self.discovered_services or
                any(service in part for service in self.discovered_services) or
                part.startswith('MGMT-') or
                any(role_type in part.upper() for role_type in self.discovered_role_types) or
                'config' in part):
                service_start_index = i
                break
        
        # If we found a service start, return from that point
        if service_start_index is not None:
            return '_'.join(parts[service_start_index:])
        
        # Fallback: try to find meaningful parts by looking for common patterns
        meaningful_parts = []
        for part in parts:
            # Skip cluster-specific patterns
            if ('.' in part or  # FQDN
                part.startswith('jdga-') or  # Cluster prefix
                len(part) <= 3 or  # Too short
                part.isdigit() or  # Timestamp
                part in ['config', 'role', 'service', 'settings']):  # Common words
                continue
            
            # Include meaningful parts
            if (part in self.discovered_services or
                part in self.discovered_roles or
                part in self.discovered_mgmt_roles or
                any(role_type in part.upper() for role_type in self.discovered_role_types) or
                '-' in part):  # Role-like patterns
                meaningful_parts.append(part)
        
        if meaningful_parts:
            return '_'.join(meaningful_parts)
        
        # Final fallback: return the last few parts
        if len(parts) >= 3:
            return '_'.join(parts[-3:])
        elif len(parts) >= 2:
            return '_'.join(parts[-2:])
        else:
            return parts[0] if parts else filename
    
    def compare_configs(self) -> List[Dict[str, Any]]:
        """Compare configurations between source and target directories."""
        differences = []
        processed_files = 0
        empty_files = 0
        missing_files = 0
        
        # Find all config files in both directories
        source_files = self.find_config_files(self.source_dir)
        target_files = self.find_config_files(self.target_dir)
        
        print(f"Found {len(source_files)} config files in source directory")
        print(f"Found {len(target_files)} config files in target directory")
        
        # Compare each source file with corresponding target file
        for filename, source_file in source_files.items():
            if filename not in target_files:
                missing_files += 1
                continue
                
            target_file = target_files[filename]
            
            # Parse configurations
            source_config = self.parse_json_file(source_file)
            target_config = self.parse_json_file(target_file)
            
            if not source_config:
                empty_files += 1
                continue
                
            processed_files += 1
            # Find differences
            file_differences = self.find_differences(filename, source_config, target_config, source_file, target_file)
            differences.extend(file_differences)
        
        # Summary
        print(f"Processed {processed_files} files with configurations")
        if empty_files > 0:
            print(f"Skipped {empty_files} empty configuration files")
        if missing_files > 0:
            print(f"Skipped {missing_files} files not found in target directory")
            
        return differences
    
    def find_differences(self, filename: str, source_config: Dict[str, Any], 
                        target_config: Dict[str, Any], source_file: Path, target_file: Path) -> List[Dict[str, Any]]:
        """Find differences between source and target configurations for a specific file."""
        differences = []
        
        # Check for missing properties in target
        for prop_name, source_value in source_config.items():
            if self.should_ignore_property(prop_name):
                continue
                
            if prop_name not in target_config:
                # Property missing in target - needs to be added
                differences.append({
                    'filename': filename,
                    'property_name': prop_name,
                    'source_value': source_value,
                    'target_value': 'MISSING',
                    'action': 'ADD',
                    'source_file': str(source_file),
                    'target_file': str(target_file),
                    'put_command': self.generate_put_command(filename, prop_name, source_value, source_file)
                })
            elif source_value != target_config[prop_name]:
                # Property value differs - needs to be updated
                differences.append({
                    'filename': filename,
                    'property_name': prop_name,
                    'source_value': source_value,
                    'target_value': target_config[prop_name],
                    'action': 'UPDATE',
                    'source_file': str(source_file),
                    'target_file': str(target_file),
                    'put_command': self.generate_put_command(filename, prop_name, source_value, source_file)
                })
        
        return differences
    
    def generate_put_command(self, filename: str, property_name: str, property_value: str, source_file: Path) -> str:
        """Generate a PUT command based on the file type and location."""
        # Determine if this is a cluster service, cluster role, or MGMT service/role
        file_path_str = str(source_file)
        actual_filename = source_file.name  # Use the actual filename from the file path
        
        if 'ClusterServices' in file_path_str:
            if 'roleConfigGroups' in file_path_str:
                # Cluster role config group
                service_name = self.extract_service_name(actual_filename)
                role_name = self.extract_role_name(actual_filename)
                return f'curl -s -L -k -u "${{WORKLOAD_USER}}:*****" -X PUT "${{CM_SERVER}}/api/${{CM_API_VERSION}}/clusters/${{CM_CLUSTER_NAME}}/services/{service_name}/roleConfigGroups/{role_name}/config" -H "content-type:application/json" -d \'{{"items":[{{"name":"{property_name}","value":"{property_value}"}}]}}\''
            else:
                # Cluster service config
                service_name = self.extract_service_name(actual_filename)
                return f'curl -s -L -k -u "${{WORKLOAD_USER}}:*****" -X PUT "${{CM_SERVER}}/api/${{CM_API_VERSION}}/clusters/${{CM_CLUSTER_NAME}}/services/{service_name}/config" -H "content-type:application/json" -d \'{{"items":[{{"name":"{property_name}","value":"{property_value}"}}]}}\''
        elif 'MGMT_Services' in file_path_str:
            if 'roleConfigGroups' in file_path_str:
                # MGMT role config group
                role_group = self.extract_mgmt_role_group(actual_filename)
                return f'curl -s -L -k -u "${{WORKLOAD_USER}}:*****" -X PUT "${{CM_SERVER}}/api/${{CM_API_VERSION}}/cm/service/roleConfigGroups/{role_group}/config" -H "content-type:application/json" -d \'{{"items":[{{"name":"{property_name}","value":"{property_value}"}}]}}\''
            else:
                # MGMT service config
                return f'curl -s -L -k -u "${{WORKLOAD_USER}}:*****" -X PUT "${{CM_SERVER}}/api/${{CM_API_VERSION}}/cm/service/config" -H "content-type:application/json" -d \'{{"items":[{{"name":"{property_name}","value":"{property_value}"}}]}}\''
        else:
            # Fallback generic PUT command
            return f'curl -s -L -k -u "${{WORKLOAD_USER}}:*****" -X PUT "${{CM_SERVER}}/api/${{CM_API_VERSION}}/config" -H "content-type:application/json" -d \'{{"items":[{{"name":"{property_name}","value":"{property_value}"}}]}}\''
    
    def extract_service_name(self, filename: str) -> str:
        """Extract service name from filename using discovered services."""
        # Remove .json extension
        name_without_ext = filename.replace('.json', '')
        
        # Split by underscores
        parts = name_without_ext.split('_')
        
        # Look for the pattern: hostname_cluster_service_... or hostname_cluster_service_role_...
        # The service name is typically the first meaningful part after the cluster name
        for i, part in enumerate(parts):
            # Skip hostname and cluster name parts
            if i < 2:
                continue
            
            # Check if this part matches any discovered service
            if part in self.discovered_services:
                return part
            
            # Check for services with suffixes (extract base name)
            if '-' in part:
                base_service = part.split('-')[0]
                if base_service in self.discovered_services:
                    return base_service
            
            # Check for multi-part service names (e.g., query_processor split as query + processor)
            if i + 1 < len(parts):
                combined = f"{part}_{parts[i+1]}"
                if combined in self.discovered_services:
                    return combined
        
        # If no service found, try to extract from the last meaningful parts
        if len(parts) >= 2:
            for i in range(len(parts) - 1, max(0, len(parts) - 4), -1):
                if parts[i] in self.discovered_services:
                    return parts[i]
        
        return "unknown_service"
    
    def extract_role_name(self, filename: str) -> str:
        """Extract role name from filename using discovered roles."""
        # Remove .json extension
        name_without_ext = filename.replace('.json', '')
        
        # Split by underscores
        parts = name_without_ext.split('_')
        
        # Look for role patterns (typically contain dashes and role names)
        # Skip the first part (hostname) and look for role patterns
        for i, part in enumerate(parts):
            if i == 0:  # Skip hostname part
                continue
            
            # Check if this part matches any discovered role
            if part in self.discovered_roles:
                return part
            
            # Check for role patterns with discovered role type indicators
            if '-' in part and any(role_type in part.upper() for role_type in self.discovered_role_types):
                return part
        
        return "unknown_role"
    
    def extract_mgmt_role_group(self, filename: str) -> str:
        """Extract MGMT role group name from filename using discovered MGMT roles."""
        # Remove .json extension
        name_without_ext = filename.replace('.json', '')
        
        # Split by underscores
        parts = name_without_ext.split('_')
        
        # Look for MGMT role group pattern
        # The pattern is: hostname_MGMT_MGMT-ROLEGROUP-BASE_role_config
        for i, part in enumerate(parts):
            if part == 'MGMT' and i + 1 < len(parts):
                # The next part should be the role group name (e.g., MGMT-REPORTSMANAGER-BASE)
                role_group = parts[i + 1]
                
                # Check if this role group is in our discovered MGMT roles
                if role_group in self.discovered_mgmt_roles:
                    return role_group
                
                # Fallback: verify it starts with MGMT- and contains discovered role type indicators
                if role_group.startswith('MGMT-') and any(role_type in role_group.upper() for role_type in self.discovered_role_types):
                    return role_group
        
        return "unknown_mgmt_role"
    
    def generate_consolidated_api_calls(self, differences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate consolidated API calls grouped by service and role."""
        consolidated_calls = []
        
        # Group differences by service/role combination
        grouped_diffs = {}
        
        for diff in differences:
            # Extract service and role information from the source file path instead of put_command
            source_file = Path(diff['source_file'])
            actual_filename = source_file.name
            
            # Determine the grouping key based on the file path
            if 'MGMT_Services' in str(source_file):
                # MGMT role config group
                role_group = self.extract_mgmt_role_group(actual_filename)
                group_key = f"MGMT_ROLE_{role_group}"
                service_type = "MGMT_ROLE"
                service_name = "MGMT"
                role_name = role_group
            elif 'ClusterServices' in str(source_file) and 'roleConfigGroups' in str(source_file):
                # Cluster role config group
                service_name = self.extract_service_name(actual_filename)
                role_name = self.extract_role_name(actual_filename)
                group_key = f"CLUSTER_ROLE_{service_name}_{role_name}"
                service_type = "CLUSTER_ROLE"
            elif 'ClusterServices' in str(source_file) and 'ServiceConfigs' in str(source_file):
                # Cluster service config
                service_name = self.extract_service_name(actual_filename)
                group_key = f"CLUSTER_SERVICE_{service_name}"
                service_type = "CLUSTER_SERVICE"
                role_name = None
            else:
                # Skip unknown patterns
                continue
            
            if group_key not in grouped_diffs:
                grouped_diffs[group_key] = {
                    'service_type': service_type,
                    'service_name': service_name,
                    'role_name': role_name,
                    'properties': [],
                    'api_endpoint': str(source_file)
                }
            
            grouped_diffs[group_key]['properties'].append({
                'name': diff['property_name'],
                'value': diff['source_value'],
                'action': diff['action']
            })
        
        # Generate consolidated API calls
        for group_key, group_data in grouped_diffs.items():
            # Create items array for the JSON payload
            items = []
            for prop in group_data['properties']:
                items.append({
                    "name": prop['name'],
                    "value": prop['value']
                })
            
            # Generate the consolidated PUT command
            consolidated_command = self.generate_consolidated_put_command(
                group_data['service_type'],
                group_data['service_name'],
                group_data['role_name'],
                items,
                group_data['api_endpoint']
            )
            
            consolidated_calls.append({
                'group_key': group_key,
                'service_type': group_data['service_type'],
                'service_name': group_data['service_name'],
                'role_name': group_data['role_name'],
                'property_count': len(group_data['properties']),
                'properties': '; '.join([f"{p['name']}={p['value']}" for p in group_data['properties']]),
                'consolidated_put_command': consolidated_command,
                'json_payload': json.dumps({"items": items})
            })
        
        return consolidated_calls
    
    def extract_api_endpoint(self, put_command: str) -> str:
        """Extract the base API endpoint from a PUT command."""
        # Extract the URL part before the query parameters
        if ' -d ' in put_command:
            return put_command.split(' -d ')[0].strip()
        return put_command
    
    def generate_consolidated_put_command(self, service_type: str, service_name: str, role_name: str, items: List[Dict], api_endpoint: str) -> str:
        """Generate a consolidated PUT command with all properties."""
        # Create the JSON payload
        json_payload = json.dumps({"items": items})
        
        # Use the existing API endpoint structure but with consolidated payload
        if service_type == "MGMT_ROLE":
            return f'curl -s -L -k -u "${{WORKLOAD_USER}}:*****" -X PUT "${{CM_SERVER}}/api/${{CM_API_VERSION}}/cm/service/roleConfigGroups/{role_name}/config" -H "content-type:application/json" -d \'{json_payload}\''
        elif service_type == "CLUSTER_ROLE":
            return f'curl -s -L -k -u "${{WORKLOAD_USER}}:*****" -X PUT "${{CM_SERVER}}/api/${{CM_API_VERSION}}/clusters/${{CM_CLUSTER_NAME}}/services/{service_name}/roleConfigGroups/{role_name}/config" -H "content-type:application/json" -d \'{json_payload}\''
        elif service_type == "CLUSTER_SERVICE":
            return f'curl -s -L -k -u "${{WORKLOAD_USER}}:*****" -X PUT "${{CM_SERVER}}/api/${{CM_API_VERSION}}/clusters/${{CM_CLUSTER_NAME}}/services/{service_name}/config" -H "content-type:application/json" -d \'{json_payload}\''
        else:
            return f'curl -s -L -k -u "${{WORKLOAD_USER}}:*****" -X PUT "${{CM_SERVER}}/api/${{CM_API_VERSION}}/config" -H "content-type:application/json" -d \'{json_payload}\''

    def generate_csv_report(self, differences: List[Dict[str, Any]], output_file: str):
        """Generate a CSV report with the differences and consolidated API calls."""
        if not differences:
            print("No differences found. Configurations are identical.")
            # Still create a CSV file with a summary row
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'filename', 'property_name', 'source_value', 'target_value', 
                    'action', 'put_command', 'source_file', 'target_file'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                # Add a summary row
                writer.writerow({
                    'filename': 'SUMMARY',
                    'property_name': 'No differences found',
                    'source_value': 'Configurations are identical',
                    'target_value': 'Configurations are identical',
                    'action': 'NONE',
                    'put_command': 'No action required',
                    'source_file': 'N/A',
                    'target_file': 'N/A'
                })
            
            print(f"Summary CSV created: {output_file}")
            return
        
        # Generate consolidated API calls
        consolidated_calls = self.generate_consolidated_api_calls(differences)
        
        # Create the detailed CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'filename', 'property_name', 'source_value', 'target_value', 
                'action', 'put_command', 'source_file', 'target_file'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for diff in differences:
                writer.writerow(diff)
        
        # Create the consolidated CSV
        consolidated_output_file = output_file.replace('.csv', '_consolidated.csv')
        with open(consolidated_output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'group_key', 'service_type', 'service_name', 'role_name', 
                'property_count', 'properties', 'consolidated_put_command', 'json_payload'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for call in consolidated_calls:
                writer.writerow(call)
        
        print(f"Detailed CSV report generated: {output_file}")
        print(f"Consolidated CSV report generated: {consolidated_output_file}")
        print(f"Total differences found: {len(differences)}")
        print(f"Consolidated API calls: {len(consolidated_calls)}")
        
        # Summary by action type
        action_counts = {}
        for diff in differences:
            action = diff['action']
            action_counts[action] = action_counts.get(action, 0) + 1
        
        print("Summary by action type:")
        for action, count in action_counts.items():
            print(f"  {action}: {count} properties")

def validate_directories(source_dir: str, target_dir: str) -> None:
    """
    Validate that source and target directories exist and are accessible.
    
    Args:
        source_dir: Path to source configuration directory
        target_dir: Path to target configuration directory
        
    Raises:
        SystemExit: If directories don't exist or are not accessible
    """
    if not os.path.isdir(source_dir):
        print(f"Error: Source directory '{source_dir}' does not exist")
        sys.exit(1)
        
    if not os.path.isdir(target_dir):
        print(f"Error: Target directory '{target_dir}' does not exist")
        sys.exit(1)


def create_output_directory(output_dir: str) -> str:
    """
    Create output directory with timestamp suffix.
    
    Args:
        output_dir: Base output directory path
        
    Returns:
        str: Full path to timestamped output directory
        
    Raises:
        SystemExit: If directory creation fails
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir_with_timestamp = f"{output_dir}_{timestamp}"
    
    try:
        os.makedirs(output_dir_with_timestamp, exist_ok=True)
        print(f"Created output directory: {output_dir_with_timestamp}")
        return output_dir_with_timestamp
    except Exception as e:
        print(f"Error: Could not create output directory '{output_dir_with_timestamp}': {e}")
        sys.exit(1)


def generate_csv_filename() -> str:
    """
    Generate CSV filename with timestamp.
    
    Returns:
        str: CSV filename in format 'cluster_config_differences-YYYYMMDD_HHMMSS.csv'
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"cluster_config_differences-{timestamp}.csv"


def main():
    """
    Main function to run the configuration comparison tool.
    
    Parses command line arguments, validates directories, creates output structure,
    runs the comparison, and generates the CSV report.
    """
    parser = argparse.ArgumentParser(
        description="Compare Cloudera Manager configurations and generate difference report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 compare_configs.py --source /tmp/old_configs --target /tmp/new_configs --output-dir /tmp/comparison_results
  python3 compare_configs.py -s /tmp/old_configs -t /tmp/new_configs -o /tmp/comparison_results
        """
    )
    
    parser.add_argument('--source', '-s', required=True, 
                       help='Source configuration directory (baseline)')
    parser.add_argument('--target', '-t', required=True, 
                       help='Target configuration directory (to be updated)')
    parser.add_argument('--output-dir', '-o', required=True, 
                       help='Output directory for comparison results (will be created with timestamp)')
    
    args = parser.parse_args()
    
    # Validate directories
    validate_directories(args.source, args.target)
    
    # Create output directory with timestamp
    output_dir_with_timestamp = create_output_directory(args.output_dir)
    
    # Generate CSV filename
    csv_filename = generate_csv_filename()
    csv_file_path = os.path.join(output_dir_with_timestamp, csv_filename)
    
    print(f"Comparing configurations:")
    print(f"  Source (baseline): {args.source}")
    print(f"  Target (to update): {args.target}")
    print(f"  Output directory: {output_dir_with_timestamp}")
    print(f"  CSV file: {csv_filename}")
    print()
    
    # Create comparator and run comparison
    comparator = ConfigComparator(args.source, args.target)
    differences = comparator.compare_configs()
    
    # Generate report
    comparator.generate_csv_report(differences, csv_file_path)
    
    print(f"\nComparison completed successfully!")
    print(f"Results saved to: {output_dir_with_timestamp}")

if __name__ == "__main__":
    main()
