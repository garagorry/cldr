#!/usr/bin/env python3
"""
IDBroker Mappings Validator

This script validates IDBroker mappings by checking if users and groups exist
before creating a new mapping list. It helps prevent "NOT_FOUND" errors during
datalake creation.

Usage:
    python validates_mappings.py <input_json_file>
    python validates_mappings.py --stdin  # Read from stdin

Optional Dependencies:
    tqdm - For progress bars during long-running operations
    Install with: pip install tqdm
"""

import json
import sys
import subprocess
import argparse
import re
import os
from datetime import datetime
from typing import Dict, List, Set, Optional
from dataclasses import dataclass

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    # Fallback: create a no-op tqdm-like class
    class tqdm:
        def __init__(self, iterable=None, desc=None, total=None, unit=None, **kwargs):
            self.iterable = iterable if iterable is not None else []
            self.desc = desc
            self.total = total
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def __iter__(self):
            return iter(self.iterable)
        def close(self):
            pass
        def update(self, n=1):
            pass
        def set_description(self, desc=None):
            if desc:
                self.desc = desc


@dataclass
class MappingInfo:
    """Information about a mapping entry extracted from accessorCrn."""
    accessor_crn: str
    role: str
    is_user: bool
    is_group: bool
    entity_id: str
    entity_name: str


class CDPCLIError(Exception):
    """Custom exception for CDP CLI command failures."""


