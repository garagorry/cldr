# CDP Configuration Debugging Tools

This repository contains comprehensive Python scripts to debug CDP (Cloudera Data Platform) configuration issues. These tools help identify why CDP configurations might work from the shell but fail when called from Python code.

## 📋 Overview

The debugging tools consist of two main scripts:

1. **`cdp_config_debugger.py`** - Comprehensive CDP configuration debugger
2. **`cdp_permissions_checker.py`** - Specialized permissions checker using `namei -l`

## 🚀 Quick Start

### Basic Usage

```bash
# Run comprehensive CDP configuration debug
python cdp_config_debugger.py

# Check permissions specifically
python cdp_permissions_checker.py

# Debug with verbose output
python cdp_config_debugger.py --debug --verbose

# Check specific profile
python cdp_config_debugger.py --profile my-profile --debug
```

### Advanced Usage

```bash
# Save results to JSON file
python cdp_config_debugger.py --debug --output debug_results.json

# Check permissions and save results
python cdp_permissions_checker.py --verbose --output permissions_results.json

# Debug with specific profile and save logs
python cdp_config_debugger.py --profile production --debug --output production_debug.json
```

## 🔧 Features

### CDP Configuration Debugger (`cdp_config_debugger.py`)

#### Comprehensive Checks:

- ✅ **Environment Variables** - Check CDP environment variables
- ✅ **File Permissions** - Validate file ownership and permissions
- ✅ **CDP CLI Installation** - Verify CDP CLI availability and version
- ✅ **Credentials Validation** - Check credentials file structure and content
- ✅ **Config File Analysis** - Validate CDP config file
- ✅ **Profile Validation** - Test CDP profile functionality
- ✅ **Shell vs Python Comparison** - Compare behavior differences
- ✅ **API Testing** - Test CDP API endpoints

#### Security Features:

- 🔒 **Sensitive Data Masking** - Automatically masks access keys and private keys
- 🔒 **Permission Analysis** - Identifies insecure file permissions
- 🔒 **Security Recommendations** - Provides specific security fixes

#### Debugging Features:

- 📝 **Comprehensive Logging** - Detailed debug logs saved to files
- 📊 **Structured Output** - JSON results for programmatic analysis
- 🎯 **Exit Codes** - Proper exit codes for automation
- 📈 **Progress Tracking** - Real-time progress indicators

### CDP Permissions Checker (`cdp_permissions_checker.py`)

#### Specialized Features:

- 🔍 **namei -l Integration** - Uses `namei -l` command for detailed permission analysis
- 🔍 **Fallback Support** - Uses `ls -la` when `namei` is not available
- 🔍 **Path Traversal** - Checks entire path hierarchy for permission issues
- 🔍 **Symbolic Link Detection** - Identifies potential security risks

#### Permission Analysis:

- 📁 **Directory Permissions** - Check `.cdp` directory permissions
- 🔑 **Credentials File** - Validate `~/.cdp/credentials` permissions
- ⚙️ **Config File** - Validate `~/.cdp/config` permissions
- 🔗 **Symbolic Links** - Detect and warn about symbolic links

## 📊 Output Examples

### Summary Output

```
================================================================================
🔍 CDP CONFIGURATION DEBUG RESULTS
================================================================================

📊 OVERALL STATUS: ✅ HEALTHY
📈 Checks Passed: 8/8

✅ Secure files: credentials, config, cdp_home

🔑 CREDENTIALS PROFILES:
  Available profiles: default, production, staging
```

### Detailed Debug Output (with --verbose)

```
🔍 DETAILED RESULTS:

--- ENVIRONMENT ---
  user: jgaragorry
  home: /home/jgaragorry
  python_version: 3.9.5 (default, May 4 2021, 00:00:00)
  python_executable: /usr/bin/python3
  cdp_region: not_set
  cdp_access_key_id: not_set
  cdp_private_key: not_set

--- FILE_PERMISSIONS ---
  cdp_home_exists: True
  cdp_home_permissions:
    owner: jgaragorry
    group: jgaragorry
    permissions: rwxr-xr-x
    mode: 755
    size: 4096
    modified: 2024-01-15T10:30:00
```

