#!/usr/bin/env python3
"""
Kubernetes Pod Health Snapshot Script

This script connects to Kubernetes pods and gathers comprehensive OS-level
diagnostic information to help diagnose performance issues, hangs, or freezes.

Usage:
    python3 pod_health_snapshot.py --kubeconfig <path> --namespace <namespace> [--pod <pod-name>] [--output <dir>]

Examples:
    # Single pod
    python3 pod_health_snapshot.py --kubeconfig ~/k8s/config.yml --namespace my-ns --pod huebackend-0
    
    # Multiple pods (comma-separated)
    python3 pod_health_snapshot.py --kubeconfig ~/k8s/config.yml --namespace my-ns --pod huebackend-0,huebackend-1
    
    # Auto-discover Hue pods (no --pod specified)
    python3 pod_health_snapshot.py --kubeconfig ~/k8s/config.yml --namespace my-ns
"""

import argparse
import subprocess
import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import shutil
import tarfile
import tempfile


class Colors:
    """ANSI color codes for terminal output."""
    INFO = '\033[94m'  # Blue
    SUCCESS = '\033[92m'  # Green
    WARNING = '\033[93m'  # Yellow
    ERROR = '\033[91m'  # Red
    RESET = '\033[0m'  # Reset
    BOLD = '\033[1m'

def log_info(message: str):
    """Print informational message to stdout.
    
    Args:
        message: Message text to display
    """
    print(f"{Colors.INFO}[INFO]{Colors.RESET} {message}")


def log_success(message: str):
    """Print success message to stdout.
    
    Args:
        message: Message text to display
    """
    print(f"{Colors.SUCCESS}[SUCCESS]{Colors.RESET} {message}")


def log_warning(message: str):
    """Print warning message to stdout.
    
    Args:
        message: Message text to display
    """
    print(f"{Colors.WARNING}[WARNING]{Colors.RESET} {message}")


def log_error(message: str):
    """Print error message to stdout.
    
    Args:
        message: Message text to display
    """
    print(f"{Colors.ERROR}[ERROR]{Colors.RESET} {message}")

def expand_path(path: str) -> str:
    """Expand ~ and environment variables in path.
    
    Args:
        path: Path string that may contain ~ or environment variables
        
    Returns:
        Expanded path string
    """
    return os.path.expanduser(os.path.expandvars(path))

def is_binary_content(content: bytes, max_sample_size: int = 8192) -> bool:
    """Check if content is binary.
    
    Args:
        content: The content to check (bytes)
        max_sample_size: Maximum number of bytes to sample for detection
    
    Returns:
        True if content appears to be binary, False otherwise
    """
    if not content:
        return False
    
    sample = content[:max_sample_size]
    
    if b'\x00' in sample:
        return True
    
    allowed_control_chars = {0x09, 0x0A, 0x0B, 0x0C, 0x0D}
    
    text_bytes = 0
    total_bytes = len(sample)
    
    for byte_val in sample:
        if (32 <= byte_val < 127) or byte_val in allowed_control_chars:
            text_bytes += 1
    
    text_ratio = text_bytes / total_bytes if total_bytes > 0 else 0
    if text_ratio < 0.7:
        return True
    
    return False

_binary_audit_log = []