class IDBrokerMappingValidator:
    """
    Validates IDBroker mappings by checking user/group existence in CDP.
    
    This class provides functionality to:
    - Load existing users and groups from CDP
    - Validate mapping entries against existing entities
    - Generate clean mapping lists with only valid entries
    - Provide detailed validation reports
    """
    
    def __init__(self):
        """Initialize the validator with empty data structures."""
        self.existing_users: Set[str] = set()
        self.existing_groups: Set[str] = set()
        self.group_members: Dict[str, Set[str]] = {}
        self.validated_mappings: List[Dict] = []
        self.invalid_mappings: List[Dict] = []
    
    def run_cdp_command(self, command: List[str]) -> Dict:
        """
        Execute a CDP CLI command and return parsed JSON output.
        
        Args:
            command: List of command arguments to execute
            
        Returns:
            Parsed JSON response from CDP CLI
            
        Raises:
            CDPCLIError: If command fails or output cannot be parsed
        """
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            raise CDPCLIError(f"CDP CLI command failed: {e.stderr}")
        except json.JSONDecodeError as e:
            raise CDPCLIError(f"Failed to parse CDP CLI output: {e}")
    
    def load_existing_users(self) -> None:
        """
        Load all existing users from CDP and store their CRNs.
        
        Uses 'cdp iam list-users' command to retrieve user information.
        """
        print("Loading existing users...")
        try:
            users_data = self.run_cdp_command(["cdp", "iam", "list-users", "--max-items", "10000"])
            users_list = users_data.get("users", [])
            with tqdm(users_list, desc="Processing users", unit="user") as pbar:
                for user in pbar:
                    self.existing_users.add(user["crn"])
            print(f"Loaded {len(self.existing_users)} users")
        except CDPCLIError as e:
            print(f"Warning: Could not load users: {e}")
    
    def load_existing_groups(self) -> None:
        """
        Load all existing groups from CDP and store their CRNs.
        
        Uses 'cdp iam list-groups' command to retrieve group information.
        """
        print("Loading existing groups...")
        try:
            groups_data = self.run_cdp_command(["cdp", "iam", "list-groups", "--max-items", "10000"])
            groups_list = groups_data.get("groups", [])
            with tqdm(groups_list, desc="Processing groups", unit="group") as pbar:
                for group in pbar:
                    self.existing_groups.add(group["crn"])
            print(f"Loaded {len(self.existing_groups)} groups")
        except CDPCLIError as e:
            print(f"Warning: Could not load groups: {e}")
    
    def load_group_members(self, group_crns: Set[str]) -> None:
        """
        Load members for specific groups using CDP CLI.
        
        Args:
            group_crns: Set of group CRNs to load members for
        """
        if not group_crns:
            return
        
        print("Loading group members...")
        group_list = list(group_crns)
        pbar = tqdm(group_list, desc="Loading group members", unit="group", total=len(group_list))
        try:
            for group_crn in pbar:
                try:
                    group_name = self.extract_entity_name_from_crn(group_crn)
                    if not group_name:
                        if HAS_TQDM:
                            pbar.set_description("Skipping invalid CRN")
                        continue
                    
                    if HAS_TQDM:
                        pbar.set_description(f"Loading members for {group_name}")
                    members_data = self.run_cdp_command(["cdp", "iam", "list-group-members", "--group-name", group_name])
                    member_crns = set()
                    for member in members_data.get("members", []):
                        member_crns.add(member["crn"])
                    self.group_members[group_crn] = member_crns
                    if not HAS_TQDM:
                        print(f"Loaded {len(member_crns)} members for group {group_name}")
                except CDPCLIError as e:
                    if not HAS_TQDM:
                        print(f"Warning: Could not load members for group {group_crn}: {e}")
                    self.group_members[group_crn] = set()
        finally:
            if HAS_TQDM:
                pbar.close()
    
    def extract_entity_name_from_crn(self, crn: str) -> Optional[str]:
        """
        Extract entity name from a CDP CRN.
        
        Args:
            crn: CDP CRN string
            
        Returns:
            Entity name if found, None otherwise
        """
        match = re.match(r'crn:altus:iam:[^:]+:[^:]+:(?:user|group):([^/]+)/', crn)
        return match.group(1) if match else None
    
    def parse_mapping(self, mapping: Dict) -> MappingInfo:
        """
        Parse a mapping entry and extract structured information.
        
        Args:
            mapping: Dictionary containing accessorCrn and role
            
        Returns:
            MappingInfo object with parsed data
        """
        accessor_crn = mapping["accessorCrn"]
        role = mapping["role"]
        
        is_user = ":user:" in accessor_crn
        is_group = ":group:" in accessor_crn
        
        entity_name = self.extract_entity_name_from_crn(accessor_crn)
        entity_id = accessor_crn.split("/")[-1] if "/" in accessor_crn else ""
        
        return MappingInfo(
            accessor_crn=accessor_crn,
            role=role,
            is_user=is_user,
            is_group=is_group,
            entity_id=entity_id,
            entity_name=entity_name or ""
        )
    
    def validate_user_mapping(self, mapping_info: MappingInfo) -> bool:
        """
        Validate if a user mapping exists in CDP.
        
        Args:
            mapping_info: Parsed mapping information
            
        Returns:
            True if user exists, False otherwise
        """
        return mapping_info.accessor_crn in self.existing_users
    
    def validate_group_mapping(self, mapping_info: MappingInfo) -> bool:
        """
        Validate if a group mapping exists and has members.
        
        Args:
            mapping_info: Parsed mapping information
            
        Returns:
            True if group exists and has members, False otherwise
        """
        if mapping_info.accessor_crn in self.existing_groups:
            return True
        
        if mapping_info.accessor_crn in self.group_members:
            return len(self.group_members[mapping_info.accessor_crn]) > 0
        
        return False
    
    def validate_mappings(self, mappings: List[Dict]) -> None:
        """
        Validate all mappings and categorize them as valid or invalid.
        
        Args:
            mappings: List of mapping dictionaries to validate
        """
        print(f"\nValidating {len(mappings)} mappings...")
        
        group_crns = set()
        pbar = tqdm(mappings, desc="Extracting group CRNs", unit="mapping", total=len(mappings))
        try:
            for mapping in pbar:
                mapping_info = self.parse_mapping(mapping)
                if mapping_info.is_group:
                    group_crns.add(mapping_info.accessor_crn)
        finally:
            if HAS_TQDM:
                pbar.close()
        
        if group_crns:
            self.load_group_members(group_crns)
        
        print()  # Add spacing before validation results
        pbar = tqdm(mappings, desc="Validating mappings", unit="mapping", total=len(mappings))
        try:
            for idx, mapping in enumerate(pbar, 1):
                mapping_info = self.parse_mapping(mapping)
                is_valid = False
                
                if mapping_info.is_user:
                    is_valid = self.validate_user_mapping(mapping_info)
                    entity_type = "user"
                elif mapping_info.is_group:
                    is_valid = self.validate_group_mapping(mapping_info)
                    entity_type = "group"
                else:
                    print(f"Warning: Unknown entity type in CRN: {mapping_info.accessor_crn}")
                    is_valid = False
                    entity_type = "unknown"
                
                if is_valid:
                    self.validated_mappings.append(mapping)
                    status_msg = f"✓ Valid {entity_type}: {mapping_info.entity_name}"
                else:
                    self.invalid_mappings.append(mapping)
                    status_msg = f"✗ Invalid {entity_type}: {mapping_info.entity_name}"
                
                if HAS_TQDM:
                    pbar.set_description(f"[{idx}/{len(mappings)}] {status_msg}")
                else:
                    print(f"[{idx}/{len(mappings)}] {status_msg} ({mapping_info.accessor_crn})")
        finally:
            if HAS_TQDM:
                pbar.close()
    
    def create_clean_mapping_list(self, original_data: Dict) -> Dict:
        """
        Create a new mapping list containing only valid mappings.
        
        Args:
            original_data: Original mapping data structure
            
        Returns:
            Clean data structure with only valid mappings
        """
        clean_data = original_data.copy()
        clean_data["mappings"] = self.validated_mappings
        clean_data["setEmptyMappings"] = len(self.validated_mappings) == 0
        return clean_data
    
    def print_summary(self) -> None:
        """Print detailed validation summary to console."""
        print(f"\n{'='*60}")
        print("VALIDATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total mappings processed: {len(self.validated_mappings) + len(self.invalid_mappings)}")
        print(f"Valid mappings: {len(self.validated_mappings)}")
        print(f"Invalid mappings: {len(self.invalid_mappings)}")
        
        if self.invalid_mappings:
            print(f"\nINVALID MAPPINGS (will be excluded):")
            for mapping in self.invalid_mappings:
                mapping_info = self.parse_mapping(mapping)
                print(f"  - {mapping_info.entity_name} ({mapping_info.accessor_crn})")
    
    def save_clean_mappings(self, output_file: str, clean_data: Dict, original_data: Dict, env_name: Optional[str] = None, timestamp: Optional[str] = None) -> tuple:
        """
        Save the clean mapping data to a JSON file and create a backup of the original.
        Creates a timestamped directory structure if env_name and timestamp are provided.
        
        Args:
            output_file: Path to output file (or base name if using timestamped directory)
            clean_data: Clean mapping data to save
            original_data: Original mapping data to backup
            env_name: Environment name for directory structure (optional)
            timestamp: Timestamp string for directory structure (optional)
            
        Returns:
            Tuple of (backup_file_path, clean_file_path, directory_path)
        """
        if env_name and timestamp:
            base_dir = '/tmp'
            timestamped_dir = os.path.join(base_dir, f"{env_name}_mappings_{timestamp}")
            os.makedirs(timestamped_dir, exist_ok=True)
            
            backup_file = os.path.join(timestamped_dir, f"{env_name}_mappings_{timestamp}_original.json")
            clean_file = os.path.join(timestamped_dir, f"clean_{env_name}_mappings_{timestamp}.json")
        else:
            output_dir = os.path.dirname(output_file) if os.path.dirname(output_file) else '.'
            output_basename = os.path.basename(output_file)
            
            output_name, output_ext = os.path.splitext(output_basename)
            if output_name.startswith('clean_'):
                backup_name = output_name[6:] + '_original' + output_ext
            else:
                backup_name = output_name + '_original' + output_ext
            
            backup_file = os.path.join(output_dir, backup_name)
            clean_file = output_file
            timestamped_dir = output_dir
        
        with open(clean_file, 'w') as f:
            json.dump(clean_data, f, indent=2)
        print(f"\nClean mappings saved to: {clean_file}")
        
        with open(backup_file, 'w') as f:
            json.dump(original_data, f, indent=2)
        print(f"Original mappings backup saved to: {backup_file}")
        
        return (backup_file, clean_file, timestamped_dir)
    
    def print_final_report(self, backup_file: str, clean_file: str, directory: str, env_name: Optional[str] = None) -> None:
        """
        Print final report with file locations and example command to apply mappings.
        
        Args:
            backup_file: Path to backup file
            clean_file: Path to clean mappings file
            directory: Directory where files are stored
            env_name: Environment name (optional)
        """
        print(f"\n{'='*70}")
        print("VALIDATION COMPLETE - FILE LOCATIONS")
        print(f"{'='*70}")
        print(f"Backup directory: {directory}")
        print(f"Original backup:  {backup_file}")
        print(f"Clean mappings:    {clean_file}")
        
        print(f"\n{'='*70}")
        print("TO APPLY THE CLEAN MAPPINGS TO YOUR CDP ENVIRONMENT")
        print(f"{'='*70}")
        print("Use the following command:\n")
        
        abs_clean_file = os.path.abspath(clean_file)
        print(f"cdp environments set-id-broker-mappings \\")
        print(f"  --cli-input-json \"file://{abs_clean_file}\"")
        
        if env_name:
            print(f"\n# Or with environment name variable:")
            print(f"ENV_NAME=\"{env_name}\"")
            print(f"CLEAN_FILE=\"{abs_clean_file}\"")
            print(f"cdp environments set-id-broker-mappings \\")
            print(f"  --cli-input-json \"file://${{CLEAN_FILE}}\"")
        
        print(f"\n{'='*70}")


