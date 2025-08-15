# FreeIPA Status Functions - Comprehensive Health Check Suite

A professional-grade FreeIPA infrastructure monitoring and health validation toolkit for Cloudera environments.

## 🚀 **Latest Version 2.0.0 Features**

### **✨ New Comprehensive Health Check**

- **One-Command Execution**: Run all health checks with `freeipa_comprehensive_health_check`
- **Progress Tracking**: Real-time progress bars and spinners for long-running operations
- **Professional Output**: Beautiful UI with box-drawing characters and color-coded results
- **Execution Timing**: Tracks and displays total execution time
- **Enhanced Logging**: Timestamped, structured logging with multiple levels

### **🔧 Enhanced Functionality**

- **8 Comprehensive Health Checks**: Services, backups, replication, LDAP conflicts, DNS validation
- **Smart Progress Indicators**: Spinners for Salt operations, LDAP queries, and DNS checks
- **Improved Error Handling**: Proper return codes and error propagation
- **Backward Compatibility**: All legacy functions maintained as wrappers

### **🎯 Enhanced Runner Script**

- **Command-Line Options**: Flexible execution with various flags and parameters
- **Single Check Execution**: Run individual health checks as needed
- **Logging Support**: Optional file logging with timestamps and structured output
- **Environment Validation**: Automatic prerequisite checking and validation
- **Dry-Run Mode**: Preview execution without running actual checks

---

## 📋 **Quick Start**

### **Option 1: Enhanced Runner Script (Recommended)**

```bash
# Run comprehensive health check
./freeipa/misc/run_freeipa_health_check.sh

# Run with logging enabled
./freeipa/misc/run_freeipa_health_check.sh -l

# Run specific health check only
./freeipa/misc/run_freeipa_health_check.sh -c freeipa_status_check

# Verbose mode with logging
./freeipa/misc/run_freeipa_health_check.sh -v -l
```

### **Option 2: Direct Function Source**

```bash
# Source the functions
source freeipa/misc/freeipa_status_functions.sh

# Run comprehensive health check
freeipa_comprehensive_health_check
```

### **Option 3: Individual Health Checks**

```bash
# Source the functions
source freeipa/misc/freeipa_status_functions.sh

# Run specific checks
freeipa_status_check          # Services status
freeipa_backup_check          # Cloud backups
freeipa_cipa_check            # Replication consistency
freeipa_ldap_conflicts_check  # LDAP conflicts
freeipa_replication_agreements_check  # Replication agreements
freeipa_groups_consistency_check      # Group consistency
freeipa_users_consistency_check       # User consistency
freeipa_dns_duplicates_check          # DNS duplicates
```

---

## 🎮 **Runner Script Usage**

### **Command-Line Options**

```bash
./run_freeipa_health_check.sh [OPTIONS]

Options:
  -h, --help          Show help message
  -v, --verbose       Enable verbose output
  -l, --log           Enable logging to file
  -q, --quiet         Suppress progress indicators
  -t, --target        Specify Salt target (default: all nodes)
  -c, --check         Run specific health check only
  -n, --dry-run       Show what would be executed without running
```

### **Usage Examples**

```bash
# Basic comprehensive health check
./run_freeipa_health_check.sh

# Verbose mode with file logging
./run_freeipa_health_check.sh -v -l

# Run only services status check
./run_freeipa_health_check.sh -c freeipa_status_check

# Dry run to see what would be executed
./run_freeipa_health_check.sh -n

# Target specific nodes only
./run_freeipa_health_check.sh -t "*master*"

# Quiet mode (suppress progress indicators)
./run_freeipa_health_check.sh -q
```

### **Available Health Checks for -c Option**

```bash
freeipa_status_check               # Services status
freeipa_backup_check               # Cloud backups
freeipa_cipa_check                 # Replication consistency
freeipa_ldap_conflicts_check       # LDAP conflicts
freeipa_replication_agreements_check # Replication agreements
freeipa_groups_consistency_check   # Group consistency
freeipa_users_consistency_check    # User consistency
freeipa_dns_duplicates_check       # DNS duplicates
```

### **Exit Codes**

- **0**: All health checks passed
- **1**: One or more health checks failed
- **2**: Script execution error
- **3**: Invalid arguments or configuration

---

## 🎯 **Health Check Coverage**