def log_binary_skip(file_path: str, reason: str = "Binary content detected"):
    """Log that a binary file was skipped.
    
    Args:
        file_path: Path to the file that was skipped
        reason: Reason for skipping
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _binary_audit_log.append({
        "timestamp": timestamp,
        "file_path": file_path,
        "reason": reason
    })
    log_warning(f"Skipping binary file: {file_path} - {reason}")

def get_binary_audit_log() -> List[Dict]:
    """Get the audit log of skipped binary files."""
    return _binary_audit_log.copy()

def clear_binary_audit_log():
    """Clear the audit log."""
    _binary_audit_log.clear()

def write_binary_audit_log(output_dir: str):
    """Write the binary file audit log to a file.
    
    Args:
        output_dir: Directory to write the audit log file
    """
    audit_log = get_binary_audit_log()
    
    if not audit_log:
        with open(os.path.join(output_dir, "binary_files_audit.txt"), "w") as f:
            f.write("=== Binary Files Audit Log ===\n\n")
            f.write("No binary files were encountered during collection.\n")
            f.write("All collected files were verified as text files.\n")
        return
    
    with open(os.path.join(output_dir, "binary_files_audit.txt"), "w") as f:
        f.write("=== Binary Files Audit Log ===\n\n")
        f.write(f"Total binary files skipped: {len(audit_log)}\n\n")
        f.write("The following binary files were detected and skipped during collection:\n\n")
        f.write("-" * 80 + "\n\n")
        
        for entry in audit_log:
            f.write(f"Timestamp: {entry['timestamp']}\n")
            f.write(f"File Path: {entry['file_path']}\n")
            f.write(f"Reason: {entry['reason']}\n")
            f.write("-" * 80 + "\n\n")
        
        f.write("\nNote: Binary files are automatically skipped to avoid collecting\n")
        f.write("non-text content. If you need to inspect these files, access them\n")
        f.write("directly on the pod using kubectl exec.\n")
    
    log_info(f"Binary audit log written: {len(audit_log)} file(s) skipped")

def find_kubectl() -> str:
    """Find kubectl binary path in common locations or PATH.
    
    Returns:
        Path to kubectl binary, or "kubectl" if not found
    """
    common_paths = [
        os.path.expanduser("~/bin/kubectl"),
        "/usr/local/bin/kubectl",
        "/usr/bin/kubectl",
        "kubectl"
    ]
    
    for path in common_paths:
        if path == "kubectl":
            result = subprocess.run(["which", "kubectl"], capture_output=True)
            if result.returncode == 0:
                return result.stdout.decode().strip()
        elif os.path.exists(path) and os.access(path, os.X_OK):
            return path
    
    return "kubectl"

def run_kubectl_exec(kubeconfig: str, namespace: str, pod: str, 
                     cmd: List[str], timeout: int = 30, binary: bool = False) -> Tuple[int, any, any]:
    """Run command inside pod via kubectl exec.
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Kubernetes namespace
        pod: Pod name
        cmd: Command to execute as list of arguments
        timeout: Command timeout in seconds (default: 30)
        binary: If True, return bytes instead of strings (default: False)
        
    Returns:
        Tuple of (returncode, stdout, stderr)
        - If binary=True: stdout and stderr are bytes
        - If binary=False: stdout and stderr are strings
    """
    kubectl_path = find_kubectl()
    full_cmd = [kubectl_path, "--kubeconfig", expand_path(kubeconfig), 
                "-n", namespace, "exec", pod, "--"] + cmd
    
    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=not binary,
            timeout=timeout,
            check=False
        )
        if binary:
            stdout_bytes = result.stdout if isinstance(result.stdout, bytes) else result.stdout.encode('utf-8', errors='replace')
            stderr_bytes = result.stderr if isinstance(result.stderr, bytes) else result.stderr.encode('utf-8', errors='replace')
            return result.returncode, stdout_bytes, stderr_bytes
        else:
            return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        log_warning(f"Command timed out after {timeout} seconds: {' '.join(cmd)}")
        if binary:
            return 1, b"", f"Command timed out after {timeout} seconds".encode('utf-8')
        else:
            return 1, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        log_error(f"Error running command: {e}")
        if binary:
            return 1, b"", str(e).encode('utf-8')
        else:
            return 1, "", str(e)

def discover_hue_pods(kubeconfig: str, namespace: str) -> List[str]:
    """Discover Hue-related pods in the namespace.
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Kubernetes namespace
        
    Returns:
        List of pod names that are Hue-related and in Running state
    """
    log_info(f"Discovering Hue-related pods in namespace '{namespace}'...")
    
    kubectl_path = find_kubectl()
    
    cmd = [kubectl_path, "--kubeconfig", expand_path(kubeconfig),
           "-n", namespace, "get", "pods", "-o", "json", "-l", "app=huebackend"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            pods = []
            for item in data.get("items", []):
                name = item["metadata"]["name"]
                status = item["status"].get("phase", "Unknown")
                if status == "Running":
                    pods.append(name)
            if pods:
                log_success(f"Found {len(pods)} Hue pod(s) using label selector: {', '.join(pods)}")
                return pods
    except Exception as e:
        log_warning(f"Label selector search failed: {e}")
    
    cmd = [kubectl_path, "--kubeconfig", expand_path(kubeconfig),
           "-n", namespace, "get", "pods", "-o", "json"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
        if result.returncode != 0:
            log_error(f"Failed to get pods: {result.stderr}")
            return []
        
        data = json.loads(result.stdout)
        pods = []
        hue_patterns = ["hue", "huebackend", "hue-backend", "hue-backend"]
        
        for item in data.get("items", []):
            name = item["metadata"]["name"]
            status = item["status"].get("phase", "Unknown")
            
            name_lower = name.lower()
            if any(pattern.lower() in name_lower for pattern in hue_patterns):
                if status == "Running":
                    pods.append(name)
        
        if pods:
            log_success(f"Found {len(pods)} Hue-related pod(s): {', '.join(pods)}")
        else:
            log_warning("No running Hue-related pods found in namespace")
        
        return pods
    except json.JSONDecodeError:
        log_error("Failed to parse pod list JSON")
        return []
    except Exception as e:
        log_error(f"Error discovering pods: {e}")
        return []

def get_pod_info(kubeconfig: str, namespace: str, pod: str) -> Dict:
    """Get pod information from Kubernetes API.
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Kubernetes namespace
        pod: Pod name
        
    Returns:
        Dictionary containing pod information, or empty dict if error
    """
    log_info("Retrieving pod information from Kubernetes API...")
    
    kubectl_path = find_kubectl()
    cmd = [kubectl_path, "--kubeconfig", expand_path(kubeconfig),
           "-n", namespace, "get", "pod", pod, "-o", "json"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            log_success("Pod information retrieved")
            return data
        else:
            log_error(f"Failed to get pod info: {result.stderr}")
            return {}
    except Exception as e:
        log_error(f"Error getting pod info: {e}")
        return {}

def collect_system_info(kubeconfig: str, namespace: str, pod: str, output_dir: str):
    """Collect basic system information.
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Kubernetes namespace
        pod: Pod name
        output_dir: Output directory for collected files
    """
    log_info("Collecting system information...")
    
    info = {}
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod, ["hostname"])
    if returncode == 0:
        info["hostname"] = stdout.strip()
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod, ["uptime"])
    if returncode == 0:
        info["uptime"] = stdout.strip()
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod, 
                                                  ["cat", "/etc/os-release"])
    if returncode == 0:
        info["os_release"] = stdout
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod, ["uname", "-a"])
    if returncode == 0:
        info["kernel"] = stdout.strip()
    
    with open(os.path.join(output_dir, "system_info.txt"), "w") as f:
        f.write("=== System Information ===\n\n")
        for key, value in info.items():
            f.write(f"{key.upper()}:\n{value}\n\n")
    
    log_success("System information collected")

def collect_process_info(kubeconfig: str, namespace: str, pod: str, output_dir: str):
    """Collect detailed process information.
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Kubernetes namespace
        pod: Pod name
        output_dir: Output directory for collected files
    """
    log_info("Collecting process information...")
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod, 
                                                  ["ps", "aux"], timeout=10)
    if returncode == 0:
        with open(os.path.join(output_dir, "processes_ps_aux.txt"), "w") as f:
            f.write("=== All Processes (ps aux) ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod, 
                                                  ["ps", "auxf"], timeout=10)
    if returncode == 0:
        with open(os.path.join(output_dir, "process_tree.txt"), "w") as f:
            f.write("=== Process Tree (ps auxf) ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["ps", "-eo", "pid,ppid,user,stat,start,time,command"], timeout=10)
    if returncode == 0:
        with open(os.path.join(output_dir, "processes_detailed.txt"), "w") as f:
            f.write("=== Detailed Process Information ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["bash", "-c", "ps aux --sort=-%cpu | head -20"], timeout=10)
    if returncode == 0:
        with open(os.path.join(output_dir, "top_cpu_processes.txt"), "w") as f:
            f.write("=== Top 20 Processes by CPU ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["bash", "-c", "ps aux --sort=-%mem | head -20"], timeout=10)
    if returncode == 0:
        with open(os.path.join(output_dir, "top_memory_processes.txt"), "w") as f:
            f.write("=== Top 20 Processes by Memory ===\n\n")
            f.write(stdout)
    
    log_success("Process information collected")

def collect_resource_usage(kubeconfig: str, namespace: str, pod: str, output_dir: str):
    """Collect resource usage information.
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Kubernetes namespace
        pod: Pod name
        output_dir: Output directory for collected files
    """
    log_info("Collecting resource usage information...")
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod, ["free", "-h"])
    if returncode == 0:
        with open(os.path.join(output_dir, "memory_info.txt"), "w") as f:
            f.write("=== Memory Information ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod, ["cat", "/proc/cpuinfo"])
    if returncode == 0:
        with open(os.path.join(output_dir, "cpu_info.txt"), "w") as f:
            f.write("=== CPU Information ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod, ["cat", "/proc/loadavg"])
    if returncode == 0:
        with open(os.path.join(output_dir, "load_average.txt"), "w") as f:
            f.write("=== Load Average ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod, ["df", "-h"])
    if returncode == 0:
        with open(os.path.join(output_dir, "disk_usage.txt"), "w") as f:
            f.write("=== Disk Usage ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod, ["df", "-i"])
    if returncode == 0:
        with open(os.path.join(output_dir, "inode_usage.txt"), "w") as f:
            f.write("=== Inode Usage ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod, ["iostat", "-x", "1", "2"], timeout=15)
    if returncode == 0:
        with open(os.path.join(output_dir, "io_statistics.txt"), "w") as f:
            f.write("=== I/O Statistics ===\n\n")
            f.write(stdout)
    else:
        returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod, ["cat", "/proc/diskstats"])
        if returncode == 0:
            with open(os.path.join(output_dir, "disk_stats.txt"), "w") as f:
                f.write("=== Disk Statistics ===\n\n")
                f.write(stdout)
    
    log_success("Resource usage information collected")

def collect_network_info(kubeconfig: str, namespace: str, pod: str, output_dir: str):
    """Collect network connection information.
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Kubernetes namespace
        pod: Pod name
        output_dir: Output directory for collected files
    """
    log_info("Collecting network information...")
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["netstat", "-tuln"], timeout=10)
    if returncode == 0:
        with open(os.path.join(output_dir, "network_listening.txt"), "w") as f:
            f.write("=== Listening Network Connections (netstat -tuln) ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["netstat", "-tun"], timeout=10)
    if returncode == 0:
        with open(os.path.join(output_dir, "network_connections.txt"), "w") as f:
            f.write("=== All Network Connections (netstat -tun) ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["netstat", "-s"], timeout=10)
    if returncode == 0:
        with open(os.path.join(output_dir, "network_statistics.txt"), "w") as f:
            f.write("=== Network Statistics (netstat -s) ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["ss", "-tuln"], timeout=10)
    if returncode == 0:
        with open(os.path.join(output_dir, "network_ss_listening.txt"), "w") as f:
            f.write("=== Listening Network Connections (ss -tuln) ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["ip", "addr", "show"], timeout=10)
    if returncode != 0:
        returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                      ["ifconfig", "-a"], timeout=10)
    if returncode == 0:
        with open(os.path.join(output_dir, "network_interfaces.txt"), "w") as f:
            f.write("=== Network Interfaces ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["ip", "route", "show"], timeout=10)
    if returncode != 0:
        returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                      ["route", "-n"], timeout=10)
    if returncode == 0:
        with open(os.path.join(output_dir, "routing_table.txt"), "w") as f:
            f.write("=== Routing Table ===\n\n")
            f.write(stdout)
    
    log_success("Network information collected")

def collect_file_descriptors(kubeconfig: str, namespace: str, pod: str, output_dir: str):
    """Collect file descriptor information.
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Kubernetes namespace
        pod: Pod name
        output_dir: Output directory for collected files
    """
    log_info("Collecting file descriptor information...")
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["cat", "/proc/sys/fs/file-nr"])
    if returncode == 0:
        with open(os.path.join(output_dir, "file_descriptors_system.txt"), "w") as f:
            f.write("=== System File Descriptors ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["bash", "-c", 
                                                   "for pid in $(ps -eo pid --no-headers 2>/dev/null | head -20); do echo \"PID: $pid ($(ps -p $pid -o comm= 2>/dev/null || echo 'unknown'))\"; ls /proc/$pid/fd 2>/dev/null | wc -l || echo '0'; done"], timeout=15)
    if returncode == 0:
        with open(os.path.join(output_dir, "file_descriptors_per_process.txt"), "w") as f:
            f.write("=== File Descriptors per Process (Top 20) ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["bash", "-c",
                                                   "for pid in $(ps -eo pid --no-headers 2>/dev/null); do fd_count=$(ls /proc/$pid/fd 2>/dev/null | wc -l); if [ $fd_count -gt 10 ]; then echo \"$fd_count $pid $(ps -p $pid -o comm= 2>/dev/null || echo 'unknown')\"; fi; done | sort -rn | head -20"], timeout=20)
    if returncode == 0 and stdout.strip():
        with open(os.path.join(output_dir, "top_file_descriptors.txt"), "w") as f:
            f.write("=== Top Processes by File Descriptor Count ===\n\n")
            f.write("Format: FD_Count PID Command\n\n")
            f.write(stdout)
    
    log_success("File descriptor information collected")

def collect_thread_info(kubeconfig: str, namespace: str, pod: str, output_dir: str):
    """Collect thread information.
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Kubernetes namespace
        pod: Pod name
        output_dir: Output directory for collected files
    """
    log_info("Collecting thread information...")
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["ps", "-eLf"], timeout=10)
    if returncode == 0:
        with open(os.path.join(output_dir, "threads_all.txt"), "w") as f:
            f.write("=== All Threads (ps -eLf) ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["bash", "-c",
                                                   "ps -eo pid,nlwp,comm --sort=-nlwp 2>/dev/null | head -20"], timeout=10)
    if returncode == 0:
        with open(os.path.join(output_dir, "top_threads.txt"), "w") as f:
            f.write("=== Top Processes by Thread Count ===\n\n")
            f.write(stdout)
    
    log_success("Thread information collected")

def collect_hue_specific_info(kubeconfig: str, namespace: str, pod: str, output_dir: str):
    """Collect Hue-specific process and application information.
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Kubernetes namespace
        pod: Pod name
        output_dir: Output directory for collected files
    """
    log_info("Collecting Hue-specific information...")
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["bash", "-c", "ps aux | grep -i hue | grep -v grep"], timeout=10)
    if returncode == 0 and stdout.strip():
        with open(os.path.join(output_dir, "hue_processes.txt"), "w") as f:
            f.write("=== Hue Processes ===\n\n")
            f.write(stdout)
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["bash", "-c", "ps aux | grep -i python | grep -v grep"], timeout=10)
    if returncode == 0 and stdout.strip():
        with open(os.path.join(output_dir, "python_processes.txt"), "w") as f:
            f.write("=== Python Processes ===\n\n")
            f.write(stdout)
    
    hue_log_dir = "/var/log/hive"
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["bash", "-c", f"ls -lah {hue_log_dir}/ 2>/dev/null | head -50"], timeout=5)
    if returncode == 0:
        with open(os.path.join(output_dir, "hue_log_directory.txt"), "w") as f:
            f.write("=== Hue Log Directory Contents ===\n\n")
            f.write(stdout)
        
        log_files = []
        for line in stdout.split('\n'):
            if line.strip() and not line.startswith('total'):
                parts = line.split()
                if len(parts) >= 9:
                    if parts[0].startswith('-'):
                        filename = ' '.join(parts[8:])
                        if filename and filename != '.' and filename != '..':
                            log_files.append(filename)
        
        if log_files:
            logs_subdir = os.path.join(output_dir, "hue_logs")
            os.makedirs(logs_subdir, exist_ok=True)
            log_info(f"Collecting {min(len(log_files), 20)} Hue log files...")
            
            for log_file in log_files[:20]:  # Limit to first 20 files
                log_path = f"{hue_log_dir}/{log_file}"
                returncode, stdout_bytes, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                              ["cat", log_path], timeout=10, binary=True)
                if returncode == 0:
                    if is_binary_content(stdout_bytes):
                        log_binary_skip(log_path, "Binary content detected in log file")
                        continue
                    
                    content = stdout_bytes[:1048576] if len(stdout_bytes) > 1048576 else stdout_bytes
                    safe_filename = log_file.replace('/', '_')
                    
                    try:
                        text_content = content.decode('utf-8', errors='replace')
                        with open(os.path.join(logs_subdir, safe_filename), "w", encoding='utf-8') as f:
                            f.write(text_content)
                    except (UnicodeDecodeError, AttributeError):
                        log_binary_skip(log_path, "Failed to decode as UTF-8")
                        continue
                    
                    if len(stdout_bytes) > 1048576:
                        with open(os.path.join(logs_subdir, f"{safe_filename}.truncated"), "w") as f:
                            f.write(f"File truncated at 1MB. Original size: {len(stdout_bytes)} bytes\n")
    
    hue_config_dir = "/etc/hue/conf"
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["bash", "-c", f"ls -lah {hue_config_dir}/ 2>/dev/null"], timeout=5)
    if returncode == 0:
        with open(os.path.join(output_dir, "hue_config_files.txt"), "w") as f:
            f.write("=== Hue Configuration Files ===\n\n")
            f.write(stdout)
        
        config_files = []
        for line in stdout.split('\n'):
            if line.strip() and not line.startswith('total'):
                parts = line.split()
                if len(parts) >= 9:
                    if parts[0].startswith('-'):
                        filename = ' '.join(parts[8:])
                        if filename and filename != '.' and filename != '..':
                            config_files.append(filename)
        
        if config_files:
            config_subdir = os.path.join(output_dir, "hue_config")
            os.makedirs(config_subdir, exist_ok=True)
            log_info(f"Collecting {len(config_files)} Hue config files...")
            
            for config_file in config_files:
                config_path = f"{hue_config_dir}/{config_file}"
                returncode, stdout_bytes, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                              ["cat", config_path], timeout=10, binary=True)
                if returncode == 0:
                    if is_binary_content(stdout_bytes):
                        log_binary_skip(config_path, "Binary content detected in config file")
                        continue
                    
                    safe_filename = config_file.replace('/', '_')
                    
                    try:
                        text_content = stdout_bytes.decode('utf-8', errors='replace')
                        with open(os.path.join(config_subdir, safe_filename), "w", encoding='utf-8') as f:
                            f.write(text_content)
                    except (UnicodeDecodeError, AttributeError):
                        log_binary_skip(config_path, "Failed to decode as UTF-8")
                        continue
    
    log_success("Hue-specific information collected")

def collect_container_info(kubeconfig: str, namespace: str, pod: str, output_dir: str):
    """Collect container-specific information.
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Kubernetes namespace
        pod: Pod name
        output_dir: Output directory for collected files
    """
    log_info("Collecting container information...")
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["test", "-f", "/.dockerenv"], timeout=5)
    is_docker = returncode == 0
    
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["test", "-d", "/var/run/secrets/kubernetes.io"], timeout=5)
    is_k8s = returncode == 0
    
    with open(os.path.join(output_dir, "container_info.txt"), "w") as f:
        f.write("=== Container Information ===\n\n")
        f.write(f"Is Docker Container: {is_docker}\n")
        f.write(f"Is Kubernetes Pod: {is_k8s}\n\n")
        
        if is_k8s:
            returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                          ["cat", "/var/run/secrets/kubernetes.io/serviceaccount/namespace"], timeout=5)
            if returncode == 0:
                f.write(f"Kubernetes Namespace: {stdout.strip()}\n")
        
        # Hostname
        returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod, ["hostname"])
        if returncode == 0:
            f.write(f"Hostname: {stdout.strip()}\n")
    
    log_success("Container information collected")

def collect_system_logs(kubeconfig: str, namespace: str, pod: str, output_dir: str):
    """Collect recent system logs."""
    log_info("Collecting system logs...")
    
    # dmesg (kernel messages)
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["dmesg", "-T"], timeout=10)
    if returncode == 0:
        # Get last 100 lines
        lines = stdout.split('\n')[-100:]
        with open(os.path.join(output_dir, "dmesg_recent.txt"), "w") as f:
            f.write("=== Recent Kernel Messages (last 100 lines) ===\n\n")
            f.write('\n'.join(lines))
    
    # System logs (if available)
    for log_file in ["/var/log/messages", "/var/log/syslog"]:
        returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                      ["tail", "-100", log_file], timeout=5)
        if returncode == 0:
            with open(os.path.join(output_dir, f"system_log_{os.path.basename(log_file)}.txt"), "w") as f:
                f.write(f"=== Recent {log_file} (last 100 lines) ===\n\n")
                f.write(stdout)
            break
    
    log_success("System logs collected")

def collect_hung_process_indicators(kubeconfig: str, namespace: str, pod: str, output_dir: str):
    """Collect indicators of hung/frozen processes."""
    log_info("Checking for hung process indicators...")
    
    indicators = []
    
    # Processes in D state (uninterruptible sleep - often indicates I/O wait)
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["ps", "aux"], timeout=10)
    if returncode == 0:
        d_state_processes = []
        for line in stdout.split('\n'):
            if ' D ' in line or ' D+ ' in line:
                d_state_processes.append(line)
        
        if d_state_processes:
            with open(os.path.join(output_dir, "hung_indicators_d_state.txt"), "w") as f:
                f.write("=== Processes in D State (Uninterruptible Sleep) ===\n")
                f.write("WARNING: These processes may be waiting on I/O and could indicate hangs\n\n")
                for proc in d_state_processes:
                    f.write(proc + "\n")
            indicators.append(f"Found {len(d_state_processes)} process(es) in D state")
    
    # High load average
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["cat", "/proc/loadavg"], timeout=5)
    if returncode == 0:
        parts = stdout.strip().split()
        if len(parts) >= 3:
            load_1min = float(parts[0])
            load_5min = float(parts[1])
            load_15min = float(parts[2])
            
            # Get CPU count
            returncode2, cpuinfo, _ = run_kubectl_exec(kubeconfig, namespace, pod,
                                                       ["grep", "-c", "^processor", "/proc/cpuinfo"], timeout=5)
            cpu_count = int(cpuinfo.strip()) if returncode2 == 0 and cpuinfo.strip() else 1
            
            if load_1min > cpu_count * 2:
                indicators.append(f"High load average: {load_1min} (CPUs: {cpu_count})")
            
            with open(os.path.join(output_dir, "load_analysis.txt"), "w") as f:
                f.write("=== Load Average Analysis ===\n\n")
                f.write(f"1-minute load: {load_1min}\n")
                f.write(f"5-minute load: {load_5min}\n")
                f.write(f"15-minute load: {load_15min}\n")
                f.write(f"CPU cores: {cpu_count}\n")
                f.write(f"Load per CPU: {load_1min/cpu_count:.2f}\n")
                if load_1min > cpu_count * 2:
                    f.write("\n⚠️ WARNING: Load average significantly exceeds CPU count\n")
    
    # Processes with high CPU time (potential infinite loops)
    returncode, stdout, stderr = run_kubectl_exec(kubeconfig, namespace, pod,
                                                  ["bash", "-c", "ps aux --sort=-time | head -21"], timeout=10)
    if returncode == 0:
        with open(os.path.join(output_dir, "high_cpu_time_processes.txt"), "w") as f:
            f.write("=== Processes with Highest CPU Time ===\n")
            f.write("High CPU time may indicate busy loops or hung processes\n\n")
            f.write(stdout)
    
    # Write summary
    with open(os.path.join(output_dir, "hung_indicators_summary.txt"), "w") as f:
        f.write("=== Hung Process Indicators Summary ===\n\n")
        if indicators:
            f.write("⚠️ Potential issues detected:\n\n")
            for indicator in indicators:
                f.write(f"- {indicator}\n")
        else:
            f.write("✅ No obvious hung process indicators detected\n")
    
    if indicators:
        log_warning(f"Found {len(indicators)} potential hung process indicator(s)")
    else:
        log_success("No hung process indicators detected")
    
    log_success("Hung process analysis completed")

def collect_pod_events(kubeconfig: str, namespace: str, pod: str, output_dir: str):
    """Collect Kubernetes pod events."""
    log_info("Collecting Kubernetes pod events...")
    
    kubectl_path = find_kubectl()
    cmd = [kubectl_path, "--kubeconfig", expand_path(kubeconfig),
           "-n", namespace, "get", "events", "--field-selector", f"involvedObject.name={pod}", "-o", "yaml"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
        if result.returncode == 0:
            with open(os.path.join(output_dir, "pod_events.yaml"), "w") as f:
                f.write("=== Kubernetes Pod Events ===\n\n")
                f.write(result.stdout)
            log_success("Pod events collected")
        else:
            log_warning("Could not retrieve pod events")
    except Exception as e:
        log_warning(f"Error collecting pod events: {e}")

def generate_summary_report(kubeconfig: str, namespace: str, pod: str, 
                           pod_info: Dict, output_dir: str):
    """Generate summary report."""
    log_info("Generating summary report...")
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Get pod status
    pod_status = "Unknown"
    pod_phase = "Unknown"
    if pod_info:
        pod_status = pod_info.get("status", {}).get("phase", "Unknown")
        pod_phase = pod_status
        containers = pod_info.get("status", {}).get("containerStatuses", [])
    
    report = f"""# Pod Health Snapshot Report

