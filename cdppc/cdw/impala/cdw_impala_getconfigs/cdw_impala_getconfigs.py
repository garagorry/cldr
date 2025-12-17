#!/usr/bin/env python3
"""
CDW Impala Deployment Configuration Collector

This script performs a comprehensive analysis of all Kubernetes resources
associated with a CDW Impala deployment in a given namespace. It collects
detailed information about pods, services, deployments, statefulsets,
configmaps, secrets, persistent volumes, nodes, and all other relevant
Kubernetes infrastructure components.

The collected data is stored in a timestamped directory for analysis and
troubleshooting purposes.

Usage:
    python cdw_impala_getconfigs.py --ns <namespace> [--kubectl <path>] [--kubeconfig <path>]

Compatible with Python 3.6+
"""

import argparse
import json
import os
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple


class ProgressBar:
    """
    Simple progress bar implementation compatible with Python 3.6+.
    No external dependencies required.
    """
    
    def __init__(self, total: int, description: str = "", width: int = 50):
        """
        Initialize progress bar.
        
        Args:
            total: Total number of items to process
            description: Description text to display
            width: Width of the progress bar in characters
        """
        self.total = total
        self.current = 0
        self.description = description
        self.width = width
        self._last_percent = -1
    
    def update(self, n: int = 1) -> None:
        """
        Update progress by n items.
        
        Args:
            n: Number of items to increment
        """
        self.current = min(self.current + n, self.total)
        self._display()
    
    def _display(self) -> None:
        """Display the current progress."""
        if self.total == 0:
            percent = 100
        else:
            percent = int((self.current / self.total) * 100)
        
        if percent == self._last_percent and self.current < self.total:
            return
        
        self._last_percent = percent
        
        filled = int(self.width * self.current / self.total) if self.total > 0 else self.width
        bar = "=" * filled + "-" * (self.width - filled)
        status = "{} [{}/{}] {}%".format(self.description, self.current, self.total, percent)
        
        print("\r{} |{}| {}".format(status, bar, ""), end="", flush=True)
        
        if self.current >= self.total:
            print()
    
    def close(self) -> None:
        """Close the progress bar."""
        if self.current < self.total:
            self.current = self.total
            self._display()


"""Namespace-scoped Kubernetes resource types to collect."""
RESOURCE_TYPES = [
    "pods",
    "services",
    "deployments",
    "statefulsets",
    "daemonsets",
    "replicasets",
    "configmaps",
    "secrets",
    "persistentvolumeclaims",
    "endpoints",
    "ingress",
    "networkpolicies",
    "serviceaccounts",
    "roles",
    "rolebindings",
    "horizontalpodautoscalers",
    "poddisruptionbudgets",
    "events",
    "jobs",
    "cronjobs",
]

"""Cluster-scoped Kubernetes resource types to collect."""
CLUSTER_RESOURCE_TYPES = [
    "persistentvolumes",
    "clusterroles",
    "clusterrolebindings",
]


