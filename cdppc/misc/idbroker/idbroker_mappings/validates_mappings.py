#!/usr/bin/env python3
"""
IDBroker Mappings Validator

This script validates IDBroker mappings by checking if users and groups exist
before creating a new mapping list. It helps prevent "NOT_FOUND" errors during
datalake creation.

Usage:
    python validates_mappings.py <input_json_file>
    python validates_mappings.py --stdin  # Read from stdin
"""

import json
import sys
import subprocess
import argparse
import re
from typing import Dict, List, Set, Optional
from dataclasses import dataclass


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
            for user in users_data.get("users", []):
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
            for group in groups_data.get("groups", []):
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
        print("Loading group members...")
        for group_crn in group_crns:
            try:
                group_name = self.extract_entity_name_from_crn(group_crn)
                if not group_name:
                    continue
                
                members_data = self.run_cdp_command(["cdp", "iam", "list-group-members", "--group-name", group_name])
                member_crns = set()
                for member in members_data.get("members", []):
                    member_crns.add(member["crn"])
                self.group_members[group_crn] = member_crns
                print(f"Loaded {len(member_crns)} members for group {group_name}")
            except CDPCLIError as e:
                print(f"Warning: Could not load members for group {group_crn}: {e}")
                self.group_members[group_crn] = set()
    
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
        for mapping in mappings:
            mapping_info = self.parse_mapping(mapping)
            if mapping_info.is_group:
                group_crns.add(mapping_info.accessor_crn)
        
        if group_crns:
            self.load_group_members(group_crns)
        
        for mapping in mappings:
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
                print(f"✓ Valid {entity_type}: {mapping_info.entity_name} ({mapping_info.accessor_crn})")
            else:
                self.invalid_mappings.append(mapping)
                print(f"✗ Invalid {entity_type}: {mapping_info.entity_name} ({mapping_info.accessor_crn})")
    
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
    
    def save_clean_mappings(self, output_file: str, clean_data: Dict) -> None:
        """
        Save the clean mapping data to a JSON file.
        
        Args:
            output_file: Path to output file
            clean_data: Clean mapping data to save
        """
        with open(output_file, 'w') as f:
            json.dump(clean_data, f, indent=2)
        print(f"\nClean mappings saved to: {output_file}")


def main():
    """
    Main entry point for the IDBroker mappings validator.
    
    Parses command line arguments, loads input data, validates mappings,
    and generates clean output files.
    """
    parser = argparse.ArgumentParser(description="Validate IDBroker mappings")
    parser.add_argument("input_file", nargs="?", help="Input JSON file with mappings")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    parser.add_argument("--output", "-o", default="clean_mappings.json", help="Output file for clean mappings")
    
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
        validator.load_existing_users()
        validator.load_existing_groups()
        
        mappings = data.get("mappings", [])
        if not mappings:
            print("Warning: No mappings found in input data")
            sys.exit(0)
        
        validator.validate_mappings(mappings)
        
        clean_data = validator.create_clean_mapping_list(data)
        
        validator.print_summary()
        
        validator.save_clean_mappings(args.output, clean_data)
        
        if validator.invalid_mappings:
            print(f"\nWarning: {len(validator.invalid_mappings)} invalid mappings were found and excluded.")
            print("Review the invalid mappings above and update your source data if needed.")
            sys.exit(1)
        else:
            print("\nAll mappings are valid!")
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