## Executive Summary

**Date**: {timestamp}  
**Namespace**: `{namespace}`  
**Pod**: `{pod}`  
**Pod Status**: {pod_phase}  
**Report Location**: `{output_dir}`

---

## 1. Pod Information

### 1.1 Kubernetes Pod Status
"""
    
    if pod_info:
        status = pod_info.get("status", {})
        metadata = pod_info.get("metadata", {})
        
        report += f"""
- **Name**: {metadata.get("name", "Unknown")}
- **Namespace**: {metadata.get("namespace", "Unknown")}
- **Phase**: {status.get("phase", "Unknown")}
- **Node**: {status.get("hostIP", "Unknown")}
- **Pod IP**: {status.get("podIP", "Unknown")}
- **Start Time**: {status.get("startTime", "Unknown")}

### 1.2 Container Status
"""
        containers = status.get("containerStatuses", [])
        for container in containers:
            name = container.get("name", "Unknown")
            ready = container.get("ready", False)
            state = container.get("state", {})
            report += f"""
**Container: {name}**
- Ready: {ready}
- State: {list(state.keys())[0] if state else "Unknown"}
"""
    
    report += f"""
---

## 2. Collected Information

The following diagnostic information has been collected:

### 2.1 System Information
- `system_info.txt` - Basic system information (hostname, uptime, OS, kernel)