def get_kubectl_path(custom_path: Optional[str] = None) -> str:
    """
    Determine the kubectl binary path.
    
    Args:
        custom_path: Optional custom path to kubectl binary
        
    Returns:
        Path to kubectl binary
    """
    if custom_path:
        expanded = os.path.expanduser(custom_path)
        if os.path.exists(expanded):
            return expanded
        return custom_path
    
    common_paths = [
        os.path.expanduser("~/bin/kubectl"),
        "/usr/local/bin/kubectl",
        "/usr/bin/kubectl",
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    return "kubectl"


def get_kubeconfig_path(custom_path: Optional[str] = None) -> Optional[str]:
    """
    Determine the kubeconfig file path from various sources.
    
    Checks in order:
    1. Custom path provided via argument
    2. KUBECONFIG environment variable
    3. Default ~/.kube/config location
    
    Args:
        custom_path: Optional custom path to kubeconfig file
        
    Returns:
        Path to kubeconfig file, or None if not found
    """
    if custom_path:
        expanded = os.path.expanduser(custom_path)
        if os.path.exists(expanded):
            return expanded
        return expanded
    
    kubeconfig_env = os.environ.get("KUBECONFIG")
    if kubeconfig_env:
        expanded = os.path.expanduser(kubeconfig_env)
        if os.path.exists(expanded):
            return expanded
        return expanded
    
    default_path = os.path.expanduser("~/.kube/config")
    if os.path.exists(default_path):
        return default_path
    
    return None


def run_kubectl_command(
    kubectl_path: str,
    namespace: str,
    kubeconfig: Optional[str],
    resource_type: str,
    output_format: str = "json",
    additional_args: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Execute a kubectl command and return the result as JSON.
    
    Args:
        kubectl_path: Path to kubectl binary
        namespace: Kubernetes namespace
        kubeconfig: Path to kubeconfig file (optional)
        resource_type: Type of resource to get (e.g., "pods", "services")
        output_format: Output format ("json" or "yaml")
        additional_args: Additional kubectl arguments
        
    Returns:
        Dictionary containing the kubectl output, or empty dict on error
    """
    cmd = [kubectl_path]
    
    if kubeconfig:
        cmd.extend(["--kubeconfig", kubeconfig])
    
    cmd.extend(["-n", namespace])
    cmd.append("get")
    cmd.append(resource_type)
    
    if additional_args:
        cmd.extend(additional_args)
    
    cmd.extend(["-o", output_format])
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
            timeout=60
        )
        
        if result.returncode != 0:
            print("Warning: kubectl command failed: {}".format(" ".join(cmd)), file=sys.stderr)
            print("Error: {}".format(result.stderr), file=sys.stderr)
            return {}
        
        if output_format == "json":
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                print("Warning: Failed to parse JSON output for {}".format(resource_type), file=sys.stderr)
                return {}
        else:
            return {"yaml": result.stdout}
            
    except subprocess.TimeoutExpired:
        print("Warning: kubectl command timed out: {}".format(" ".join(cmd)), file=sys.stderr)
        return {}
    except Exception as e:
        print("Warning: Error running kubectl command: {}".format(e), file=sys.stderr)
        return {}


def get_node_details(
    kubectl_path: str,
    kubeconfig: Optional[str],
    node_name: str
) -> Dict[str, Any]:
    """
    Get detailed information about a specific node.
    
    Args:
        kubectl_path: Path to kubectl binary
        kubeconfig: Path to kubeconfig file (optional)
        node_name: Name of the node
        
    Returns:
        Dictionary containing node details
    """
    cmd = [kubectl_path]
    
    if kubeconfig:
        cmd.extend(["--kubeconfig", kubeconfig])
    
    cmd.extend(["get", "node", node_name, "-o", "json"])
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
            timeout=30
        )
        
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {}
    except Exception:
        pass
    
    return {}


def collect_namespace_resources(
    kubectl_path: str,
    namespace: str,
    kubeconfig: Optional[str],
    output_dir: Path
) -> None:
    """
    Collect all namespace-scoped resources.
    
    Args:
        kubectl_path: Path to kubectl binary
        namespace: Kubernetes namespace
        kubeconfig: Path to kubeconfig file (optional)
        output_dir: Directory to save collected data
    """
    print("Collecting namespace-scoped resources...")
    
    progress = ProgressBar(len(RESOURCE_TYPES), "Resources", width=40)
    
    for idx, resource_type in enumerate(RESOURCE_TYPES):
        progress.description = "Collecting {}".format(resource_type)
        progress.update(0)
        
        data = run_kubectl_command(
            kubectl_path,
            namespace,
            kubeconfig,
            resource_type,
            output_format="json"
        )
        
        if not data:
            continue
        
        resource_file = output_dir / "{}.json".format(resource_type)
        with open(resource_file, "w") as f:
            json.dump(data, f, indent=2)
        
        items = data.get("items", [])
        if items:
            resource_detail_dir = output_dir / "{}_details".format(resource_type)
            resource_detail_dir.mkdir(exist_ok=True)
            
            if len(items) > 5:
                item_progress = ProgressBar(len(items), "  Details", width=30)
            else:
                item_progress = None
            
            for item_idx, item in enumerate(items):
                metadata = item.get("metadata", {})
                resource_name = metadata.get("name", "unknown")
                
                detail_data = run_kubectl_command(
                    kubectl_path,
                    namespace,
                    kubeconfig,
                    resource_type,
                    output_format="yaml",
                    additional_args=[resource_name]
                )
                
                if detail_data:
                    detail_file = resource_detail_dir / "{}.yaml".format(resource_name)
                    with open(detail_file, "w") as f:
                        if isinstance(detail_data, dict) and "yaml" in detail_data:
                            f.write(detail_data["yaml"])
                        else:
                            json.dump(detail_data, f, indent=2)
                
                if item_progress:
                    item_progress.update(1)
            
            if item_progress:
                item_progress.close()
        
        progress.update(1)
    
    progress.close()


def collect_cluster_resources(
    kubectl_path: str,
    kubeconfig: Optional[str],
    output_dir: Path
) -> None:
    """
    Collect cluster-scoped resources (not namespace-specific).
    
    Args:
        kubectl_path: Path to kubectl binary
        kubeconfig: Path to kubeconfig file (optional)
        output_dir: Directory to save collected data
    """
    print("Collecting cluster-scoped resources...")
    
    cluster_dir = output_dir / "cluster_resources"
    cluster_dir.mkdir(exist_ok=True)
    
    progress = ProgressBar(len(CLUSTER_RESOURCE_TYPES), "Cluster resources", width=40)
    
    for resource_type in CLUSTER_RESOURCE_TYPES:
        progress.description = "Collecting {}".format(resource_type)
        progress.update(0)
        
        cmd = [kubectl_path]
        if kubeconfig:
            cmd.extend(["--kubeconfig", kubeconfig])
        cmd.extend(["get", resource_type, "-o", "json"])
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=False,
                timeout=60
            )
            
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    resource_file = cluster_dir / "{}.json".format(resource_type)
                    with open(resource_file, "w") as f:
                        json.dump(data, f, indent=2)
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass
        
        progress.update(1)
    
    progress.close()


def collect_node_information(
    kubectl_path: str,
    namespace: str,
    kubeconfig: Optional[str],
    output_dir: Path
) -> None:
    """
    Collect information about nodes where Impala pods are running.
    
    Args:
        kubectl_path: Path to kubectl binary
        namespace: Kubernetes namespace
        kubeconfig: Path to kubeconfig file (optional)
        output_dir: Directory to save collected data
    """
    print("Collecting node information...")
    
    pods_data = run_kubectl_command(
        kubectl_path,
        namespace,
        kubeconfig,
        "pods",
        output_format="json"
    )
    
    if not pods_data:
        return
    
    nodes_dir = output_dir / "nodes"
    nodes_dir.mkdir(exist_ok=True)
    
    nodes_seen = set()
    pods = pods_data.get("items", [])
    
    unique_nodes = []
    for pod in pods:
        spec = pod.get("spec", {})
        node_name = spec.get("nodeName")
        if node_name and node_name not in nodes_seen:
            nodes_seen.add(node_name)
            unique_nodes.append(node_name)
    
    if unique_nodes:
        node_progress = ProgressBar(len(unique_nodes), "Nodes", width=40)
        for node_name in unique_nodes:
            node_progress.description = "Node: {}".format(node_name[:40])
            node_progress.update(0)
            
            node_data = get_node_details(kubectl_path, kubeconfig, node_name)
            
            if node_data:
                node_file = nodes_dir / "{}.json".format(node_name)
                with open(node_file, "w") as f:
                    json.dump(node_data, f, indent=2)
            
            node_progress.update(1)
        node_progress.close()
    
    print("  - Collecting all cluster nodes...")
    cmd = [kubectl_path]
    if kubeconfig:
        cmd.extend(["--kubeconfig", kubeconfig])
    cmd.extend(["get", "nodes", "-o", "json"])
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
            timeout=60
        )
        
        if result.returncode == 0:
            try:
                all_nodes_data = json.loads(result.stdout)
                all_nodes_file = nodes_dir / "all_nodes.json"
                with open(all_nodes_file, "w") as f:
                    json.dump(all_nodes_data, f, indent=2)
            except json.JSONDecodeError:
                pass
    except Exception:
        pass


def collect_pod_logs(
    kubectl_path: str,
    namespace: str,
    kubeconfig: Optional[str],
    output_dir: Path,
    tail_lines: int = 100
) -> None:
    """
    Collect recent logs from all pods.
    
    Args:
        kubectl_path: Path to kubectl binary
        namespace: Kubernetes namespace
        kubeconfig: Path to kubeconfig file (optional)
        output_dir: Directory to save collected data
        tail_lines: Number of lines to tail from logs
    """
    print("Collecting pod logs (last {} lines)...".format(tail_lines))
    
    pods_data = run_kubectl_command(
        kubectl_path,
        namespace,
        kubeconfig,
        "pods",
        output_format="json"
    )
    
    if not pods_data:
        return
    
    logs_dir = output_dir / "pod_logs"
    logs_dir.mkdir(exist_ok=True)
    
    pods = pods_data.get("items", [])
    
    total_containers = 0
    for pod in pods:
        metadata = pod.get("metadata", {})
        status = pod.get("status", {})
        phase = status.get("phase", "")
        if phase not in ["Running", "Pending"]:
            continue
        spec = pod.get("spec", {})
        containers = spec.get("containers", [])
        total_containers += len(containers)
    
    if total_containers > 0:
        log_progress = ProgressBar(total_containers, "Pod logs", width=40)
    else:
        log_progress = None
    
    for pod in pods:
        metadata = pod.get("metadata", {})
        pod_name = metadata.get("name", "unknown")
        status = pod.get("status", {})
        
        phase = status.get("phase", "")
        if phase not in ["Running", "Pending"]:
            continue
        
        spec = pod.get("spec", {})
        containers = spec.get("containers", [])
        
        for container in containers:
            container_name = container.get("name", "default")
            
            if log_progress:
                log_progress.description = "Logs: {}/{}".format(container_name[:15], pod_name[:20])
            
            cmd = [kubectl_path]
            if kubeconfig:
                cmd.extend(["--kubeconfig", kubeconfig])
            cmd.extend(["-n", namespace, "logs", pod_name, "-c", container_name, "--tail={}".format(tail_lines)])
            
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    check=False,
                    timeout=30
                )
                
                log_file = logs_dir / "{}_{}.log".format(pod_name, container_name)
                with open(log_file, "w") as f:
                    if result.returncode == 0:
                        f.write(result.stdout)
                    else:
                        f.write("Error retrieving logs:\n{}".format(result.stderr))
            except Exception as e:
                log_file = logs_dir / "{}_{}.log".format(pod_name, container_name)
                with open(log_file, "w") as f:
                    f.write("Error: {}\n".format(str(e)))
            
            if log_progress:
                log_progress.update(1)
    
    if log_progress:
        log_progress.close()


def collect_describe_output(
    kubectl_path: str,
    namespace: str,
    kubeconfig: Optional[str],
    output_dir: Path
) -> None:
    """
    Collect 'kubectl describe' output for all resources.
    
    Args:
        kubectl_path: Path to kubectl binary
        namespace: Kubernetes namespace
        kubeconfig: Path to kubeconfig file (optional)
        output_dir: Directory to save collected data
    """
    print("Collecting 'kubectl describe' output...")
    
    describe_dir = output_dir / "describe"
    describe_dir.mkdir(exist_ok=True)
    
    progress = ProgressBar(len(RESOURCE_TYPES), "Describe", width=40)
    
    for resource_type in RESOURCE_TYPES:
        progress.description = "Describing {}".format(resource_type)
        progress.update(0)
        
        cmd = [kubectl_path]
        if kubeconfig:
            cmd.extend(["--kubeconfig", kubeconfig])
        cmd.extend(["-n", namespace, "describe", resource_type])
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=False,
                timeout=60
            )
            
            describe_file = describe_dir / "{}.txt".format(resource_type)
            with open(describe_file, "w") as f:
                if result.returncode == 0:
                    f.write(result.stdout)
                else:
                    f.write("Error: {}\n".format(result.stderr))
        except Exception as e:
            describe_file = describe_dir / "{}.txt".format(resource_type)
            with open(describe_file, "w") as f:
                f.write("Error: {}\n".format(str(e)))
        
        progress.update(1)
    
    progress.close()


def create_tar_archive(
    output_dir: Path,
    output_path: Optional[Path] = None
) -> Path:
    """
    Create a tar.gz archive with maximum compression of the output directory.
    
    Args:
        output_dir: Directory to archive
        output_path: Optional directory where to create the archive (default: same as output_dir)
        
    Returns:
        Path to the created archive file
    """
    archive_name = "{}.tar.gz".format(output_dir.name)
    
    if output_path:
        output_path.mkdir(parents=True, exist_ok=True)
        archive_path = output_path / archive_name
    else:
        archive_path = output_dir.parent / archive_name
    
    print("Creating compressed archive: {}".format(archive_path))
    
    file_count = sum(1 for _ in output_dir.rglob("*") if _.is_file())
    
    if file_count > 0:
        archive_progress = ProgressBar(file_count, "Archiving", width=40)
    else:
        archive_progress = None
    
    with tarfile.open(archive_path, "w:gz", compresslevel=9) as tar:
        for file_path in output_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(output_dir.parent)
                tar.add(file_path, arcname=arcname)
                if archive_progress:
                    archive_progress.description = "Archiving: {}".format(file_path.name[:30])
                    archive_progress.update(1)
    
    if archive_progress:
        archive_progress.close()
    
    archive_size = archive_path.stat().st_size
    size_mb = archive_size / (1024 * 1024)
    
    print("Archive created: {} ({:.2f} MB)".format(archive_path, size_mb))
    
    return archive_path


def run_cdp_command(
    command: List[str],
    timeout: int = 60
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Execute a CDP CLI command and return JSON output.
    
    Args:
        command: CDP CLI command as list of strings
        timeout: Command timeout in seconds
        
    Returns:
        Tuple of (json_data, error_message)
    """
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
            timeout=timeout
        )
        
        if result.returncode != 0:
            return None, result.stderr.strip()
        
        if not result.stdout.strip():
            return {}, None
        
        try:
            return json.loads(result.stdout), None
        except json.JSONDecodeError:
            return None, "Failed to parse JSON output"
            
    except subprocess.TimeoutExpired:
        return None, "Command timed out"
    except FileNotFoundError:
        return None, "cdp command not found. Please install CDP CLI."
    except Exception as e:
        return None, str(e)


def extract_environment_from_namespace(namespace: str) -> Optional[str]:
    """
    Extract environment name from Kubernetes namespace.
    
    CDW namespaces typically follow patterns like:
    - impala-{timestamp}-{id}
    - hive-{timestamp}-{id}
    
    Args:
        namespace: Kubernetes namespace
        
    Returns:
        Environment name if can be inferred, None otherwise
    """
    parts = namespace.split("-")
    if len(parts) >= 2:
        return None
    return None


def collect_cdp_cdw_information(
    namespace: str,
    output_dir: Path,
    cdp_profile: str = "default",
    environment_name: Optional[str] = None
) -> None:
    """
    Collect CDW information from CDP Control Plane using CDP CLI Beta.
    
    Matches Virtual Warehouses to the namespace pattern and collects:
    - CDW cluster details
    - Virtual Warehouses (especially Impala VWs matching the namespace)
    - Database Catalogs
    - Hue instances
    - Data Visualizations
    - Upgrade version information
    
    Args:
        namespace: Kubernetes namespace (used to find matching CDW resources)
        output_dir: Directory to save collected data
        cdp_profile: CDP CLI profile to use
        environment_name: Optional environment name (filters clusters to this environment)
    """
    print("Collecting CDP Control Plane information...")
    
    cdp_dir = output_dir / "cdp_control_plane"
    cdp_dir.mkdir(exist_ok=True)
    
    try:
        result = subprocess.run(
            ["cdp", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=10
        )
        if result.returncode != 0:
            print("  ⚠️  CDP CLI not found or not working. Skipping CDP collection.")
            return
    except FileNotFoundError:
        print("  ⚠️  CDP CLI Beta not found. Skipping CDP collection.")
        print("      Install with: pip3 install cdpcli-beta")
        print("      See: https://docs.cloudera.com/cdp-public-cloud/cloud/cli/topics/mc_beta_cdp_cli.html")
        return
    
    print("  - Listing CDW clusters...")
    clusters_cmd = ["cdp", "dw", "list-clusters", "--profile", cdp_profile, "--output", "json"]
    clusters_data, clusters_err = run_cdp_command(clusters_cmd)
    
    if not clusters_data:
        print("  ⚠️  Could not list CDW clusters: {}".format(clusters_err or "Unknown error"))
        return
    
    clusters = clusters_data.get("clusters", [])
    if not clusters:
        print("  ℹ️  No CDW clusters found")
        return
    
    # Filter clusters by environment name if provided
    # Match logic: environment name in environmentCrn OR in cluster name
    # This matches the logic used in the discovery tool
    if environment_name:
        print("  Filtering clusters for environment: {}".format(environment_name))
        filtered_clusters = []
        for cluster in clusters:
            env_crn = cluster.get("environmentCrn", "")
            cluster_name = cluster.get("name", "")
            
            if (env_crn and environment_name in env_crn) or \
               (cluster_name and environment_name in cluster_name):
                filtered_clusters.append(cluster)
        
        if not filtered_clusters:
            print("  ⚠️  No CDW clusters found for environment: {}".format(environment_name))
            print("  Available clusters: {}".format([c.get("name", "unknown") for c in clusters]))
            return
        
        clusters = filtered_clusters
        print("  Found {} CDW cluster(s) in environment {}".format(len(clusters), environment_name))
    else:
        print("  Found {} CDW cluster(s) (no environment filter applied)".format(len(clusters)))
    
    clusters_file = cdp_dir / "cdw_clusters_list.json"
    clusters_data_filtered = {"clusters": clusters}
    with open(clusters_file, "w") as f:
        json.dump(clusters_data_filtered, f, indent=2)
    
    matching_cluster = None
    matching_vw_id = None
    
    namespace_parts = namespace.split("-")
    potential_vw_id = None
    if len(namespace_parts) >= 3:
        potential_vw_id = namespace_parts[-1]
    
    print("  - Searching for Virtual Warehouse matching namespace: {}".format(namespace))
    for cluster in clusters:
        cluster_id = cluster.get("id", "")
        cluster_name = cluster.get("name", "")
        
        vws_test_cmd = ["cdp", "dw", "list-vws", "--cluster-id", cluster_id,
                       "--profile", cdp_profile, "--output", "json"]
        vws_test_data, _ = run_cdp_command(vws_test_cmd, timeout=30)
        
        if vws_test_data:
            vws_test = vws_test_data.get("vws", [])
            for vw in vws_test:
                vw_id = vw.get("id", "")
                vw_name = vw.get("name", "")
                vw_type = vw.get("vwType", "").lower()
                
                if vw_type != "impala":
                    continue
                
                if (namespace in vw_id or vw_id in namespace or
                    namespace in vw_name or vw_name in namespace or
                    (potential_vw_id and potential_vw_id in vw_id)):
                    matching_cluster = cluster
                    matching_vw_id = vw_id
                    print("  ✓ Found matching Impala VW '{}' (ID: {}) in cluster '{}'".format(
                        vw_name, vw_id, cluster_name))
                    break
        
        if matching_cluster:
            break
    
    if not matching_cluster:
        for cluster in clusters:
            cluster_id = cluster.get("id", "")
            cluster_name = cluster.get("name", "")
            
            if namespace in cluster_id or namespace in cluster_name:
                matching_cluster = cluster
                print("  ℹ️  Matched cluster by ID/name pattern: {}".format(cluster_name))
                break
    
    if not matching_cluster and clusters:
        matching_cluster = clusters[0]
        print("  ℹ️  No VW match found, using first cluster from environment: {}".format(
            matching_cluster.get("name", "unknown")))
        print("     (Namespace '{}' may not match any VW identifier)".format(namespace))
    
    if not matching_cluster:
        print("  ⚠️  Could not determine matching CDW cluster")
        return
    
    cluster_id = matching_cluster.get("id")
    cluster_name = matching_cluster.get("name", cluster_id)
    
    print("  - Collecting details for cluster: {}".format(cluster_name))
    
    describe_cmd = ["cdp", "dw", "describe-cluster", "--cluster-id", cluster_id, 
                    "--profile", cdp_profile, "--output", "json"]
    cluster_data, describe_err = run_cdp_command(describe_cmd)
    
    if cluster_data:
        cluster_file = cdp_dir / "cdw_cluster_{}.json".format(cluster_name)
        with open(cluster_file, "w") as f:
            json.dump(cluster_data, f, indent=2)
    else:
        print("  ⚠️  Could not describe cluster: {}".format(describe_err or "Unknown error"))
    
    print("  - Listing Virtual Warehouses...")
    vws_cmd = ["cdp", "dw", "list-vws", "--cluster-id", cluster_id,
               "--profile", cdp_profile, "--output", "json"]
    vws_data, vws_err = run_cdp_command(vws_cmd)
    
    if vws_data:
        vws_file = cdp_dir / "virtual_warehouses_list.json"
        with open(vws_file, "w") as f:
            json.dump(vws_data, f, indent=2)
        
        vws = vws_data.get("vws", [])
        print("  Found {} Virtual Warehouse(s)".format(len(vws)))
        
        impala_vws = [vw for vw in vws if vw.get("vwType", "").lower() == "impala"]
        
        if matching_vw_id:
            matching_vw = [vw for vw in impala_vws if vw.get("id") == matching_vw_id]
            if matching_vw:
                print("  ✓ Collecting details for matching Impala VW: {}".format(
                    matching_vw[0].get("name", "unknown")))
                impala_vws = matching_vw
            else:
                print("  Found {} Impala Virtual Warehouse(s)".format(len(impala_vws)))
        elif impala_vws and namespace:
            namespace_matched_vws = []
            for vw in impala_vws:
                vw_id = vw.get("id", "")
                vw_name = vw.get("name", "")
                
                if (namespace in vw_id or vw_id in namespace or
                    namespace in vw_name or vw_name in namespace):
                    namespace_matched_vws.append(vw)
            
            if namespace_matched_vws:
                print("  Found {} Impala VW(s) matching namespace pattern".format(len(namespace_matched_vws)))
                impala_vws = namespace_matched_vws
            else:
                print("  ℹ️  No Impala VWs match namespace pattern, collecting all {} Impala VW(s)".format(len(impala_vws)))
        else:
            print("  Found {} Impala Virtual Warehouse(s)".format(len(impala_vws)))
        
        if impala_vws:
            vws_detail_dir = cdp_dir / "virtual_warehouses"
            vws_detail_dir.mkdir(exist_ok=True)
            
            progress = ProgressBar(len(impala_vws), "VW details", width=40)
            
            for vw in impala_vws:
                vw_id = vw.get("id")
                vw_name = vw.get("name", vw_id)
                
                progress.description = "VW: {}".format(vw_name[:30])
                progress.update(0)
                
                vw_describe_cmd = ["cdp", "dw", "describe-vw", "--cluster-id", cluster_id,
                                  "--vw-id", vw_id, "--profile", cdp_profile, "--output", "json"]
                vw_data, vw_err = run_cdp_command(vw_describe_cmd)
                
                if vw_data:
                    vw_file = vws_detail_dir / "vw_{}.json".format(vw_name)
                    with open(vw_file, "w") as f:
                        json.dump(vw_data, f, indent=2)
                
                upgrade_cmd = ["cdp", "dw", "get-upgrade-vw-versions", "--cluster-id", cluster_id,
                              "--vw-id", vw_id, "--profile", cdp_profile, "--output", "json"]
                upgrade_data, upgrade_err = run_cdp_command(upgrade_cmd)
                
                if upgrade_data:
                    upgrade_file = vws_detail_dir / "vw_{}_upgrade_versions.json".format(vw_name)
                    with open(upgrade_file, "w") as f:
                        json.dump(upgrade_data, f, indent=2)
                
                progress.update(1)
            
            progress.close()
    else:
        print("  ⚠️  Could not list VWs: {}".format(vws_err or "Unknown error"))
    
    print("  - Listing Database Catalogs...")
    dbcs_cmd = ["cdp", "dw", "list-dbcs", "--cluster-id", cluster_id,
                "--profile", cdp_profile, "--output", "json"]
    dbcs_data, dbcs_err = run_cdp_command(dbcs_cmd)
    
    if dbcs_data:
        dbcs_file = cdp_dir / "database_catalogs_list.json"
        with open(dbcs_file, "w") as f:
            json.dump(dbcs_data, f, indent=2)
        
        dbcs = dbcs_data.get("dbcs", [])
        print("  Found {} Database Catalog(s)".format(len(dbcs)))
        
        if dbcs:
            dbcs_detail_dir = cdp_dir / "database_catalogs"
            dbcs_detail_dir.mkdir(exist_ok=True)
            
            progress = ProgressBar(len(dbcs), "DBC details", width=40)
            
            for dbc in dbcs:
                dbc_id = dbc.get("id")
                dbc_name = dbc.get("name", dbc_id)
                
                progress.description = "DBC: {}".format(dbc_name[:30])
                progress.update(0)
                
                dbc_describe_cmd = ["cdp", "dw", "describe-dbc", "--cluster-id", cluster_id,
                                   "--dbc-id", dbc_id, "--profile", cdp_profile, "--output", "json"]
                dbc_data, dbc_err = run_cdp_command(dbc_describe_cmd)
                
                if dbc_data:
                    dbc_file = dbcs_detail_dir / "dbc_{}.json".format(dbc_name)
                    with open(dbc_file, "w") as f:
                        json.dump(dbc_data, f, indent=2)
                
                upgrade_cmd = ["cdp", "dw", "get-upgrade-dbc-versions", "--cluster-id", cluster_id,
                              "--dbc-id", dbc_id, "--profile", cdp_profile, "--output", "json"]
                upgrade_data, upgrade_err = run_cdp_command(upgrade_cmd)
                
                if upgrade_data:
                    upgrade_file = dbcs_detail_dir / "dbc_{}_upgrade_versions.json".format(dbc_name)
                    with open(upgrade_file, "w") as f:
                        json.dump(upgrade_data, f, indent=2)
                
                progress.update(1)
            
            progress.close()
    else:
        print("  ⚠️  Could not list DBCs: {}".format(dbcs_err or "Unknown error"))
    
    print("  - Listing Hue instances...")
    hues_cmd = ["cdp", "dw", "list-hues", "--cluster-id", cluster_id,
                "--profile", cdp_profile, "--output", "json"]
    hues_data, hues_err = run_cdp_command(hues_cmd)
    
    if hues_data:
        hues_file = cdp_dir / "hue_instances_list.json"
        with open(hues_file, "w") as f:
            json.dump(hues_data, f, indent=2)
        hues = hues_data.get("hues", [])
        print("  Found {} Hue instance(s)".format(len(hues)))
    else:
        if hues_err:
            print("  ℹ️  Could not list Hue instances: {}".format(hues_err))
    
    print("  - Listing Data Visualizations...")
    dvizs_cmd = ["cdp", "dw", "list-data-visualizations", "--cluster-id", cluster_id,
                 "--profile", cdp_profile, "--output", "json"]
    dvizs_data, dvizs_err = run_cdp_command(dvizs_cmd)
    
    if dvizs_data:
        dvizs_file = cdp_dir / "data_visualizations_list.json"
        with open(dvizs_file, "w") as f:
            json.dump(dvizs_data, f, indent=2)
        dvizs = dvizs_data.get("dataVisualizations", [])
        if dvizs:
            print("  Found {} Data Visualization(s)".format(len(dvizs)))
    else:
        if dvizs_err:
            print("  ℹ️  Could not list Data Visualizations: {}".format(dvizs_err))


def create_summary_report(
    namespace: str,
    output_dir: Path,
    kubectl_path: str,
    kubeconfig: Optional[str]
) -> None:
    """
    Create a summary report of the collected information.
    
    Args:
        namespace: Kubernetes namespace
        output_dir: Directory containing collected data
        kubectl_path: Path to kubectl binary used
        kubeconfig: Path to kubeconfig file used
    """
    print("Generating summary report...")
    
    summary_file = output_dir / "SUMMARY.txt"
    
    with open(summary_file, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("CDW Impala Deployment Configuration Summary\n")
        f.write("=" * 80 + "\n\n")
        f.write("Namespace: {}\n".format(namespace))
        f.write("Collection Time: {}\n".format(datetime.now().isoformat()))
        f.write("Kubectl Path: {}\n".format(kubectl_path))
        f.write("Kubeconfig: {}\n".format(kubeconfig or "default"))
        f.write("\n" + "=" * 80 + "\n\n")
        
        f.write("Namespace-Scoped Resource Counts:\n")
        f.write("-" * 80 + "\n")
        
        for resource_type in RESOURCE_TYPES:
            resource_file = output_dir / "{}.json".format(resource_type)
            if resource_file.exists():
                try:
                    with open(resource_file, "r") as rf:
                        data = json.load(rf)
                        items = data.get("items", [])
                        count = len(items)
                        f.write("  {}: {}\n".format(resource_type, count))
                except Exception:
                    f.write("  {}: Error reading file\n".format(resource_type))
        
        cluster_dir = output_dir / "cluster_resources"
        if cluster_dir.exists():
            f.write("\nCluster-Scoped Resource Counts:\n")
            f.write("-" * 80 + "\n")
            
            for resource_type in CLUSTER_RESOURCE_TYPES:
                resource_file = cluster_dir / "{}.json".format(resource_type)
                if resource_file.exists():
                    try:
                        with open(resource_file, "r") as rf:
                            data = json.load(rf)
                            items = data.get("items", [])
                            count = len(items)
                            f.write("  {}: {}\n".format(resource_type, count))
                    except Exception:
                        f.write("  {}: Error reading file\n".format(resource_type))
        
        f.write("\n" + "=" * 80 + "\n\n")
        f.write("Directory Structure:\n")
        f.write("-" * 80 + "\n")
        f.write("  - <resource_type>.json: List of namespace-scoped resources\n")
        f.write("  - <resource_type>_details/: Detailed YAML for each resource\n")
        f.write("  - cluster_resources/: Cluster-scoped resources (PVs, ClusterRoles, etc.)\n")
        f.write("  - nodes/: Node information\n")
        f.write("  - pod_logs/: Recent pod logs\n")
        f.write("  - describe/: kubectl describe output\n")
        f.write("\n")


def main() -> int:
    """
    Main function to orchestrate the collection of Impala deployment information.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        description="Collect comprehensive Kubernetes resource information for CDW Impala deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with namespace
  python cdw_impala_getconfigs.py --ns impala-1765804600-725v
  
  # With custom kubectl and kubeconfig
  python cdw_impala_getconfigs.py --ns impala-1765804600-725v \\
      --kubectl ~/bin/kubectl \\
      --kubeconfig ~/k8s/my-cluster.yml
  
  # Using environment variables
  export KUBECONFIG=~/k8s/my-cluster.yml
  python cdw_impala_getconfigs.py --ns impala-1765804600-725v
        """
    )
    
    parser.add_argument(
        "--ns",
        "--namespace",
        dest="namespace",
        required=True,
        help="Kubernetes namespace containing the Impala deployment"
    )
    
    parser.add_argument(
        "--kubectl",
        dest="kubectl_path",
        default=None,
        help="Path to kubectl binary (default: ~/bin/kubectl or PATH)"
    )
    
    parser.add_argument(
        "--kubeconfig",
        dest="kubeconfig_path",
        default=None,
        help="Path to kubeconfig file (default: KUBECONFIG env var or ~/.kube/config)"
    )
    
    parser.add_argument(
        "--log-lines",
        type=int,
        default=100,
        help="Number of log lines to collect per pod (default: 100)"
    )
    
    parser.add_argument(
        "--skip-logs",
        action="store_true",
        help="Skip collecting pod logs (faster execution)"
    )
    
    parser.add_argument(
        "--skip-describe",
        action="store_true",
        help="Skip collecting kubectl describe output (faster execution)"
    )
    
    parser.add_argument(
        "--output",
        dest="output_path",
        default=None,
        help="Directory path where to create the output bundle (default: current directory)"
    )
    
    parser.add_argument(
        "--enable-cdp",
        action="store_true",
        help="Enable CDP CLI collection to gather information from Cloudera Control Plane"
    )
    
    parser.add_argument(
        "--cdp-profile",
        dest="cdp_profile",
        default="default",
        help="CDP CLI profile to use (default: default)"
    )
    
    parser.add_argument(
        "--environment-name",
        dest="environment_name",
        default=None,
        help="CDP environment name (filters CDW clusters to only this environment)"
    )
    
    args = parser.parse_args()
    
    kubectl_path = get_kubectl_path(args.kubectl_path)
    kubeconfig = get_kubeconfig_path(args.kubeconfig_path)
    
    try:
        test_cmd = [kubectl_path, "version", "--client"]
        if kubeconfig:
            test_cmd.extend(["--kubeconfig", kubeconfig])
        result = subprocess.run(
            test_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=10
        )
        if result.returncode != 0:
            print("Error: kubectl is not working properly", file=sys.stderr)
            print("Error output: {}".format(result.stderr), file=sys.stderr)
            return 1
    except FileNotFoundError:
        print("Error: kubectl not found at: {}".format(kubectl_path), file=sys.stderr)
        return 1
    except Exception as e:
        print("Error: Failed to verify kubectl: {}".format(e), file=sys.stderr)
        return 1
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir_name = "{}_{}".format(args.namespace, timestamp)
    
    if args.output_path:
        output_base = Path(os.path.expanduser(args.output_path))
        output_base.mkdir(parents=True, exist_ok=True)
        output_dir = output_base / output_dir_name
    else:
        output_dir = Path(output_dir_name)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("CDW Impala Deployment Configuration Collector")
    print("=" * 80)
    print("Namespace: {}".format(args.namespace))
    print("Output Directory: {}".format(output_dir.absolute()))
    print("Kubectl: {}".format(kubectl_path))
    print("Kubeconfig: {}".format(kubeconfig or "default"))
    print("=" * 80)
    print()
    
    try:
        total_steps = 4
        if not args.skip_logs:
            total_steps += 1
        if not args.skip_describe:
            total_steps += 1
        if args.enable_cdp:
            total_steps += 1
        total_steps += 1
        
        overall_progress = ProgressBar(total_steps, "Overall progress", width=50)
        current_step = 0
        
        collect_namespace_resources(kubectl_path, args.namespace, kubeconfig, output_dir)
        current_step += 1
        overall_progress.update(1)
        print()
        
        collect_cluster_resources(kubectl_path, kubeconfig, output_dir)
        current_step += 1
        overall_progress.update(1)
        print()
        
        collect_node_information(kubectl_path, args.namespace, kubeconfig, output_dir)
        current_step += 1
        overall_progress.update(1)
        print()
        
        if not args.skip_logs:
            collect_pod_logs(kubectl_path, args.namespace, kubeconfig, output_dir, args.log_lines)
            current_step += 1
            overall_progress.update(1)
            print()
        
        if not args.skip_describe:
            collect_describe_output(kubectl_path, args.namespace, kubeconfig, output_dir)
            current_step += 1
            overall_progress.update(1)
            print()
        
        if args.enable_cdp:
            overall_progress.description = "CDP Control Plane"
            overall_progress.update(0)
            collect_cdp_cdw_information(
                args.namespace,
                output_dir,
                args.cdp_profile,
                args.environment_name
            )
            overall_progress.update(1)
            print()
        
        overall_progress.description = "Generating summary"
        overall_progress.update(0)
        create_summary_report(args.namespace, output_dir, kubectl_path, kubeconfig)
        overall_progress.update(1)
        
        print()
        output_base_path = Path(os.path.expanduser(args.output_path)) if args.output_path else None
        archive_path = create_tar_archive(output_dir, output_base_path)
        overall_progress.update(1)
        overall_progress.close()
        
        print("=" * 80)
        print("Collection complete!")
        print("Output directory: {}".format(output_dir.absolute()))
        print("Archive: {}".format(archive_path.absolute()))
        print("=" * 80)
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\nCollection interrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print("Error during collection: {}".format(e), file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
