#!/usr/bin/env python3
"""
CDP Configuration Debugger

This script helps debug CDP configuration issues by:
1. Checking file permissions and ownership
2. Validating CDP credentials and config files
3. Testing CDP CLI functionality
4. Comparing shell vs Python behavior
5. Providing detailed logging and debugging information

Usage:
    python cdp_config_debugger.py [--profile PROFILE] [--debug] [--verbose]
"""

import os
import sys
import json
import subprocess
import logging
import argparse
import stat
import pwd
import grp
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import configparser
import shutil
from datetime import datetime

# Configure logging
def setup_logging(debug: bool = False, verbose: bool = False):
    """Setup logging configuration with appropriate level and format."""
    level = logging.DEBUG if debug else (logging.INFO if verbose else logging.WARNING)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    # Setup file handler for debug logs
    if debug:
        log_dir = Path("/tmp/cdp_debug_logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"cdp_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # Add both handlers
        logging.getLogger().addHandler(file_handler)
        logging.getLogger().addHandler(console_handler)
        logging.getLogger().setLevel(logging.DEBUG)
        
        print(f"📝 Debug logs will be saved to: {log_file}")
    else:
        # Add only console handler
        logging.getLogger().addHandler(console_handler)
        logging.getLogger().setLevel(level)
    
    # Disable propagation to avoid duplicate logs
    logging.getLogger().propagate = False

class CDPConfigDebugger:
    """Main class for debugging CDP configuration issues."""
    
    def __init__(self, profile: str = "default", debug: bool = False, verbose: bool = False):
        self.profile = profile
        self.debug = debug
        self.verbose = verbose
        self.cdp_home = Path.home() / ".cdp"
        self.credentials_file = self.cdp_home / "credentials"
        self.config_file = self.cdp_home / "config"
        
        setup_logging(debug, verbose)
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"🔍 CDP Configuration Debugger initialized")
        self.logger.info(f"📁 CDP Home: {self.cdp_home}")
        self.logger.info(f"🔑 Credentials file: {self.credentials_file}")
        self.logger.info(f"⚙️  Config file: {self.config_file}")
        self.logger.info(f"👤 Profile: {self.profile}")
    
    def run_full_debug(self) -> Dict:
        """Run complete CDP configuration debugging."""
        self.logger.info("🚀 Starting comprehensive CDP configuration debug")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "profile": self.profile,
            "cdp_home": str(self.cdp_home),
            "checks": {}
        }
        
        # Run all checks
        results["checks"]["environment"] = self.check_environment()
        results["checks"]["file_permissions"] = self.check_file_permissions()
        results["checks"]["cdp_cli"] = self.check_cdp_cli()
        results["checks"]["credentials"] = self.check_credentials()
        results["checks"]["config"] = self.check_config()
        results["checks"]["profile_validation"] = self.validate_profile()
        results["checks"]["shell_vs_python"] = self.compare_shell_vs_python()
        results["checks"]["api_test"] = self.test_cdp_api()
        
        # Generate summary
        results["summary"] = self.generate_summary(results["checks"])
        
        self.logger.info("✅ CDP configuration debug completed")
        return results
    
    def check_environment(self) -> Dict:
        """Check environment variables and system information."""
        self.logger.info("🔍 Checking environment variables and system info")
        
        env_info = {
            "user": os.getenv("USER", "unknown"),
            "home": os.getenv("HOME", "unknown"),
            "path": os.getenv("PATH", "unknown"),
            "python_version": sys.version,
            "python_executable": sys.executable,
            "current_working_directory": os.getcwd(),
            "cdp_region": os.getenv("CDP_REGION", "not_set"),
            "cdp_access_key_id": os.getenv("CDP_ACCESS_KEY_ID", "not_set"),
            "cdp_private_key": os.getenv("CDP_PRIVATE_KEY", "not_set"),
        }
        
        # Check if CDP environment variables are set
        env_info["cdp_env_vars_set"] = {
            "CDP_REGION": bool(env_info["cdp_region"] != "not_set"),
            "CDP_ACCESS_KEY_ID": bool(env_info["cdp_access_key_id"] != "not_set"),
            "CDP_PRIVATE_KEY": bool(env_info["cdp_private_key"] != "not_set"),
        }
        
        self.logger.debug(f"Environment info: {json.dumps(env_info, indent=2)}")
        return env_info
    
    def check_file_permissions(self) -> Dict:
        """Check permissions and ownership of CDP configuration files."""
        self.logger.info("🔐 Checking file permissions and ownership")
        
        permission_info = {
            "cdp_home_exists": self.cdp_home.exists(),
            "cdp_home_permissions": None,
            "credentials_exists": self.credentials_file.exists(),
            "credentials_permissions": None,
            "config_exists": self.config_file.exists(),
            "config_permissions": None,
        }
        
        if self.cdp_home.exists():
            permission_info["cdp_home_permissions"] = self._get_file_permissions(self.cdp_home)
        
        if self.credentials_file.exists():
            permission_info["credentials_permissions"] = self._get_file_permissions(self.credentials_file)
        
        if self.config_file.exists():
            permission_info["config_permissions"] = self._get_file_permissions(self.config_file)
        
        # Check if permissions are secure
        permission_info["security_issues"] = self._check_security_issues(permission_info)
        
        self.logger.debug(f"Permission info: {json.dumps(permission_info, indent=2)}")
        return permission_info
    
    def _get_file_permissions(self, file_path: Path) -> Dict:
        """Get detailed file permissions and ownership information."""
        try:
            stat_info = file_path.stat()
            
            # Get user and group names
            try:
                owner = pwd.getpwuid(stat_info.st_uid).pw_name
            except KeyError:
                owner = f"uid_{stat_info.st_uid}"
            
            try:
                group = grp.getgrgid(stat_info.st_gid).gr_name
            except KeyError:
                group = f"gid_{stat_info.st_gid}"
            
            # Get permission string
            mode = stat_info.st_mode
            perms = ""
            perms += "r" if mode & stat.S_IRUSR else "-"
            perms += "w" if mode & stat.S_IWUSR else "-"
            perms += "x" if mode & stat.S_IXUSR else "-"
            perms += "r" if mode & stat.S_IRGRP else "-"
            perms += "w" if mode & stat.S_IWGRP else "-"
            perms += "x" if mode & stat.S_IXGRP else "-"
            perms += "r" if mode & stat.S_IROTH else "-"
            perms += "w" if mode & stat.S_IWOTH else "-"
            perms += "x" if mode & stat.S_IXOTH else "-"
            
            return {
                "owner": owner,
                "group": group,
                "permissions": perms,
                "mode": oct(mode)[-3:],
                "size": stat_info.st_size,
                "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Error getting permissions for {file_path}: {e}")
            return {"error": str(e)}
    
    def _check_security_issues(self, permission_info: Dict) -> List[str]:
        """Check for security issues in file permissions."""
        issues = []
        
        if not permission_info["cdp_home_exists"]:
            issues.append("CDP home directory does not exist")
            return issues
        
        # Check credentials file permissions
        if permission_info["credentials_exists"]:
            cred_perms = permission_info["credentials_permissions"]
            if cred_perms and "permissions" in cred_perms:
                perms = cred_perms["permissions"]
                if perms[1] == "w" or perms[4] == "w" or perms[7] == "w":
                    issues.append("Credentials file has write permissions for group or others")
                if perms[3] == "r" or perms[6] == "r":
                    issues.append("Credentials file has read permissions for group or others")
        
        # Check config file permissions
        if permission_info["config_exists"]:
            config_perms = permission_info["config_permissions"]
            if config_perms and "permissions" in config_perms:
                perms = config_perms["permissions"]
                if perms[1] == "w" or perms[4] == "w" or perms[7] == "w":
                    issues.append("Config file has write permissions for group or others")
        
        return issues
    
    def check_cdp_cli(self) -> Dict:
        """Check CDP CLI installation and availability."""
        self.logger.info("🔧 Checking CDP CLI installation")
        
        cli_info = {
            "cdp_binary_path": shutil.which("cdp"),
            "cdp_completer_path": shutil.which("cdp_completer"),
            "cdp_version": None,
            "cdp_help": None,
        }
        
        # Get CDP version
        if cli_info["cdp_binary_path"]:
            try:
                result = subprocess.run(
                    ["cdp", "--version"], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                if result.returncode == 0:
                    cli_info["cdp_version"] = result.stdout.strip()
                else:
                    cli_info["cdp_version"] = f"Error: {result.stderr.strip()}"
            except subprocess.TimeoutExpired:
                cli_info["cdp_version"] = "Timeout getting version"
            except Exception as e:
                cli_info["cdp_version"] = f"Exception: {e}"
        
        # Test basic CDP help
        if cli_info["cdp_binary_path"]:
            try:
                result = subprocess.run(
                    ["cdp", "--help"], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                if result.returncode == 0:
                    cli_info["cdp_help"] = "Available"
                else:
                    cli_info["cdp_help"] = f"Error: {result.stderr.strip()}"
            except subprocess.TimeoutExpired:
                cli_info["cdp_help"] = "Timeout getting help"
            except Exception as e:
                cli_info["cdp_help"] = f"Exception: {e}"
        
        self.logger.debug(f"CLI info: {json.dumps(cli_info, indent=2)}")
        return cli_info
    
    def check_credentials(self) -> Dict:
        """Check CDP credentials file content and structure."""
        self.logger.info("🔑 Checking CDP credentials file")
        
        cred_info = {
            "file_exists": self.credentials_file.exists(),
            "file_size": None,
            "profiles": [],
            "profile_details": {},
            "parsing_errors": [],
        }
        
        if not cred_info["file_exists"]:
            self.logger.warning("Credentials file does not exist")
            return cred_info
        
        try:
            cred_info["file_size"] = self.credentials_file.stat().st_size
            
            # Read and parse credentials file
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
                            masked_value = value[:4] + "*" * (len(value) - 8) + value[-4:] if len(value) > 8 else "***"
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
            
        except configparser.Error as e:
            cred_info["parsing_errors"].append(f"ConfigParser error: {e}")
        except Exception as e:
            cred_info["parsing_errors"].append(f"Unexpected error: {e}")
        
        self.logger.debug(f"Credentials info: {json.dumps(cred_info, indent=2)}")
        return cred_info
    
    def check_config(self) -> Dict:
        """Check CDP config file content and structure."""
        self.logger.info("⚙️  Checking CDP config file")
        
        config_info = {
            "file_exists": self.config_file.exists(),
            "file_size": None,
            "sections": [],
            "section_details": {},
            "parsing_errors": [],
        }
        
        if not config_info["file_exists"]:
            self.logger.warning("Config file does not exist")
            return config_info
        
        try:
            config_info["file_size"] = self.config_file.stat().st_size
            
            # Read and parse config file
            config = configparser.ConfigParser()
            config.read(self.config_file)
            
            # Get all sections
            config_info["sections"] = config.sections()
            
            # Get details for each section
            for section in config.sections():
                config_info["section_details"][section] = dict(config[section])
            
        except configparser.Error as e:
            config_info["parsing_errors"].append(f"ConfigParser error: {e}")
        except Exception as e:
            config_info["parsing_errors"].append(f"Unexpected error: {e}")
        
        self.logger.debug(f"Config info: {json.dumps(config_info, indent=2)}")
        return config_info
    
    def validate_profile(self) -> Dict:
        """Validate the specified CDP profile."""
        self.logger.info(f"✅ Validating CDP profile: {self.profile}")
        
        validation_info = {
            "profile": self.profile,
            "profile_exists": False,
            "cdp_iam_test": None,
            "cdp_account_test": None,
            "error_details": [],
        }
        
        # Check if profile exists in credentials
        if self.credentials_file.exists():
            try:
                config = configparser.ConfigParser()
                config.read(self.credentials_file)
                validation_info["profile_exists"] = self.profile in config.sections()
            except Exception as e:
                validation_info["error_details"].append(f"Error checking profile existence: {e}")
        
        # Test CDP IAM get-user command
        try:
            result = subprocess.run(
                ["cdp", "--profile", self.profile, "iam", "get-user"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                validation_info["cdp_iam_test"] = "SUCCESS"
                try:
                    user_data = json.loads(result.stdout)
                    validation_info["user_info"] = {
                        "crn": user_data.get("user", {}).get("crn", "unknown"),
                        "email": user_data.get("user", {}).get("email", "unknown"),
                        "workloadUsername": user_data.get("user", {}).get("workloadUsername", "unknown"),
                    }
                except json.JSONDecodeError:
                    validation_info["user_info"] = {"raw_output": result.stdout[:200] + "..."}
            else:
                validation_info["cdp_iam_test"] = "FAILED"
                validation_info["error_details"].append(f"IAM get-user failed: {result.stderr.strip()}")
        except subprocess.TimeoutExpired:
            validation_info["cdp_iam_test"] = "TIMEOUT"
            validation_info["error_details"].append("IAM get-user command timed out")
        except Exception as e:
            validation_info["cdp_iam_test"] = "ERROR"
            validation_info["error_details"].append(f"IAM get-user exception: {e}")
        
        # Test CDP IAM get-account command
        try:
            result = subprocess.run(
                ["cdp", "--profile", self.profile, "iam", "get-account"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                validation_info["cdp_account_test"] = "SUCCESS"
                try:
                    account_data = json.loads(result.stdout)
                    validation_info["account_info"] = {
                        "crn": account_data.get("account", {}).get("crn", "unknown"),
                        "accountId": account_data.get("account", {}).get("accountId", "unknown"),
                        "displayName": account_data.get("account", {}).get("displayName", "unknown"),
                    }
                except json.JSONDecodeError:
                    validation_info["account_info"] = {"raw_output": result.stdout[:200] + "..."}
            else:
                validation_info["cdp_account_test"] = "FAILED"
                validation_info["error_details"].append(f"IAM get-account failed: {result.stderr.strip()}")
        except subprocess.TimeoutExpired:
            validation_info["cdp_account_test"] = "TIMEOUT"
            validation_info["error_details"].append("IAM get-account command timed out")
        except Exception as e:
            validation_info["cdp_account_test"] = "ERROR"
            validation_info["error_details"].append(f"IAM get-account exception: {e}")
        
        self.logger.debug(f"Profile validation: {json.dumps(validation_info, indent=2)}")
        return validation_info
    
    def compare_shell_vs_python(self) -> Dict:
        """Compare CDP behavior between shell and Python execution."""
        self.logger.info("🔄 Comparing shell vs Python CDP execution")
        
        comparison_info = {
            "shell_command": None,
            "python_command": None,
            "shell_result": None,
            "python_result": None,
            "differences": [],
        }
        
        # Test command to run
        test_command = ["cdp", "--profile", self.profile, "iam", "get-user"]
        comparison_info["shell_command"] = " ".join(test_command)
        comparison_info["python_command"] = str(test_command)
        
        # Run in shell
        try:
            shell_result = subprocess.run(
                test_command,
                capture_output=True,
                text=True,
                timeout=30,
                env=os.environ.copy()  # Use current environment
            )
            comparison_info["shell_result"] = {
                "returncode": shell_result.returncode,
                "stdout": shell_result.stdout.strip(),
                "stderr": shell_result.stderr.strip(),
            }
        except Exception as e:
            comparison_info["shell_result"] = {"error": str(e)}
        
        # Run in Python (simulated)
        try:
            # Create a new environment with explicit Python path
            python_env = os.environ.copy()
            python_env["PYTHONPATH"] = os.getcwd()
            
            python_result = subprocess.run(
                test_command,
                capture_output=True,
                text=True,
                timeout=30,
                env=python_env
            )
            comparison_info["python_result"] = {
                "returncode": python_result.returncode,
                "stdout": python_result.stdout.strip(),
                "stderr": python_result.stderr.strip(),
            }
        except Exception as e:
            comparison_info["python_result"] = {"error": str(e)}
        
        # Compare results
        if (comparison_info["shell_result"] and 
            comparison_info["python_result"] and
            "error" not in comparison_info["shell_result"] and
            "error" not in comparison_info["python_result"]):
            
            shell_rc = comparison_info["shell_result"]["returncode"]
            python_rc = comparison_info["python_result"]["returncode"]
            
            if shell_rc != python_rc:
                comparison_info["differences"].append(f"Return codes differ: shell={shell_rc}, python={python_rc}")
            
            if comparison_info["shell_result"]["stdout"] != comparison_info["python_result"]["stdout"]:
                comparison_info["differences"].append("STDOUT differs between shell and Python")
            
            if comparison_info["shell_result"]["stderr"] != comparison_info["python_result"]["stderr"]:
                comparison_info["differences"].append("STDERR differs between shell and Python")
        
        self.logger.debug(f"Shell vs Python comparison: {json.dumps(comparison_info, indent=2)}")
        return comparison_info
    
    def test_cdp_api(self) -> Dict:
        """Test various CDP API endpoints."""
        self.logger.info("🌐 Testing CDP API endpoints")
        
        api_tests = {
            "environments_list": None,
            "datalake_list": None,
            "datahub_list": None,
            "errors": [],
        }
        
        # Test environments list
        try:
            result = subprocess.run(
                ["cdp", "--profile", self.profile, "environments", "list-environments"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                try:
                    env_data = json.loads(result.stdout)
                    api_tests["environments_list"] = {
                        "status": "SUCCESS",
                        "count": len(env_data.get("environments", [])),
                        "environments": [env.get("environmentName", "unknown") for env in env_data.get("environments", [])]
                    }
                except json.JSONDecodeError:
                    api_tests["environments_list"] = {"status": "SUCCESS", "raw_output": result.stdout[:200] + "..."}
            else:
                api_tests["environments_list"] = {"status": "FAILED", "error": result.stderr.strip()}
        except Exception as e:
            api_tests["environments_list"] = {"status": "ERROR", "error": str(e)}
        
        # Test datalake list (if environments exist)
        if (api_tests["environments_list"] and 
            api_tests["environments_list"]["status"] == "SUCCESS" and
            api_tests["environments_list"]["count"] > 0):
            
            try:
                env_name = api_tests["environments_list"]["environments"][0]
                result = subprocess.run(
                    ["cdp", "--profile", self.profile, "datalake", "list-datalakes", "--environment-name", env_name],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    try:
                        dl_data = json.loads(result.stdout)
                        api_tests["datalake_list"] = {
                            "status": "SUCCESS",
                            "environment": env_name,
                            "count": len(dl_data.get("datalakes", [])),
                            "datalakes": [dl.get("datalakeName", "unknown") for dl in dl_data.get("datalakes", [])]
                        }
                    except json.JSONDecodeError:
                        api_tests["datalake_list"] = {"status": "SUCCESS", "raw_output": result.stdout[:200] + "..."}
                else:
                    api_tests["datalake_list"] = {"status": "FAILED", "error": result.stderr.strip()}
            except Exception as e:
                api_tests["datalake_list"] = {"status": "ERROR", "error": str(e)}
        
        self.logger.debug(f"API tests: {json.dumps(api_tests, indent=2)}")
        return api_tests
    
    def generate_summary(self, checks: Dict) -> Dict:
        """Generate a summary of all checks."""
        self.logger.info("📊 Generating debug summary")
        
        summary = {
            "overall_status": "UNKNOWN",
            "critical_issues": [],
            "warnings": [],
            "recommendations": [],
            "passed_checks": 0,
            "failed_checks": 0,
            "total_checks": 0,
        }
        
        # Analyze each check
        for check_name, check_result in checks.items():
            summary["total_checks"] += 1
            
            if check_name == "environment":
                # Check environment variables
                env_vars = check_result.get("cdp_env_vars_set", {})
                if not any(env_vars.values()):
                    summary["warnings"].append("No CDP environment variables are set")
                else:
                    summary["passed_checks"] += 1
            
            elif check_name == "file_permissions":
                # Check file permissions
                if not check_result.get("cdp_home_exists", False):
                    summary["critical_issues"].append("CDP home directory does not exist")
                    summary["failed_checks"] += 1
                elif check_result.get("security_issues"):
                    summary["warnings"].extend(check_result["security_issues"])
                    summary["failed_checks"] += 1
                else:
                    summary["passed_checks"] += 1
            
            elif check_name == "cdp_cli":
                # Check CDP CLI
                if not check_result.get("cdp_binary_path"):
                    summary["critical_issues"].append("CDP CLI is not installed or not in PATH")
                    summary["failed_checks"] += 1
                elif check_result.get("cdp_help") != "Available":
                    summary["critical_issues"].append("CDP CLI is not working properly")
                    summary["failed_checks"] += 1
                else:
                    summary["passed_checks"] += 1
            
            elif check_name == "credentials":
                # Check credentials
                if not check_result.get("file_exists", False):
                    summary["critical_issues"].append("CDP credentials file does not exist")
                    summary["failed_checks"] += 1
                elif check_result.get("parsing_errors"):
                    summary["critical_issues"].extend(check_result["parsing_errors"])
                    summary["failed_checks"] += 1
                elif self.profile not in check_result.get("profiles", []):
                    summary["critical_issues"].append(f"Profile '{self.profile}' not found in credentials file")
                    summary["failed_checks"] += 1
                else:
                    summary["passed_checks"] += 1
            
            elif check_name == "profile_validation":
                # Check profile validation
                if not check_result.get("profile_exists", False):
                    summary["critical_issues"].append(f"Profile '{self.profile}' does not exist")
                    summary["failed_checks"] += 1
                elif check_result.get("cdp_iam_test") != "SUCCESS":
                    summary["critical_issues"].append(f"Profile validation failed: {check_result.get('cdp_iam_test', 'UNKNOWN')}")
                    summary["failed_checks"] += 1
                else:
                    summary["passed_checks"] += 1
        
        # Determine overall status
        if summary["critical_issues"]:
            summary["overall_status"] = "CRITICAL"
        elif summary["warnings"]:
            summary["overall_status"] = "WARNING"
        elif summary["passed_checks"] == summary["total_checks"]:
            summary["overall_status"] = "HEALTHY"
        else:
            summary["overall_status"] = "ISSUES"
        
        # Generate recommendations
        if summary["overall_status"] == "CRITICAL":
            summary["recommendations"].append("Fix critical issues before proceeding")
        if summary["overall_status"] == "WARNING":
            summary["recommendations"].append("Review warnings and consider addressing them")
        if not checks.get("cdp_cli", {}).get("cdp_binary_path"):
            summary["recommendations"].append("Install CDP CLI: pip install cdpcli")
        if not checks.get("credentials", {}).get("file_exists"):
            summary["recommendations"].append("Run 'cdp configure' to set up credentials")
        
        self.logger.debug(f"Summary: {json.dumps(summary, indent=2)}")
        return summary
    
    def print_results(self, results: Dict) -> None:
        """Print formatted results to console."""
        print("\n" + "="*80)
        print("🔍 CDP CONFIGURATION DEBUG RESULTS")
        print("="*80)
        
        # Print summary
        summary = results["summary"]
        status_emoji = {
            "HEALTHY": "✅",
            "WARNING": "⚠️",
            "ISSUES": "❌",
            "CRITICAL": "🚨",
            "UNKNOWN": "❓"
        }
        
        print(f"\n📊 OVERALL STATUS: {status_emoji.get(summary['overall_status'], '❓')} {summary['overall_status']}")
        print(f"📈 Checks Passed: {summary['passed_checks']}/{summary['total_checks']}")
        
        if summary["critical_issues"]:
            print(f"\n🚨 CRITICAL ISSUES:")
            for issue in summary["critical_issues"]:
                print(f"   • {issue}")
        
        if summary["warnings"]:
            print(f"\n⚠️  WARNINGS:")
            for warning in summary["warnings"]:
                print(f"   • {warning}")
        
        if summary["recommendations"]:
            print(f"\n💡 RECOMMENDATIONS:")
            for rec in summary["recommendations"]:
                print(f"   • {rec}")
        
        # Print detailed results if verbose or debug
        if self.verbose or self.debug:
            print(f"\n🔍 DETAILED RESULTS:")
            
            for check_name, check_result in results["checks"].items():
                print(f"\n--- {check_name.upper()} ---")
                if isinstance(check_result, dict):
                    for key, value in check_result.items():
                        if isinstance(value, dict):
                            print(f"  {key}:")
                            for sub_key, sub_value in value.items():
                                print(f"    {sub_key}: {sub_value}")
                        else:
                            print(f"  {key}: {value}")
                else:
                    print(f"  {check_result}")
        
        print("\n" + "="*80)

def main():
    """Main function to run the CDP configuration debugger."""
    parser = argparse.ArgumentParser(
        description="Debug CDP configuration issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cdp_config_debugger.py
  python cdp_config_debugger.py --profile my-profile
  python cdp_config_debugger.py --debug --verbose
  python cdp_config_debugger.py --profile default --debug
        """
    )
    
    parser.add_argument(
        "--profile",
        default="default",
        help="CDP profile to debug (default: default)"
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
    
    # Create debugger instance
    debugger = CDPConfigDebugger(
        profile=args.profile,
        debug=args.debug,
        verbose=args.verbose
    )
    
    try:
        # Run full debug
        results = debugger.run_full_debug()
        
        # Print results
        debugger.print_results(results)
        
        # Save to file if requested
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n💾 Results saved to: {output_path}")
        
        # Exit with appropriate code
        summary = results["summary"]
        if summary["overall_status"] in ["CRITICAL", "ISSUES"]:
            sys.exit(1)
        elif summary["overall_status"] == "WARNING":
            sys.exit(2)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Debug interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 