### 2.2 Process Information
- `processes_ps_aux.txt` - All running processes
- `process_tree.txt` - Process tree view
- `processes_detailed.txt` - Detailed process information
- `top_cpu_processes.txt` - Top processes by CPU usage
- `top_memory_processes.txt` - Top processes by memory usage

### 2.3 Resource Usage
- `memory_info.txt` - Memory usage statistics
- `cpu_info.txt` - CPU information
- `load_average.txt` - System load average
- `disk_usage.txt` - Disk space usage
- `inode_usage.txt` - Inode usage
- `io_statistics.txt` or `disk_stats.txt` - I/O statistics

### 2.4 Network Information
- `network_listening.txt` - Listening network ports
- `network_connections.txt` - All network connections
- `network_statistics.txt` - Network statistics
- `network_interfaces.txt` - Network interface configuration
- `routing_table.txt` - Routing table

### 2.5 File Descriptors
- `file_descriptors_system.txt` - System-wide file descriptor usage
- `file_descriptors_per_process.txt` - File descriptors per process
- `top_file_descriptors.txt` - Top processes by file descriptor count

### 2.6 Thread Information
- `threads_all.txt` - All threads
- `top_threads.txt` - Top processes by thread count

### 2.7 Container Information
- `container_info.txt` - Container metadata and environment

