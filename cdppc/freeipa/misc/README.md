# FreeIPA Health Check Suite v2.1.0

FreeIPA infrastructure monitoring for Cloudera CDP environments.

**Quick Start**: `./run_freeipa_health_check.sh`

## Features

- **Comprehensive Health Checks**: FreeIPA core, CDP services, network, resources, security
- **One-Command Execution**: Run all checks or individual tests
- **Resource Monitoring**: Disk, memory, CPU with configurable thresholds
- **Network Validation**: Local ports + inter-node connectivity + Salt master
- **Auto-Remediation**: Auto-install dependencies, auto-activate Salt environment
- **Progress Tracking**: Real-time progress bars and spinners
- **Professional Output**: Color-coded results with detailed reporting

---

## Quick Start

```bash
# Run all 19 health checks
./run_freeipa_health_check.sh

# With logging
./run_freeipa_health_check.sh -l

# Specific check only
./run_freeipa_health_check.sh -c freeipa_cdp_services_check

# Custom thresholds
source freeipa_status_functions.sh
freeipa_disk_check 75      # 75% threshold
freeipa_memory_check 2048  # 2GB threshold
```

---

## Command-Line Options

```bash
./run_freeipa_health_check.sh [OPTIONS]

-h, --help     Show help
-l, --log      Enable logging
-c, --check    Run specific check only
-v, --verbose  Verbose output
-n, --dry-run  Preview only
```

## Exit Codes

- 0: All checks passed
- 1: One or more checks failed
- 2: Script error

## Available Checks

Use with `-c` option for individual checks:

- `freeipa_status_check`, `freeipa_backup_check`, `freeipa_cipa_check`
- `freeipa_cdp_services_check`, `freeipa_checkports`
- `freeipa_internode_connectivity_check`
- `freeipa_disk_check`, `freeipa_memory_check`, `freeipa_cpu_check`
- `freeipa_ccm_network_status_check`
- `freeipa_check_saltuser_password_rotation`

See `./run_freeipa_health_check.sh --help` for complete list.

---

## Health Check Coverage (19 Tests)

| Check  | Description                | Status                                 |
| ------ | -------------------------- | -------------------------------------- |
| **01** | FreeIPA Services Status    | All services running across nodes      |
| **02** | Cloud Backups              | Backup functionality and latest status |
| **03** | Replication CIPA State     | Consistency across FreeIPA servers     |
| **04** | LDAP Conflicts             | User/group/host conflict detection     |
| **05** | Replication Agreements     | Status between IPA servers             |
| **06** | Group Consistency          | MD5 verification across nodes          |
| **07** | User Consistency           | MD5 verification across nodes          |
| **08** | DNS Duplicates             | Forward and reverse DNS validation     |
| **09** | CDP Services               | All 7 CDP services running             |
| **10** | Network Ports              | Required ports listening               |
| **11** | Health Agent API           | Health agent API endpoint check        |
| **12** | CCM Availability           | Cluster Connectivity Manager status    |
| **13** | Control Plane Connectivity | CDP endpoint accessibility             |
| **14** | Saltuser Password          | Password expiration check              |
| **15** | Nginx Configuration        | Config consistency across nodes        |
| **16** | Disk Usage                 | Disk utilization monitoring            |
| **17** | Memory Usage               | Memory availability monitoring         |
| **18** | CPU Usage                  | CPU utilization monitoring             |
| **19** | Inter-Node Connectivity    | Port connectivity between nodes        |

## Dependencies

**Required**: `salt`, `jq`, `ipa`, `cipa`, `ldapsearch`, `host`
**Auto-installed**: `lsof` (for port checks)
**Auto-activated**: Salt environment (if `activate_salt_env` available)

## Troubleshooting

**Permission denied**: Run as root (`sudo -i`)
**Salt issues**: Verify `source activate_salt_env` works
**Missing tools**: Use `-n` option to check without running

---

## Changelog

**v2.1.0** - Added resource monitoring, CDP services, network connectivity, 11 new checks
**v2.0.0** - Initial comprehensive health check with progress bars and logging
**v1.x** - Basic health check functions

---

## Summary

**Version**: 2.1.0
**Checks**: 19 comprehensive tests
**Coverage**: FreeIPA core + CDP services + resources + network + security
**Status**: Production ready ✅

---

_Author: Jimmy Garagorry | For Cloudera On Cloud FreeIPA Environments_