The comprehensive health check validates:

| Check  | Description             | Status                                 |
| ------ | ----------------------- | -------------------------------------- |
| **01** | FreeIPA Services Status | All services running across nodes      |
| **02** | Cloud Backups           | Backup functionality and latest status |
| **03** | Replication CIPA State  | Consistency across FreeIPA servers     |
| **04** | LDAP Conflicts          | User/group/host conflict detection     |
| **05** | Replication Agreements  | Status between IPA servers             |
| **06** | Group Consistency       | MD5 verification across nodes          |
| **07** | User Consistency        | MD5 verification across nodes          |
| **08** | DNS Duplicates          | Forward and reverse DNS validation     |

---

## 🛠️ **Dependencies**

### **Required Tools**

- `salt` (SaltStack client)
- `jq` (JSON processor)
- `ipa` (FreeIPA client tools)
- `cipa` (FreeIPA consistency checker)
- `ldapsearch` (LDAP client tools)
- `host` (DNS lookup tool)

### **Required Environment**

- `activate_salt_env` script in PATH
- Root or sudo access for FreeIPA operations
- Valid FreeIPA credentials in `/srv/pillar/freeipa/init.sls`

---

## 📖 **Usage Examples**

### **Comprehensive Health Check**

```bash
# Source the functions
source freeipa/misc/freeipa_status_functions.sh

# Run all health checks at once
freeipa_comprehensive_health_check
```

### **Individual Health Checks**

```bash
# Check specific components
freeipa_status_check                    # Services status
freeipa_backup_check                    # Backup functionality
freeipa_cipa_check                      # Replication state
freeipa_ldap_conflicts_check            # LDAP conflicts
freeipa_replication_agreements_check    # Replication health
freeipa_groups_consistency_check        # Group consistency
freeipa_users_consistency_check         # User consistency
freeipa_dns_duplicates_check            # DNS validation
```

### **Legacy Function Support**

```bash
# Legacy function names still work
freeipa_status                          # Wrapper for freeipa_status_check
freeipa_test_backup                     # Wrapper for freeipa_backup_check
freeipa_cipa_state                      # Wrapper for freeipa_cipa_check
```

---

## 🔍 **Advanced Features**

### **Progress Indicators**

- **Spinners**: Unicode spinner characters for long-running operations
- **Progress Bars**: Visual completion percentage for health checks
- **Real-time Updates**: Live feedback during execution

### **Enhanced Logging**

- **Structured Logs**: Timestamped entries with log levels
- **Color Coding**: Consistent color scheme for different message types
- **Log Levels**: INFO, SUCCESS, WARNING, ERROR
- **File Logging**: Optional logging to `/var/log/freeipa_health_check/`

### **Professional Output**

- **Beautiful UI**: Box-drawing characters and professional formatting
- **Color-coded Results**: Green for pass, red for fail, yellow for warnings
- **Comprehensive Summary**: Statistics and execution time tracking

### **Runner Script Features**

- **Environment Validation**: Automatic prerequisite checking
- **Flexible Execution**: Single checks or comprehensive runs
- **Dry-Run Mode**: Preview execution without running
- **Target Specification**: Customize Salt targets
- **Verbose Output**: Detailed execution information

---

## 📁 **File Structure**

```
freeipa/misc/
├── freeipa_status_functions.sh     # Main functions file
├── run_freeipa_health_check.sh     # Enhanced runner script
└── README.md                       # This documentation
```

---

## 🚀 **Installation & Setup**

### **Option 1: Enhanced Runner Script (Recommended)**

```bash
# Make executable
chmod +x freeipa/misc/run_freeipa_health_check.sh

# Run comprehensive health check
./freeipa/misc/run_freeipa_health_check.sh

# Run with options
./freeipa/misc/run_freeipa_health_check.sh -v -l
```

### **Option 2: Direct Source**

```bash
# Source directly from the repository
source freeipa/misc/freeipa_status_functions.sh

# Run health checks
freeipa_comprehensive_health_check
```

### **Option 3: Copy to Home Directory**

```bash
# Copy to home directory
cp freeipa/misc/freeipa_status_functions.sh ~/.freeipa_status_functions.sh

# Add to bashrc
echo "source ~/.freeipa_status_functions.sh" >> ~/.bashrc

# Reload profile
source ~/.bashrc

# List available functions
awk '/^function/ {print $2}' ~/.freeipa_status_functions.sh

# Execute health checks
freeipa_comprehensive_health_check
```

