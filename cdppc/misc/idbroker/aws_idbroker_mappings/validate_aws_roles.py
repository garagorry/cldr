#!/usr/bin/env python3
"""
AWS IAM Role Validator for IDBroker Mappings

This script validates IDBroker mappings by checking if AWS IAM roles exist
using AWS CLI. It helps identify missing or incorrect role ARNs before
creating IDBroker mappings in CDP.

Usage:
    python validate_aws_roles.py <input_json_file>
    python validate_aws_roles.py --stdin  # Read from stdin
    python validate_aws_roles.py <input_json_file> --aws-profile <profile_name>
"""

import json
import sys
import subprocess
import argparse
import re
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RoleMappingInfo:
    """Information about a role mapping entry."""
    accessor_crn: str
    role_arn: str
    is_user: bool
    is_group: bool
    entity_name: str
    role_name: str


@dataclass
class RoleValidationResult:
    """Result of validating an AWS IAM role."""
    role_arn: str
    exists: bool
    error_message: Optional[str] = None
    role_details: Optional[Dict] = None


class AWSCLIError(Exception):
    """Custom exception for AWS CLI command failures."""


class AWSIAMRoleValidator:
    """
    Validates IDBroker mappings by checking AWS IAM role existence.
    
    This class provides functionality to:
    - Extract AWS IAM role ARNs from IDBroker mappings
    - Validate role existence using AWS CLI
    - Generate detailed reports of missing/invalid roles
    - Create clean mapping lists with only valid roles
    """
    
    def __init__(self, aws_profile: Optional[str] = None):
        """
        Initialize the validator.
        
        Args:
            aws_profile: AWS CLI profile name to use (optional)
        """
        self.aws_profile = aws_profile
        self.existing_roles: Dict[str, Dict] = {}  # role_arn -> role details
        self.validated_mappings: List[Dict] = []
        self.invalid_mappings: List[Dict] = []
        self.validation_results: Dict[str, RoleValidationResult] = {}
        self.unique_roles: Set[str] = set()
    
    def run_aws_command(self, command: List[str]) -> Dict:
        """
        Execute an AWS CLI command and return parsed JSON output.
        
        Args:
            command: List of command arguments to execute
            
        Returns:
            Parsed JSON response from AWS CLI
            
        Raises:
            AWSCLIError: If command fails or output cannot be parsed
        """
        # Add profile if specified
        if self.aws_profile:
            command.extend(["--profile", self.aws_profile])
        
        # Always request JSON output
        if "--output" not in command:
            command.extend(["--output", "json"])
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
            if result.stdout.strip():
                return json.loads(result.stdout)
            return {}
        except subprocess.CalledProcessError as e:
            raise AWSCLIError(f"AWS CLI command failed: {e.stderr}")
        except json.JSONDecodeError as e:
            raise AWSCLIError(f"Failed to parse AWS CLI output: {e}")
    
    def extract_role_name_from_arn(self, role_arn: str) -> Optional[str]:
        """
        Extract role name from AWS IAM role ARN.
        
        Args:
            role_arn: AWS IAM role ARN
            
        Returns:
            Role name if found, None otherwise
            
        Example:
            arn:aws:iam::123456789012:role/my-role -> my-role
        """
        match = re.match(r'arn:aws:iam::\d+:role/(.+)', role_arn)
        return match.group(1) if match else None
    
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
    
    def validate_role_existence(self, role_arn: str) -> RoleValidationResult:
        """
        Check if an AWS IAM role exists using AWS CLI.
        
        Args:
            role_arn: AWS IAM role ARN to validate
            
        Returns:
            RoleValidationResult with validation details
        """
        # Check cache first
        if role_arn in self.validation_results:
            return self.validation_results[role_arn]
        
        role_name = self.extract_role_name_from_arn(role_arn)
        if not role_name:
            result = RoleValidationResult(
                role_arn=role_arn,
                exists=False,
                error_message="Invalid role ARN format"
            )
            self.validation_results[role_arn] = result
            return result
        
        try:
            response = self.run_aws_command([
                "aws", "iam", "get-role",
                "--role-name", role_name
            ])
            
            role_details = response.get("Role", {})
            result = RoleValidationResult(
                role_arn=role_arn,
                exists=True,
                role_details=role_details
            )
            self.existing_roles[role_arn] = role_details
            
        except AWSCLIError as e:
            error_msg = str(e)
            # Check if it's a "NoSuchEntity" error
            if "NoSuchEntity" in error_msg or "NotFound" in error_msg:
                result = RoleValidationResult(
                    role_arn=role_arn,
                    exists=False,
                    error_message="Role does not exist in AWS"
                )
            else:
                result = RoleValidationResult(
                    role_arn=role_arn,
                    exists=False,
                    error_message=error_msg
                )
        
        self.validation_results[role_arn] = result
        return result
    
    def parse_mapping(self, mapping: Dict) -> RoleMappingInfo:
        """
        Parse a mapping entry and extract structured information.
        
        Args:
            mapping: Dictionary containing accessorCrn and role
            
        Returns:
            RoleMappingInfo object with parsed data
        """
        accessor_crn = mapping.get("accessorCrn", "")
        role_arn = mapping.get("role", "")
        
        is_user = ":user:" in accessor_crn
        is_group = ":group:" in accessor_crn
        
        entity_name = self.extract_entity_name_from_crn(accessor_crn)
        role_name = self.extract_role_name_from_arn(role_arn)
        
        return RoleMappingInfo(
            accessor_crn=accessor_crn,
            role_arn=role_arn,
            is_user=is_user,
            is_group=is_group,
            entity_name=entity_name or "unknown",
            role_name=role_name or "unknown"
        )
    
    def validate_mappings(self, mappings: List[Dict]) -> None:
        """
        Validate all mappings by checking AWS IAM role existence.
        
        Args:
            mappings: List of mapping dictionaries to validate
        """
        print(f"\nValidating {len(mappings)} mappings...")
        
        # Extract unique roles first
        for mapping in mappings:
            mapping_info = self.parse_mapping(mapping)
            if mapping_info.role_arn:
                self.unique_roles.add(mapping_info.role_arn)
        
        print(f"Found {len(self.unique_roles)} unique AWS IAM roles to validate\n")
        
        # Validate each mapping
        for idx, mapping in enumerate(mappings, 1):
            mapping_info = self.parse_mapping(mapping)
            
            if not mapping_info.role_arn:
                self.invalid_mappings.append(mapping)
                print(f"[{idx}/{len(mappings)}] ✗ Missing role ARN for {mapping_info.entity_name}")
                continue
            
            # Validate the role
            validation_result = self.validate_role_existence(mapping_info.role_arn)
            
            entity_type = "user" if mapping_info.is_user else "group" if mapping_info.is_group else "unknown"
            
            if validation_result.exists:
                self.validated_mappings.append(mapping)
                print(f"[{idx}/{len(mappings)}] ✓ Valid - {entity_type}: {mapping_info.entity_name} -> {mapping_info.role_name}")
            else:
                self.invalid_mappings.append(mapping)
                print(f"[{idx}/{len(mappings)}] ✗ Invalid - {entity_type}: {mapping_info.entity_name} -> {mapping_info.role_name}")
                print(f"    Error: {validation_result.error_message}")
    
    def generate_report(self) -> Dict:
        """
        Generate a comprehensive validation report.
        
        Returns:
            Dictionary containing detailed validation report
        """
        report = {
            "validation_timestamp": datetime.now().isoformat(),
            "aws_profile": self.aws_profile or "default",
            "summary": {
                "total_mappings": len(self.validated_mappings) + len(self.invalid_mappings),
                "valid_mappings": len(self.validated_mappings),
                "invalid_mappings": len(self.invalid_mappings),
                "unique_roles_found": len(self.unique_roles),
                "existing_roles": len(self.existing_roles),
                "missing_roles": len([r for r in self.validation_results.values() if not r.exists])
            },
            "missing_roles": [],
            "invalid_mappings_details": []
        }
        
        # Collect missing roles
        missing_roles_set = set()
        for role_arn, result in self.validation_results.items():
            if not result.exists:
                missing_roles_set.add(role_arn)
                report["missing_roles"].append({
                    "role_arn": role_arn,
                    "role_name": self.extract_role_name_from_arn(role_arn),
                    "error": result.error_message
                })
        
        # Collect invalid mapping details
        for mapping in self.invalid_mappings:
            mapping_info = self.parse_mapping(mapping)
            entity_type = "user" if mapping_info.is_user else "group" if mapping_info.is_group else "unknown"
            
            validation_result = self.validation_results.get(mapping_info.role_arn)
            
            report["invalid_mappings_details"].append({
                "entity_type": entity_type,
                "entity_name": mapping_info.entity_name,
                "accessor_crn": mapping_info.accessor_crn,
                "role_arn": mapping_info.role_arn,
                "role_name": mapping_info.role_name,
                "error": validation_result.error_message if validation_result else "Unknown error"
            })
        
        return report
    
    def print_summary(self) -> None:
        """Print detailed validation summary to console."""
        print(f"\n{'='*70}")
        print("AWS IAM ROLE VALIDATION SUMMARY")
        print(f"{'='*70}")
        print(f"Total mappings processed: {len(self.validated_mappings) + len(self.invalid_mappings)}")
        print(f"Valid mappings: {len(self.validated_mappings)}")
        print(f"Invalid mappings: {len(self.invalid_mappings)}")
        print(f"Unique roles checked: {len(self.unique_roles)}")
        print(f"Existing roles: {len(self.existing_roles)}")
        print(f"Missing roles: {len([r for r in self.validation_results.values() if not r.exists])}")
        
        # Print missing roles
        missing_roles = [r for r in self.validation_results.values() if not r.exists]
        if missing_roles:
            print(f"\n{'='*70}")
            print("MISSING AWS IAM ROLES:")
            print(f"{'='*70}")
            for result in missing_roles:
                role_name = self.extract_role_name_from_arn(result.role_arn)
                print(f"  ✗ {role_name}")
                print(f"    ARN: {result.role_arn}")
                print(f"    Error: {result.error_message}")
                
                # List which users/groups are mapped to this role
                affected_entities = []
                for mapping in self.invalid_mappings:
                    mapping_info = self.parse_mapping(mapping)
                    if mapping_info.role_arn == result.role_arn:
                        entity_type = "user" if mapping_info.is_user else "group"
                        affected_entities.append(f"{entity_type}:{mapping_info.entity_name}")
                
                if affected_entities:
                    print(f"    Affected entities: {', '.join(affected_entities)}")
                print()
    
    def save_report(self, output_file: str, report: Dict) -> None:
        """
        Save the validation report to a JSON file.
        
        Args:
            output_file: Path to output file
            report: Report data to save
        """
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\nDetailed report saved to: {output_file}")
    
    def save_clean_mappings(self, output_file: str, original_data: Dict) -> None:
        """
        Save clean mappings (only valid ones) to a JSON file.
        
        Args:
            output_file: Path to output file
            original_data: Original mapping data structure
        """
        clean_data = original_data.copy()
        clean_data["mappings"] = self.validated_mappings
        clean_data["setEmptyMappings"] = len(self.validated_mappings) == 0
        
        with open(output_file, 'w') as f:
            json.dump(clean_data, f, indent=2)
        print(f"Clean mappings (valid only) saved to: {output_file}")


