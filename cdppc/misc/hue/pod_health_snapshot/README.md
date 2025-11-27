# Pod Health Snapshot Script

## Overview

The `pod_health_snapshot.py` script collects comprehensive OS-level diagnostic information from Kubernetes pods to help diagnose performance issues, hangs, or freezes. It creates a detailed snapshot of the pod's state at a specific point in time, including Hue-specific logs and configuration files.

## Features

- ✅ **Comprehensive Diagnostics** - Collects process, network, resource, and system information
- ✅ **Hung Process Detection** - Identifies processes in D state and other hung indicators
- ✅ **Resource Monitoring** - CPU, memory, disk, I/O, and file descriptor usage
- ✅ **Network Analysis** - Network connections, statistics, and routing information
- ✅ **Hue-Specific Collection** - Collects actual Hue log and configuration files
- ✅ **Binary File Filtering** - Automatically skips binary files and maintains audit log
- ✅ **Multiple Pod Support** - Process single or multiple pods in one run
- ✅ **Auto-Discovery** - Automatically finds Hue-related pods in namespace
- ✅ **Detailed Reports** - Generates markdown summary with analysis guidelines
- ✅ **Portable Bundle** - Creates `cldr_healthcheck_<timestamp>.tgz` archive
- ✅ **Portable** - Works with any kubeconfig and namespace

## Prerequisites

- Python 3.6 or higher
- `kubectl` installed and accessible
- Access to Kubernetes cluster
- Read access to target pods

## Usage

### Basic Usage - Single Pod

```bash
python3 pod_health_snapshot.py \
  --kubeconfig ~/k8s/config.yml \
  --namespace impala-1764198109-s6vr \
  --pod huebackend-0
```

### Multiple Pods

Process multiple pods in one run by specifying comma-separated pod names:

```bash
python3 pod_health_snapshot.py \
  --kubeconfig ~/k8s/config.yml \
  --namespace impala-1764198109-s6vr \
  --pod huebackend-0,huebackend-1,huebackend-2
```

### Auto-Discovery

Automatically discover and process all Hue-related pods in a namespace:

```bash
python3 pod_health_snapshot.py \
  --kubeconfig ~/k8s/config.yml \
  --namespace impala-1764198109-s6vr
```

The script will automatically find pods matching Hue-related patterns and process all running pods.

### With Custom Output Directory

```bash
python3 pod_health_snapshot.py \
  --kubeconfig ~/k8s/config.yml \
  --namespace impala-1764198109-s6vr \
  --pod huebackend-0 \
  --output /tmp/pod_snapshot
```

### Using Environment Variable

```bash
export KUBECONFIG=~/k8s/config.yml
python3 pod_health_snapshot.py \
  --namespace impala-1764198109-s6vr \
  --pod huebackend-0
```

## Command Line Options

| Option         | Required | Description                                                                              |
| -------------- | -------- | ---------------------------------------------------------------------------------------- |
| `--kubeconfig` | No\*     | Path to kubeconfig file (or set KUBECONFIG env var)                                      |
| `--namespace`  | Yes      | Kubernetes namespace                                                                     |
| `--pod`        | No       | Pod name(s), comma-separated for multiple pods. If not provided, auto-discovers Hue pods |
| `--output`     | No       | Output directory (default: auto-generated)                                               |
| `--help`       | No       | Show help message                                                                        |

\*Required if KUBECONFIG environment variable is not set

## What Gets Collected

The script collects the following diagnostic information:

### System Information

- Hostname, uptime, OS release, kernel version

### Process Information

- All running processes (`ps aux`)
- Process tree view
- Detailed process information
- Top processes by CPU usage
- Top processes by memory usage

### Resource Usage

- Memory statistics (`free -h`)
- CPU information (`/proc/cpuinfo`)
- Load average
- Disk space usage
- Inode usage
- I/O statistics

### Network Information

- Listening ports (`netstat -tuln` or `ss -tuln`)
- All network connections
- Network statistics
- Network interface configuration
- Routing table

### File Descriptors

- System-wide file descriptor usage
- File descriptors per process
- Top processes by file descriptor count

### Thread Information

- All threads (`ps -eLf`)
- Top processes by thread count

### Container Information

- Container metadata
- Kubernetes namespace
- Container environment

### System Logs

- Recent kernel messages (`dmesg`)
- System log files (if available)

### Hung Process Analysis

- Processes in D state (uninterruptible sleep)
- Load average analysis
- High CPU time processes
- Summary of hung indicators

### Kubernetes Events