### 2.8 System Logs
- `dmesg_recent.txt` - Recent kernel messages
- `system_log_*.txt` - System log files (if available)

### 2.9 Hung Process Analysis
- `hung_indicators_summary.txt` - Summary of hung process indicators
- `hung_indicators_d_state.txt` - Processes in D state (I/O wait)
- `load_analysis.txt` - Load average analysis
- `high_cpu_time_processes.txt` - Processes with high CPU time

### 2.10 Kubernetes Events
- `pod_events.yaml` - Kubernetes events for this pod

### 2.11 Hue-Specific Information
- `hue_processes.txt` - Hue-related processes
- `python_processes.txt` - Python processes (Hue runs on Python)
- `hue_log_directory.txt` - Hue log directory contents
- `hue_config_files.txt` - Hue configuration files
- `hue_logs/` - Directory containing actual Hue log files
- `hue_config/` - Directory containing actual Hue configuration files

### 2.12 Binary Files Audit
- `binary_files_audit.txt` - Audit log of binary files that were detected and skipped during collection

---

## 3. Analysis Guidelines

### 3.1 Identifying Hung Processes

**Check these files first:**
1. `hung_indicators_summary.txt` - Quick overview of potential issues
2. `processes_ps_aux.txt` - Look for processes in D state
3. `top_cpu_processes.txt` - High CPU usage may indicate busy loops
4. `load_analysis.txt` - High load may indicate resource contention