def main():
    """
    Main entry point for the AWS IAM role validator.
    
    Parses command line arguments, loads input data, validates roles,
    and generates reports.
    """
    parser = argparse.ArgumentParser(
        description="Validate AWS IAM roles in IDBroker mappings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate mappings from a file
  python validate_aws_roles.py mappings.json

  # Validate with specific AWS profile
  python validate_aws_roles.py mappings.json --aws-profile prod

  # Read from stdin
  cat mappings.json | python validate_aws_roles.py --stdin

  # Custom output files
  python validate_aws_roles.py mappings.json -o clean.json -r report.json
        """
    )
    
    parser.add_argument("input_file", nargs="?", help="Input JSON file with IDBroker mappings")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    parser.add_argument("--aws-profile", "-p", help="AWS CLI profile to use")
    parser.add_argument("--output", "-o", default="clean_aws_mappings.json", 
                       help="Output file for clean mappings (default: clean_aws_mappings.json)")
    parser.add_argument("--report", "-r", default="aws_role_validation_report.json",
                       help="Output file for validation report (default: aws_role_validation_report.json)")
    
    args = parser.parse_args()
    
    # Load input data
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
    
    # Initialize validator
    validator = AWSIAMRoleValidator(aws_profile=args.aws_profile)
    
    try:
        # Extract and validate mappings
        mappings = data.get("mappings", [])
        if not mappings:
            print("Warning: No mappings found in input data")
            sys.exit(0)
        
        # Validate all mappings
        validator.validate_mappings(mappings)
        
        # Generate and display summary
        validator.print_summary()
        
        # Generate detailed report
        report = validator.generate_report()
        validator.save_report(args.report, report)
        
        # Save clean mappings
        validator.save_clean_mappings(args.output, data)
        
        # Exit with appropriate code
        if validator.invalid_mappings:
            print(f"\n⚠️  {len(validator.invalid_mappings)} invalid mappings were found.")
            print(f"Review the report ({args.report}) for details.")
            sys.exit(1)
        else:
            print("\n✓ All mappings are valid!")
            sys.exit(0)
            
    except AWSCLIError as e:
        print(f"\nError: {e}")
        print("Make sure AWS CLI is installed and configured properly.")
        print("Run 'aws configure' or set AWS_PROFILE environment variable.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nValidation interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