- Pod events from Kubernetes API

### Hue-Specific Information

- Hue-related processes
- Python processes
- Hue log directory listing
- **Actual Hue log files** (up to 20 files, 1MB each max, text files only)
- Hue configuration file listing
- **Actual Hue configuration files** (all text files)

### Binary Files Audit

- `binary_files_audit.txt` - Log of binary files detected and skipped during collection

## Output Structure

### Single Pod

The script creates a directory with the following structure:

```
pod_snapshot_<namespace>_<pod>_<timestamp>/
├── SUMMARY.md                          # Main summary report
├── binary_files_audit.txt              # Binary files audit log
├── system_info.txt                     # System information
├── processes_ps_aux.txt                 # All processes
├── process_tree.txt                     # Process tree
├── processes_detailed.txt               # Detailed process info
├── top_cpu_processes.txt                # Top CPU processes
├── top_memory_processes.txt             # Top memory processes
├── memory_info.txt                      # Memory statistics
├── cpu_info.txt                         # CPU information
├── load_average.txt                     # Load average
├── disk_usage.txt                       # Disk usage
├── inode_usage.txt                       # Inode usage
├── io_statistics.txt                    # I/O statistics
├── network_listening.txt                # Listening ports
├── network_connections.txt              # All connections
├── network_statistics.txt               # Network stats
├── network_interfaces.txt               # Network interfaces
├── routing_table.txt                   # Routing table
├── file_descriptors_system.txt          # System FDs
├── file_descriptors_per_process.txt     # FDs per process
├── top_file_descriptors.txt             # Top FD processes
├── threads_all.txt                      # All threads
├── top_threads.txt                      # Top threads
├── container_info.txt                   # Container info
├── dmesg_recent.txt                     # Kernel messages
├── hung_indicators_summary.txt          # Hung indicators summary
├── hung_indicators_d_state.txt          # D state processes
├── load_analysis.txt                    # Load analysis
├── high_cpu_time_processes.txt          # High CPU time
├── pod_events.yaml                      # Kubernetes events
├── hue_processes.txt                    # Hue processes
├── python_processes.txt                 # Python processes
├── hue_log_directory.txt                # Hue log listing
├── hue_config_files.txt                 # Hue config listing
├── hue_logs/                            # Actual Hue log files
│   ├── <log_file_1>
│   ├── <log_file_2>
│   └── ...
└── hue_config/                          # Actual Hue config files
    ├── <config_file_1>
    ├── <config_file_2>
    └── ...
```

### Multiple Pods

When processing multiple pods, each pod gets its own subdirectory:

```
pod_snapshot_<namespace>_multiple_<timestamp>/
├── COMBINED_SUMMARY.md                 # Combined summary for all pods
├── <pod1>/
│   ├── SUMMARY.md
│   ├── binary_files_audit.txt
│   └── ... (all diagnostic files)
├── <pod2>/
│   ├── SUMMARY.md
│   ├── binary_files_audit.txt
│   └── ... (all diagnostic files)
└── ...
```

## Bundle Archive

After collection, the script automatically creates a compressed archive:

- **Format**: `cldr_healthcheck_<timestamp>.tgz`
- **Example**: `cldr_healthcheck_20251127_171033.tgz`
- **Contents**: Complete snapshot directory with all collected files
- **Compression**: gzip-compressed tar archive

## Analysis Guidelines

### Start Here

1. **Read `SUMMARY.md`** - Provides overview and analysis guidelines
2. **Check `hung_indicators_summary.txt`** - Quick overview of potential issues
3. **Review specific files** based on the symptoms

### Identifying Hung Processes

**Signs of hung processes:**

- Processes in **D state** (uninterruptible sleep) - check `hung_indicators_d_state.txt`
- High load average relative to CPU count - check `load_analysis.txt`
- High CPU time without corresponding CPU usage - check `high_cpu_time_processes.txt`
- Many threads in waiting state - check `threads_all.txt`
- File descriptor exhaustion - check `top_file_descriptors.txt`

### Resource Contention

**Check these files:**

- `memory_info.txt` - Memory pressure
- `disk_usage.txt` - Disk space issues
- `inode_usage.txt` - Inode exhaustion
- `io_statistics.txt` - I/O bottlenecks

### Network Issues

**Check these files:**

- `network_connections.txt` - Too many connections
- `network_statistics.txt` - Network errors or drops
- `routing_table.txt` - Routing issues

### Hue-Specific Issues

**Check these files:**