**Signs of hung processes:**
- Processes in **D state** (uninterruptible sleep) - waiting on I/O
- **High load average** relative to CPU count
- **High CPU time** without corresponding CPU usage
- **Many threads** in waiting state
- **File descriptor exhaustion**

### 3.2 Resource Contention

**Check these files:**
1. `memory_info.txt` - Memory pressure
2. `disk_usage.txt` - Disk space issues
3. `inode_usage.txt` - Inode exhaustion
4. `io_statistics.txt` - I/O bottlenecks

### 3.3 Network Issues

**Check these files:**
1. `network_connections.txt` - Too many connections
2. `network_statistics.txt` - Network errors or drops
3. `routing_table.txt` - Routing issues

### 3.4 Container/Pod Issues

**Check these files:**
1. `pod_events.yaml` - Kubernetes events (restarts, failures)
2. `container_info.txt` - Container environment
3. `dmesg_recent.txt` - Kernel-level issues

---

## 4. Common Issues and Solutions

### Issue: Processes in D State
**Symptom**: Processes stuck in uninterruptible sleep
**Possible Causes**:
- I/O wait (disk, network)
- NFS mount issues
- Device driver problems

**Investigation**:
- Check `io_statistics.txt` for I/O bottlenecks
- Check `network_statistics.txt` for network issues
- Review `dmesg_recent.txt` for hardware errors