---

## 🔧 **Configuration**

### **Color Customization**

The script automatically detects if color variables are defined. To customize colors:

```bash
# Define custom colors before sourcing
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export CYAN='\033[0;36m'
export PURPLE='\033[0;35m'
export NC='\033[0m'

# Source the functions
source freeipa/misc/freeipa_status_functions.sh
```

### **Logging Configuration**

The runner script supports automatic logging:

```bash
# Enable logging
./run_freeipa_health_check.sh -l

# Logs are saved to
/var/log/freeipa_health_check/health_check_YYYYMMDD_HHMMSS.log
```

---

## 📊 **Output Examples**

### **Comprehensive Health Check Output**

```
╔══════════════════════════════════════════════════════════════╗
║              FreeIPA Comprehensive Health Check              ║
╚══════════════════════════════════════════════════════════════╝

[2024-01-15 10:30:00] INFO: Health check started at 2024-01-15 10:30:00

[██████████████████████████████████████████████████] 100% Checking FreeIPA Services Status
Expected services are running [PASS]

[██████████████████████████████████████████████████] 100% Checking FreeIPA Cloud Backups
FreeIPA Cloud Backups [PASS]

...

╔══════════════════════════════════════════════════════════════╗
║                    Health Check Summary                      ║
╚══════════════════════════════════════════════════════════════╝
Total Checks: 8
Passed: 8
Failed: 0
Execution Time: 45 seconds

🎉 Overall Status: HEALTHY
[2024-01-15 10:30:45] SUCCESS: All health checks completed successfully
```

### **Runner Script Output**

```
╔══════════════════════════════════════════════════════════════╗
║              FreeIPA Health Check Runner v2.0.0              ║
╚══════════════════════════════════════════════════════════════╝

[2024-01-15 10:30:00] INFO: Validating environment and prerequisites...
[2024-01-15 10:30:00] INFO: Sourcing FreeIPA status functions...
[2024-01-15 10:30:00] INFO: Configuration:
[2024-01-15 10:30:00] INFO:   Verbose Mode: false
[2024-01-15 10:30:00] INFO:   Logging: true
[2024-01-15 10:30:00] INFO:   Quiet Mode: false
[2024-01-15 10:30:00] INFO:   Dry Run: false
[2024-01-15 10:30:00] INFO:   Salt Target: *
[2024-01-15 10:30:00] INFO: Starting comprehensive FreeIPA health check...

[Comprehensive health check output follows...]
```

---

## 🐛 **Troubleshooting**

### **Common Issues**

#### **Permission Denied**

```bash
# Ensure you're running as root or have sudo access
sudo -i
./run_freeipa_health_check.sh
```

#### **Salt Connection Issues**

```bash
# Verify Salt environment is activated
which salt
salt '*' test.ping

# Use the runner script for automatic validation
./run_freeipa_health_check.sh -n
```

#### **FreeIPA Authentication**

```bash
# Check credentials file exists
ls -la /srv/pillar/freeipa/init.sls

# Verify admin user can authenticate
kinit admin
```

#### **Missing Functions**

```bash
# Check if functions file is properly sourced
declare -f freeipa_comprehensive_health_check

# Verify file exists and is readable
ls -la freeipa/misc/freeipa_status_functions.sh
```

---

## 📝 **Changelog**

### **Version 2.0.0 (Current)**

- ✨ Added comprehensive health check function
- 🎯 Implemented progress bars and spinners
- 📊 Enhanced logging with timestamps and levels
- 🎨 Professional UI with box-drawing characters
- 🔧 Improved error handling and return codes
- 📚 Enhanced documentation and usage examples
- 🧹 Cleaned up commented code and unused functions
- 🚀 Enhanced runner script with command-line options
- 📝 Added file logging and environment validation
- 🎮 Single check execution and dry-run mode

### **Version 1.x (Legacy)**

- Basic health check functions
- Individual component validation
- Salt-based remote execution

---

## ⚠️ **Disclaimer**

This script is provided as-is for FreeIPA infrastructure monitoring in Cloudera environments. Always test in a non-production environment before use in production.
