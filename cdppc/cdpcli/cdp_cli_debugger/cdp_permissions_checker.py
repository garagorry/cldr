#!/usr/bin/env python3
"""
CDP Permissions Checker

This script specifically checks file permissions using namei -l command
and provides detailed permission analysis for CDP configuration files.

Usage:
    python cdp_permissions_checker.py [--profile PROFILE] [--debug] [--verbose]
"""

import os
import sys
import json
import subprocess
import logging
import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

def setup_logging(debug: bool = False, verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if debug else (logging.INFO if verbose else logging.WARNING)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    if debug:
        log_dir = Path("/tmp/cdp_debug_logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"cdp_permissions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        logging.getLogger().addHandler(file_handler)
        logging.getLogger().addHandler(console_handler)
        logging.getLogger().setLevel(logging.DEBUG)
        
        print(f"📝 Permissions debug logs will be saved to: {log_file}")
    else:
        logging.getLogger().addHandler(console_handler)
        logging.getLogger().setLevel(level)
    
    logging.getLogger().propagate = False

class CDPPermissionsChecker:
    """Class for checking CDP file permissions using namei -l."""
    
    def __init__(self, profile: str = "default", debug: bool = False, verbose: bool = False):
        self.profile = profile
        self.debug = debug
        self.verbose = verbose
        self.cdp_home = Path.home() / ".cdp"
        self.credentials_file = self.cdp_home / "credentials"
        self.config_file = self.cdp_home / "config"
        
        setup_logging(debug, verbose)
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"🔐 CDP Permissions Checker initialized")
        self.logger.info(f"📁 CDP Home: {self.cdp_home}")
        self.logger.info(f"🔑 Credentials file: {self.credentials_file}")
        self.logger.info(f"⚙️  Config file: {self.config_file}")
        self.logger.info(f"👤 Profile: {self.profile}")
    
    def run_permissions_check(self) -> Dict:
        """Run comprehensive permissions check using namei -l."""
        self.logger.info("🚀 Starting CDP permissions check")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "profile": self.profile,
            "cdp_home": str(self.cdp_home),
            "namei_available": self._check_namei_availability(),
            "permissions": {}
        }
        
        # Check permissions for each file
        if results["namei_available"]:
            results["permissions"]["credentials"] = self._check_file_permissions_namei(self.credentials_file)
            results["permissions"]["config"] = self._check_file_permissions_namei(self.config_file)
            results["permissions"]["cdp_home"] = self._check_file_permissions_namei(self.cdp_home)
        else:
            self.logger.warning("namei command not available, using alternative permission checking")
            results["permissions"]["credentials"] = self._check_file_permissions_alternative(self.credentials_file)
            results["permissions"]["config"] = self._check_file_permissions_alternative(self.config_file)
            results["permissions"]["cdp_home"] = self._check_file_permissions_alternative(self.cdp_home)
        
        # Analyze permissions
        results["analysis"] = self._analyze_permissions(results["permissions"])
        
        # Check credentials content
        results["credentials_content"] = self._check_credentials_content()
        
        self.logger.info("✅ CDP permissions check completed")
        return results
    
    def _check_namei_availability(self) -> bool:
        """Check if namei command is available."""
        try:
            result = subprocess.run(
                ["namei", "--help"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _check_file_permissions_namei(self, file_path: Path) -> Dict:
        """Check file permissions using namei -l command."""
        self.logger.info(f"🔍 Checking permissions for: {file_path}")
        
        permission_info = {
            "file_path": str(file_path),
            "exists": file_path.exists(),
            "namei_output": None,
            "parsed_permissions": [],
            "security_issues": [],
            "error": None
        }
        
        if not permission_info["exists"]:
            permission_info["error"] = "File does not exist"
            return permission_info
        
        try:
            # Run namei -l command
            result = subprocess.run(
                ["namei", "-l", str(file_path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                permission_info["namei_output"] = result.stdout.strip()
                permission_info["parsed_permissions"] = self._parse_namei_output(result.stdout)
                permission_info["security_issues"] = self._check_security_issues_namei(permission_info["parsed_permissions"])
            else:
                permission_info["error"] = f"namei command failed: {result.stderr.strip()}"
                
        except subprocess.TimeoutExpired:
            permission_info["error"] = "namei command timed out"
        except Exception as e:
            permission_info["error"] = f"Unexpected error: {e}"
        
        self.logger.debug(f"Permission info for {file_path}: {json.dumps(permission_info, indent=2)}")
        return permission_info
    
    def _parse_namei_output(self, output: str) -> List[Dict]:
        """Parse namei -l output into structured data."""
        parsed = []
        
        for line in output.strip().split('\n'):
            if line.strip():
                # Parse each line: f: /home/user/.cdp/credentials 0755 user user
                parts = line.split()
                if len(parts) >= 4:
                    entry = {
                        "type": parts[0],  # f, d, l, etc.
                        "path": parts[1],  # Full path
                        "permissions": parts[2],  # Octal permissions
                        "owner": parts[3],  # Owner
                        "group": parts[4] if len(parts) > 4 else "unknown"  # Group
                    }
                    parsed.append(entry)
        
        return parsed
    
    def _check_security_issues_namei(self, permissions: List[Dict]) -> List[str]:
        """Check for security issues in parsed namei output."""
        issues = []
        
        for entry in permissions:
            path = entry["path"]
            perms = entry["permissions"]
            owner = entry["owner"]
            group = entry["group"]
            
            # Check if it's a credentials or config file
            if "credentials" in path or "config" in path:
                # Check for world read/write permissions
                if len(perms) >= 3:
                    world_perms = perms[-1]
                    if world_perms in ['6', '7']:  # Write permissions for others
                        issues.append(f"World write permissions on {path}: {perms}")
                    if world_perms in ['4', '5', '6', '7']:  # Read permissions for others
                        issues.append(f"World read permissions on {path}: {perms}")
                
                # Check for group write permissions
                if len(perms) >= 3:
                    group_perms = perms[-2]
                    if group_perms in ['6', '7']:  # Write permissions for group
                        issues.append(f"Group write permissions on {path}: {perms}")
            
            # Check for symbolic links (potential security risk)
            if entry["type"] == "l":
                issues.append(f"Symbolic link found: {path}")
        
        return issues
    
    def _check_file_permissions_alternative(self, file_path: Path) -> Dict:
        """Alternative permission checking when namei is not available."""
        self.logger.info(f"🔍 Checking permissions (alternative method) for: {file_path}")
        
        permission_info = {
            "file_path": str(file_path),
            "exists": file_path.exists(),
            "method": "alternative",
            "permissions": None,
            "security_issues": [],
            "error": None
        }
        
        if not permission_info["exists"]:
            permission_info["error"] = "File does not exist"
            return permission_info
        
        try:
            # Use ls -la command as alternative
            result = subprocess.run(
                ["ls", "-la", str(file_path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                permission_info["ls_output"] = result.stdout.strip()
                permission_info["permissions"] = self._parse_ls_output(result.stdout)
                permission_info["security_issues"] = self._check_security_issues_alternative(permission_info["permissions"])
            else:
                permission_info["error"] = f"ls command failed: {result.stderr.strip()}"
                
        except subprocess.TimeoutExpired:
            permission_info["error"] = "ls command timed out"
        except Exception as e:
            permission_info["error"] = f"Unexpected error: {e}"
        
        return permission_info
    
    def _parse_ls_output(self, output: str) -> Dict:
        """Parse ls -la output."""
        lines = output.strip().split('\n')
        if not lines:
            return {}
        
        # Parse the first line (file info)
        line = lines[0]
        parts = line.split()
        
        if len(parts) >= 9:
            return {
                "permissions": parts[0],
                "links": parts[1],
                "owner": parts[2],
                "group": parts[3],
                "size": parts[4],
                "date": " ".join(parts[5:8]),
                "name": parts[8]
            }
        
        return {}
    
    def _check_security_issues_alternative(self, permissions: Dict) -> List[str]:
        """Check for security issues in ls output."""
        issues = []
        
        if not permissions:
            return issues
        
        perms = permissions.get("permissions", "")
        if len(perms) >= 10:
            # Check world permissions (last 3 characters)
            world_perms = perms[-3:]
            if world_perms[1] == 'w':  # World write
                issues.append(f"World write permissions: {perms}")
            if world_perms[0] == 'r':  # World read
                issues.append(f"World read permissions: {perms}")
            
            # Check group permissions (characters 5-7)
            group_perms = perms[4:7]
            if group_perms[1] == 'w':  # Group write
                issues.append(f"Group write permissions: {perms}")
        
        return issues
    
    def _check_credentials_content(self) -> Dict:
        """Check credentials file content and show profiles with masked sensitive data."""
        self.logger.info("🔑 Checking credentials file content")
        
        cred_info = {
            "file_exists": self.credentials_file.exists(),
            "profiles": [],
            "profile_details": {},
            "parsing_errors": [],
        }
        
        if not cred_info["file_exists"]:
            return cred_info
        
        try:
            import configparser
            config = configparser.ConfigParser()
            config.read(self.credentials_file)
            
            # Get all profiles
            cred_info["profiles"] = config.sections()
            
            # Get details for each profile (masking sensitive data)
            for profile in config.sections():
                profile_data = {}
                for key, value in config[profile].items():
                    if key.lower() in ['cdp_access_key_id', 'cdp_private_key']:
                        # Mask sensitive data
                        if value:
                            if len(value) > 8:
                                masked_value = value[:4] + "*" * (len(value) - 8) + value[-4:]
                            else:
                                masked_value = "***"
                            profile_data[key] = masked_value
                        else:
                            profile_data[key] = "***"
                    else:
                        profile_data[key] = value
                
                cred_info["profile_details"][profile] = profile_data
            
            # Check for required fields in the specified profile
            if self.profile in config.sections():
                profile_section = config[self.profile]
                required_fields = ['cdp_access_key_id', 'cdp_private_key']
                missing_fields = [field for field in required_fields if not profile_section.get(field)]
                
                if missing_fields:
                    cred_info["parsing_errors"].append(f"Profile '{self.profile}' missing required fields: {missing_fields}")
            
        except Exception as e:
            cred_info["parsing_errors"].append(f"Error parsing credentials: {e}")
        
        return cred_info
    
    def _analyze_permissions(self, permissions: Dict) -> Dict:
        """Analyze permissions and provide recommendations."""
        self.logger.info("📊 Analyzing permissions")
        
        analysis = {
            "overall_status": "UNKNOWN",
            "critical_issues": [],
            "warnings": [],
            "recommendations": [],
            "secure_files": [],
            "insecure_files": []
        }
        
        for file_type, file_info in permissions.items():
            if file_info.get("error"):
                analysis["critical_issues"].append(f"{file_type}: {file_info['error']}")
                analysis["insecure_files"].append(file_type)
            elif file_info.get("security_issues"):
                analysis["warnings"].extend([f"{file_type}: {issue}" for issue in file_info["security_issues"]])
                analysis["insecure_files"].append(file_type)
            else:
                analysis["secure_files"].append(file_type)
        
        # Determine overall status
        if analysis["critical_issues"]:
            analysis["overall_status"] = "CRITICAL"
        elif analysis["warnings"]:
            analysis["overall_status"] = "WARNING"
        elif analysis["secure_files"] and not analysis["insecure_files"]:
            analysis["overall_status"] = "SECURE"
        else:
            analysis["overall_status"] = "UNKNOWN"
        
        # Generate recommendations
        if analysis["overall_status"] == "CRITICAL":
            analysis["recommendations"].append("Fix critical permission issues immediately")
        
        if analysis["overall_status"] in ["CRITICAL", "WARNING"]:
            analysis["recommendations"].append("Set proper file permissions: chmod 600 ~/.cdp/credentials")
            analysis["recommendations"].append("Set proper directory permissions: chmod 700 ~/.cdp")
            analysis["recommendations"].append("Ensure files are owned by the current user")
        
        if "credentials" in analysis["insecure_files"]:
            analysis["recommendations"].append("Credentials file has insecure permissions - fix immediately")
        
        return analysis
    
    def print_results(self, results: Dict) -> None:
        """Print formatted results to console."""
        print("\n" + "="*80)
        print("🔐 CDP PERMISSIONS CHECK RESULTS")
        print("="*80)
        
        # Print summary
        analysis = results["analysis"]
        status_emoji = {
            "SECURE": "✅",
            "WARNING": "⚠️",
            "CRITICAL": "🚨",
            "UNKNOWN": "❓"
        }
        
        print(f"\n📊 OVERALL STATUS: {status_emoji.get(analysis['overall_status'], '❓')} {analysis['overall_status']}")
        
        if analysis["secure_files"]:
            print(f"✅ Secure files: {', '.join(analysis['secure_files'])}")
        
        if analysis["insecure_files"]:
            print(f"❌ Insecure files: {', '.join(analysis['insecure_files'])}")
        
        if analysis["critical_issues"]:
            print(f"\n🚨 CRITICAL ISSUES:")
            for issue in analysis["critical_issues"]:
                print(f"   • {issue}")
        
        if analysis["warnings"]:
            print(f"\n⚠️  WARNINGS:")
            for warning in analysis["warnings"]:
                print(f"   • {warning}")
        
        if analysis["recommendations"]:
            print(f"\n💡 RECOMMENDATIONS:")
            for rec in analysis["recommendations"]:
                print(f"   • {rec}")
        
        # Print detailed permissions if verbose or debug
        if self.verbose or self.debug:
            print(f"\n🔍 DETAILED PERMISSIONS:")
            
            for file_type, file_info in results["permissions"].items():
                print(f"\n--- {file_type.upper()} ---")
                print(f"  File: {file_info.get('file_path', 'N/A')}")
                print(f"  Exists: {file_info.get('exists', 'N/A')}")
                
                if file_info.get("namei_output"):
                    print(f"  namei -l output:")
                    for line in file_info["namei_output"].split('\n'):
                        print(f"    {line}")
                
                if file_info.get("parsed_permissions"):
                    print(f"  Parsed permissions:")
                    for perm in file_info["parsed_permissions"]:
                        print(f"    {perm['type']} {perm['path']} {perm['permissions']} {perm['owner']} {perm['group']}")
                
                if file_info.get("security_issues"):
                    print(f"  Security issues:")
                    for issue in file_info["security_issues"]:
                        print(f"    • {issue}")
                
                if file_info.get("error"):
                    print(f"  Error: {file_info['error']}")
        
        # Print credentials content
        cred_content = results["credentials_content"]
        if cred_content["file_exists"]:
            print(f"\n🔑 CREDENTIALS PROFILES:")
            print(f"  Available profiles: {', '.join(cred_content['profiles'])}")
            
            if self.verbose or self.debug:
                for profile, details in cred_content["profile_details"].items():
                    print(f"\n  Profile: {profile}")
                    for key, value in details.items():
                        print(f"    {key}: {value}")
            
            if cred_content["parsing_errors"]:
                print(f"\n  Parsing errors:")
                for error in cred_content["parsing_errors"]:
                    print(f"    • {error}")
        
        print("\n" + "="*80)

def main():
    """Main function to run the CDP permissions checker."""
    parser = argparse.ArgumentParser(
        description="Check CDP file permissions using namei -l",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cdp_permissions_checker.py
  python cdp_permissions_checker.py --debug --verbose
  python cdp_permissions_checker.py --profile my-profile --debug
        """
    )
    
    parser.add_argument(
        "--profile",
        default="default",
        help="CDP profile to check (default: default)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging and save logs to file"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--output",
        help="Output file for JSON results (optional)"
    )
    
    args = parser.parse_args()
    
    # Create checker instance
    checker = CDPPermissionsChecker(
        profile=args.profile,
        debug=args.debug,
        verbose=args.verbose
    )
    
    try:
        # Run permissions check
        results = checker.run_permissions_check()
        
        # Print results
        checker.print_results(results)
        
        # Save to file if requested
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n💾 Results saved to: {output_path}")
        
        # Exit with appropriate code
        analysis = results["analysis"]
        if analysis["overall_status"] == "CRITICAL":
            sys.exit(1)
        elif analysis["overall_status"] == "WARNING":
            sys.exit(2)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Permissions check interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 