### Issue: High Load Average
**Symptom**: Load average exceeds CPU count significantly
**Possible Causes**:
- Too many processes competing for CPU
- I/O wait causing process queuing
- CPU-intensive operations

**Investigation**:
- Check `top_cpu_processes.txt`
- Review `load_analysis.txt`
- Check `processes_ps_aux.txt` for process count

### Issue: Memory Pressure
**Symptom**: High memory usage, swapping
**Possible Causes**:
- Memory leak
- Insufficient memory allocation
- Too many processes

**Investigation**:
- Check `memory_info.txt`
- Review `top_memory_processes.txt`
- Check for OOM events in `pod_events.yaml`

### Issue: Network Connectivity Problems
**Symptom**: Cannot connect to services
**Possible Causes**:
- Too many connections
- Network errors
- Routing issues

**Investigation**:
- Check `network_connections.txt`
- Review `network_statistics.txt`
- Check `routing_table.txt`

---

## 5. Next Steps

1. **Review the summary**: Start with `hung_indicators_summary.txt`
2. **Identify the issue**: Use the analysis guidelines above
3. **Check related files**: Cross-reference information across files
4. **Compare with baseline**: If available, compare with previous snapshots
5. **Take action**: Based on findings, restart pod, adjust resources, or investigate further

---

**Report Generated**: {timestamp}  
**Script**: pod_health_snapshot.py  
**Namespace**: {namespace}  
**Pod**: {pod}

---