- `hue_logs/` - Review actual log files for errors
- `hue_config/` - Verify configuration settings
- `hue_processes.txt` - Check if Hue processes are running
- `python_processes.txt` - Monitor Python process health

## Common Issues

### Issue: Processes in D State

**Symptom**: Processes stuck in uninterruptible sleep  
**Investigation**: Check `io_statistics.txt`, `network_statistics.txt`, `dmesg_recent.txt`

### Issue: High Load Average

**Symptom**: Load average exceeds CPU count significantly  
**Investigation**: Check `top_cpu_processes.txt`, `load_analysis.txt`, `processes_ps_aux.txt`

### Issue: Memory Pressure

**Symptom**: High memory usage, swapping  
**Investigation**: Check `memory_info.txt`, `top_memory_processes.txt`, `pod_events.yaml` for OOM events

### Issue: Network Connectivity Problems

**Symptom**: Cannot connect to services  
**Investigation**: Check `network_connections.txt`, `network_statistics.txt`, `routing_table.txt`

### Issue: Hue Application Problems

**Symptom**: Hue not responding or slow  
**Investigation**:

- Check `hue_logs/` for error messages
- Review `hue_config/` for misconfigurations
- Check `hue_processes.txt` for process status
- Review `python_processes.txt` for Python-related issues

## Binary File Handling

The script automatically detects and handles binary files:

- **Text files**: Decoded as UTF-8 and saved as text
- **Binary files**: Automatically skipped and logged in `binary_files_audit.txt`
- **Large files**: Log files are truncated at 1MB to prevent huge archives
- **Audit trail**: All skipped binary files are recorded with timestamp and reason

Binary file detection uses multiple heuristics:

- Checks for null bytes (strong indicator of binary content)
- Analyzes text-to-binary ratio in file content
- Attempts UTF-8 decoding validation

If you need to inspect skipped binary files, access them directly on the pod using `kubectl exec`.

## Best Practices

1. **Take Snapshots Regularly** - Capture baseline when pod is healthy
2. **Compare Snapshots** - Compare healthy vs. problematic states
3. **Time Series Analysis** - Take multiple snapshots over time for ongoing issues
4. **Document Context** - Note what was happening when snapshot was taken
5. **Share Reports** - Bundle archives are self-contained and can be shared with team
6. **Review Hue Logs** - Check `hue_logs/` directory for application-specific errors

## Troubleshooting

### Error: kubectl not found

**Solution**: Ensure kubectl is installed and in PATH, or update the script to use full path

### Error: Cannot connect to pod

**Solution**:

- Verify pod is running: `kubectl get pods -n <namespace>`
- Check pod status: `kubectl describe pod <pod> -n <namespace>`
- Verify kubeconfig and credentials

### Error: Permission denied

**Solution**:

- Verify you have read access to the pod
- Check RBAC permissions
- Ensure pod security context allows exec

### Warning: Some commands failed

**Solution**:

- Some commands may not be available in all containers
- Check which commands are available in your container image
- Script continues even if some commands fail

### Warning: Binary files skipped

**Solution**:

- This is expected behavior - binary files are automatically skipped
- Check `binary_files_audit.txt` for a list of skipped files
- Access binary files directly on the pod if needed

## Security Considerations

- Script only performs **read-only** operations
- No data modification or deletion
- All operations are auditable via kubectl
- No credentials are stored or logged
- Output files may contain sensitive information - handle appropriately
- Bundle archives should be stored securely

## Limitations

- Requires `kubectl` access to cluster
- Some commands may not be available in minimal container images
- Network commands may require additional tools (netstat, ss, ip)
- I/O statistics require `iostat` or access to `/proc/diskstats`
- System logs may not be available in all containers
- Log files are limited to 1MB each to prevent huge archives
- Only first 20 log files are collected

## Version

Current version: 2.0.0

### Version 2.0.0 Features

- Multiple pod support (comma-separated pod names)
- Auto-discovery of Hue-related pods
- Binary file filtering with audit logging
- Combined summary reports for multiple pods

## Related Tools

- `validate_hue_cleanup.py` - Validates Hue database cleanup requirements

## Support

For issues or questions:

1. Check the troubleshooting section
2. Review the generated `SUMMARY.md` report
3. Verify kubectl and pod connectivity
4. Check pod logs for additional information

---

**Remember**: This script creates a snapshot at a specific point in time. For ongoing issues, take multiple snapshots to identify patterns and trends. The bundle archive (`cldr_healthcheck_<timestamp>.tgz`) contains all diagnostic information and can be easily shared for analysis.