def main():
    """
    Main entry point for the IDBroker mappings validator.
    
    Parses command line arguments, loads input data, validates mappings,
    and generates clean output files.
    """
    parser = argparse.ArgumentParser(description="Validate IDBroker mappings")
    parser.add_argument("input_file", nargs="?", help="Input JSON file with mappings")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    parser.add_argument("--output", "-o", default="clean_mappings.json", help="Output file for clean mappings (or base name if using timestamped directory)")
    parser.add_argument("--env-name", help="Environment name for timestamped directory structure (auto-detected from input if not provided)")
    parser.add_argument("--timestamp", help="Timestamp string for directory structure (auto-generated if not provided)")
    
    args = parser.parse_args()
    
    if args.stdin:
        try:
            data = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON input: {e}")
            sys.exit(1)
    elif args.input_file:
        try:
            with open(args.input_file, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"Error: File not found: {args.input_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in file: {e}")
            sys.exit(1)
    else:
        print("Error: Please provide either an input file or use --stdin")
        parser.print_help()
        sys.exit(1)
    
    validator = IDBrokerMappingValidator()
    
    try:
        env_name = args.env_name
        if not env_name:
            env_name = data.get("environmentName")
        
        timestamp = args.timestamp
        if not timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        validator.load_existing_users()
        validator.load_existing_groups()
        
        mappings = data.get("mappings", [])
        if not mappings:
            print("Warning: No mappings found in input data")
            sys.exit(0)
        
        validator.validate_mappings(mappings)
        
        clean_data = validator.create_clean_mapping_list(data)
        
        validator.print_summary()
        
        backup_file, clean_file, directory = validator.save_clean_mappings(
            args.output, clean_data, data, env_name, timestamp
        )
        
        validator.print_final_report(backup_file, clean_file, directory, env_name)
        
        if validator.invalid_mappings:
            print(f"\nWarning: {len(validator.invalid_mappings)} invalid mappings were found and excluded.")
            print("Review the invalid mappings above and update your source data if needed.")
            sys.exit(1)
        else:
            print("\n✓ All mappings are valid!")
            sys.exit(0)
            
    except CDPCLIError as e:
        print(f"Error: {e}")
        print("Make sure CDP CLI is installed and configured properly.")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