*This snapshot was taken at a specific point in time. For ongoing issues, consider taking multiple snapshots over time to identify patterns.*
"""
    
    with open(os.path.join(output_dir, "SUMMARY.md"), "w") as f:
        f.write(report)
    
    log_success("Summary report generated")

def process_pod(kubeconfig: str, namespace: str, pod: str, output_dir: str):
    """Process a single pod and collect all diagnostic information.
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Kubernetes namespace
        pod: Pod name
        output_dir: Output directory for this pod's snapshot
    """
    log_info(f"Processing pod: {pod}")
    
    # Get pod information
    pod_info = get_pod_info(kubeconfig, namespace, pod)
    
    # Collect all diagnostic information
    collect_system_info(kubeconfig, namespace, pod, output_dir)
    collect_process_info(kubeconfig, namespace, pod, output_dir)
    collect_resource_usage(kubeconfig, namespace, pod, output_dir)
    collect_network_info(kubeconfig, namespace, pod, output_dir)
    collect_file_descriptors(kubeconfig, namespace, pod, output_dir)
    collect_thread_info(kubeconfig, namespace, pod, output_dir)
    collect_container_info(kubeconfig, namespace, pod, output_dir)
    collect_system_logs(kubeconfig, namespace, pod, output_dir)
    collect_hung_process_indicators(kubeconfig, namespace, pod, output_dir)
    collect_pod_events(kubeconfig, namespace, pod, output_dir)
    collect_hue_specific_info(kubeconfig, namespace, pod, output_dir)
    
    # Write binary audit log for this pod
    write_binary_audit_log(output_dir)
    
    # Generate summary
    generate_summary_report(kubeconfig, namespace, pod, pod_info, output_dir)
    
    log_success(f"Completed processing pod: {pod}")

def main():
    parser = argparse.ArgumentParser(
        description="Collect comprehensive health snapshot of Kubernetes pod",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with single pod
  python3 pod_health_snapshot.py --kubeconfig ~/k8s/config.yml --namespace my-ns --pod huebackend-0
  
  # Multiple pods (comma-separated)
  python3 pod_health_snapshot.py --kubeconfig ~/k8s/config.yml --namespace my-ns --pod huebackend-0,huebackend-1
  
  # Auto-discover Hue pods (no --pod specified)
  python3 pod_health_snapshot.py --kubeconfig ~/k8s/config.yml --namespace my-ns
  
  # With custom output directory
  python3 pod_health_snapshot.py --kubeconfig ~/k8s/config.yml --namespace my-ns --pod huebackend-0 --output /tmp/pod_snapshot
        """
    )
    
    parser.add_argument(
        "--kubeconfig",
        type=str,
        help="Path to kubeconfig file (required if KUBECONFIG env var not set)"
    )
    
    parser.add_argument(
        "--namespace",
        type=str,
        required=True,
        help="Kubernetes namespace"
    )
    
    parser.add_argument(
        "--pod",
        type=str,
        required=False,
        help="Pod name(s). Can specify multiple pods separated by commas. If not provided, will auto-discover Hue-related pods in the namespace."
    )
    
    parser.add_argument(
        "--output",
        type=str,
        help="Output directory for snapshot (default: auto-generated)"
    )
    
    args = parser.parse_args()
    
    # Determine kubeconfig
    kubeconfig = args.kubeconfig or os.environ.get("KUBECONFIG")
    if not kubeconfig:
        log_error("kubeconfig not provided. Use --kubeconfig or set KUBECONFIG environment variable.")
        sys.exit(1)
    
    kubeconfig = expand_path(kubeconfig)
    if not os.path.exists(kubeconfig):
        log_error(f"Kubeconfig file not found: {kubeconfig}")
        sys.exit(1)
    
    log_info(f"Using kubeconfig: {kubeconfig}")
    log_info(f"Target namespace: {args.namespace}")
    
    # Determine which pods to process
    pods_to_process = []
    
    if args.pod:
        # Parse comma-separated pod names
        pods_to_process = [p.strip() for p in args.pod.split(",") if p.strip()]
        log_info(f"Processing {len(pods_to_process)} specified pod(s): {', '.join(pods_to_process)}")
    else:
        # Auto-discover Hue pods
        pods_to_process = discover_hue_pods(kubeconfig, args.namespace)
        if not pods_to_process:
            log_error("No pods found to process. Specify --pod or ensure Hue pods exist in the namespace.")
            sys.exit(1)
    
    if not pods_to_process:
        log_error("No pods specified or found. Cannot proceed.")
        sys.exit(1)
    
    # Create base output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.output:
        base_output_dir = expand_path(args.output)
    else:
        if len(pods_to_process) == 1:
            base_output_dir = f"pod_snapshot_{args.namespace}_{pods_to_process[0]}_{timestamp}"
        else:
            base_output_dir = f"pod_snapshot_{args.namespace}_multiple_{timestamp}"
    
    os.makedirs(base_output_dir, exist_ok=True)
    log_info(f"Base output directory: {base_output_dir}")
    
    # Clear binary audit log at the start
    clear_binary_audit_log()
    
    # Process each pod
    print("\n" + "="*70)
    print("Collecting Pod Health Snapshot")
    if len(pods_to_process) > 1:
        print(f"Processing {len(pods_to_process)} pod(s)")
    print("="*70 + "\n")
    
    processed_pods = []
    failed_pods = []
    
    for pod in pods_to_process:
        try:
            # Create per-pod output directory
            if len(pods_to_process) == 1:
                pod_output_dir = base_output_dir
            else:
                pod_output_dir = os.path.join(base_output_dir, pod)
                os.makedirs(pod_output_dir, exist_ok=True)
            
            # Clear binary audit log for each pod
            clear_binary_audit_log()
            
            # Process this pod
            print(f"\n{'='*70}")
            print(f"Processing Pod: {pod}")
            print(f"{'='*70}\n")
            
            process_pod(kubeconfig, args.namespace, pod, pod_output_dir)
            processed_pods.append(pod)
            
        except Exception as e:
            log_error(f"Failed to process pod {pod}: {e}")
            failed_pods.append(pod)
    
    # Create combined summary for multiple pods
    if len(pods_to_process) > 1:
        combined_summary_path = os.path.join(base_output_dir, "COMBINED_SUMMARY.md")
        with open(combined_summary_path, "w") as f:
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"""# Combined Pod Health Snapshot Report

## Executive Summary

**Date**: {timestamp_str}  
**Namespace**: `{args.namespace}`  
**Total Pods Processed**: {len(processed_pods)}  
**Failed Pods**: {len(failed_pods)}  
**Report Location**: `{base_output_dir}`

---

## Processed Pods

""")
            for pod in processed_pods:
                f.write(f"- **{pod}** - See: `{pod}/SUMMARY.md`\n")
            
            if failed_pods:
                f.write(f"\n## Failed Pods\n\n")
                for pod in failed_pods:
                    f.write(f"- **{pod}** - Processing failed\n")
            
            f.write(f"""
---

## Directory Structure

```
{os.path.basename(base_output_dir)}/
""")
            for pod in processed_pods:
                f.write(f"├── {pod}/\n")
                f.write(f"│   └── SUMMARY.md\n")
            f.write("```\n")
    
    # Create tar.gz bundle
    bundle_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bundle_name = f"cldr_healthcheck_{bundle_timestamp}.tgz"
    log_info(f"Creating bundle: {bundle_name}")
    
    try:
        with tarfile.open(bundle_name, "w:gz") as tar:
            tar.add(base_output_dir, arcname=os.path.basename(base_output_dir))
        log_success(f"Bundle created: {bundle_name}")
    except Exception as e:
        log_error(f"Failed to create bundle: {e}")
        bundle_name = None
    
    print("\n" + "="*70)
    log_success(f"Pod health snapshot complete!")
    log_info(f"All diagnostic information saved to: {base_output_dir}")
    if bundle_name:
        log_info(f"Bundle archive created: {bundle_name}")
    
    if len(pods_to_process) == 1:
        log_info(f"Start with: {os.path.join(base_output_dir, 'SUMMARY.md')}")
    else:
        log_info(f"Start with: {os.path.join(base_output_dir, 'COMBINED_SUMMARY.md')}")
    
    if failed_pods:
        log_warning(f"{len(failed_pods)} pod(s) failed to process: {', '.join(failed_pods)}")
    
    print("="*70 + "\n")
    
    # Exit with error code if any pods failed
    if failed_pods:
        sys.exit(1)

if __name__ == "__main__":
    main()