## 🔍 Common Issues and Solutions

### Issue 1: CDP CLI Not Found

**Symptoms:** `cdp_binary_path: None`
**Solution:**

```bash
# Install CDP CLI
pip install cdpcli

# Verify installation
cdp --version
```

### Issue 2: Credentials File Missing

**Symptoms:** `CDP credentials file does not exist`
**Solution:**

```bash
# Configure CDP credentials
cdp configure

# Or manually create credentials file
mkdir -p ~/.cdp
touch ~/.cdp/credentials
```

### Issue 3: Insecure File Permissions

**Symptoms:** `World read permissions on ~/.cdp/credentials`
**Solution:**

```bash
# Fix permissions
chmod 600 ~/.cdp/credentials
chmod 700 ~/.cdp
chown $USER:$USER ~/.cdp ~/.cdp/credentials
```

### Issue 4: Profile Not Found

**Symptoms:** `Profile 'my-profile' not found in credentials file`
**Solution:**

```bash
# List available profiles
cdp configure list

# Create new profile
cdp configure --profile my-profile
```

### Issue 5: Authentication Failures

**Symptoms:** `IAM get-user failed: Invalid credentials`
**Solution:**

```bash
# Regenerate access keys in CDP Management Console
# Update credentials file
cdp configure --profile default
```

## 🛠️ Troubleshooting Guide

### Debug Mode

Enable debug mode for maximum information:

```bash
python cdp_config_debugger.py --debug --verbose
```

This will:

- Save detailed logs to `/tmp/cdp_debug_logs/`
- Show all internal operations
- Provide step-by-step debugging information

### Permission Issues

If you suspect permission problems:

```bash
# Check permissions with namei
python cdp_permissions_checker.py --debug

# Manual permission check
namei -l ~/.cdp/credentials ~/.cdp/config
ls -la ~/.cdp/
```

### Environment Differences

To compare shell vs Python behavior:

```bash
# Run debugger with shell comparison
python cdp_config_debugger.py --debug

# Check the "shell_vs_python" section in output
```

### Profile Issues

To debug specific profile problems:

```bash
# Test specific profile
python cdp_config_debugger.py --profile problematic-profile --debug

# Check profile in credentials file
grep -A 5 "\[problematic-profile\]" ~/.cdp/credentials
```

## 📝 Log Files

When using `--debug` flag, logs are saved to:

- **Debug Logs:** `/tmp/cdp_debug_logs/cdp_debug_YYYYMMDD_HHMMSS.log`
- **Permissions Logs:** `/tmp/cdp_debug_logs/cdp_permissions_YYYYMMDD_HHMMSS.log`

### Log Format

```
2024-01-15 10:30:00,123 - INFO - run_full_debug:45 - 🚀 Starting comprehensive CDP configuration debug
2024-01-15 10:30:00,124 - DEBUG - check_environment:67 - Environment info: {"user": "jgaragorry", ...}
2024-01-15 10:30:00,125 - INFO - check_file_permissions:75 - 🔐 Checking file permissions and ownership
```

## 🔒 Security Considerations

### Sensitive Data Protection

- Access keys and private keys are automatically masked in output
- Log files do not contain sensitive credentials
- Use `--output` flag carefully in shared environments

### File Permissions

- Credentials file should have 600 permissions
- CDP directory should have 700 permissions
- Files should be owned by the current user

### Best Practices

```bash
# Set secure permissions
chmod 600 ~/.cdp/credentials
chmod 700 ~/.cdp
chown $USER:$USER ~/.cdp ~/.cdp/credentials

# Verify permissions
ls -la ~/.cdp/
```

## 📋 Exit Codes

The scripts use the following exit codes:

- **0** - Success (HEALTHY status)
- **1** - Critical issues found
- **2** - Warnings found
- **130** - Interrupted by user (Ctrl+C)

## 📚 References

- [CDP CLI Documentation](https://docs.cloudera.com/cdp-public-cloud/cloud/cli/topics/mc-installing-cdp-client.html)
