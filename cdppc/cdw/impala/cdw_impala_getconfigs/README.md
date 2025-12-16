# CDW Impala Deployment Configuration Collector

A comprehensive Python script to collect and analyze all Kubernetes resources associated with a CDW Impala deployment in a given namespace. This tool performs deep analysis of pods, services, deployments, statefulsets, configmaps, secrets, persistent volumes, nodes, and all other relevant Kubernetes infrastructure components.

## Features

### Comprehensive Resource Collection

The script collects detailed information about:

**Namespace-Scoped Resources:**

- Pods (with detailed YAML)
- Services (ClusterIP, LoadBalancer, NodePort)
- Deployments
- StatefulSets
- DaemonSets
- ReplicaSets
- ConfigMaps
- Secrets
- PersistentVolumeClaims
- Endpoints
- Ingress resources
- NetworkPolicies
- ServiceAccounts
- Roles and RoleBindings
- HorizontalPodAutoscalers
- PodDisruptionBudgets
- Events
- Jobs and CronJobs

**Cluster-Scoped Resources:**

- PersistentVolumes
- ClusterRoles
- ClusterRoleBindings

**Additional Information:**

- Node details (for nodes running Impala pods)
- Pod logs (configurable number of lines)
- `kubectl describe` output for all resources
- Summary report with resource counts

**CDP Control Plane Information (Optional):**

When `--enable-cdp` is used, the script also collects information from the Cloudera Control Plane using CDP CLI:

- CDW cluster details
- Virtual Warehouses (VWs) - especially Impala VWs
- Database Catalogs (DBCs)
- Hue instances
- Data Visualizations
- Upgrade version information for VWs and DBCs

### Output Organization

All collected data is organized in a timestamped directory with the following structure:

```
{namespace}_{timestamp}/
├── SUMMARY.txt                    # Summary report
├── pods.json                      # List of all pods
├── pods_details/                  # Detailed YAML for each pod
│   ├── coordinator-0.yaml
│   ├── huebackend-0.yaml
│   └── ...
├── services.json
├── services_details/
├── configmaps.json
├── configmaps_details/
├── cluster_resources/             # Cluster-scoped resources
│   ├── persistentvolumes.json
│   ├── clusterroles.json
│   └── clusterrolebindings.json
├── nodes/                         # Node information
│   ├── node-name-1.json
│   ├── node-name-2.json
│   └── all_nodes.json
├── pod_logs/                      # Recent pod logs
│   ├── coordinator-0_impalad-coordinator.log
│   └── ...
├── describe/                      # kubectl describe output
│   ├── pods.txt
│   ├── services.txt
│   └── ...
└── cdp_control_plane/             # CDP Control Plane information (if --enable-cdp)
    ├── cdw_clusters_list.json
    ├── cdw_cluster_{name}.json
    ├── virtual_warehouses_list.json
    ├── virtual_warehouses/
    │   ├── vw_{name}.json
    │   └── vw_{name}_upgrade_versions.json
    ├── database_catalogs_list.json
    ├── database_catalogs/
    │   ├── dbc_{name}.json
    │   └── dbc_{name}_upgrade_versions.json
    ├── hue_instances_list.json
    └── data_visualizations_list.json
```

## Requirements

- Python 3.6 or higher
- `kubectl` binary (accessible via PATH or specified path)
- Kubernetes cluster access (via kubeconfig file)
- Appropriate RBAC permissions to read resources in the target namespace
- **CDP CLI Beta** (optional, required only if using `--enable-cdp`):
  - Install with: `pip3 install cdpcli-beta`
  - Configure with: `cdp configure` (see [CDP CLI Beta Installation](https://docs.cloudera.com/cdp-public-cloud/cloud/cli/topics/mc_beta_cdp_cli.html))
  - Must have access to the CDW cluster in the Control Plane
  - **Note**: Do not install both standard and beta CLIs in the same Python environment

## Installation

No installation required. The script is self-contained and can be run directly.

## Usage

### Complete Example (Recommended)

For comprehensive data collection with all features enabled, use this example:

```bash
python3 cdw_impala_getconfigs.py \
    --ns impala-1765804600-725v \
    --log-lines 500 \
    --kubectl ~/kubectl \
    --kubeconfig ~/k8s/jdga-sbx-2-cdp-env-env-dldbc4.yml \
    --output /tmp/ \
    --enable-cdp \
    --cdp-profile default \
    --environment-name jdga-sbx-2-cdp-env
```

**What this command does:**

- ✅ Collects all Kubernetes resources from namespace `impala-1765804600-725v`
- ✅ Gathers 500 lines of logs from each pod container
- ✅ Uses custom kubectl and kubeconfig paths
- ✅ Saves output to `/tmp/` directory
- ✅ Collects CDP Control Plane information via CDP CLI Beta
- ✅ Filters CDW clusters to only those in environment `jdga-sbx-2-cdp-env`
- ✅ Matches Virtual Warehouses to the namespace pattern
- ✅ Creates a compressed tar.gz archive with maximum compression

**Output:**

- Directory: `/tmp/impala-1765804600-725v_{timestamp}/`
- Archive: `/tmp/impala-1765804600-725v_{timestamp}.tar.gz`

### Basic Usage

```bash
python3 cdw_impala_getconfigs.py --ns impala-1765804600-725v
```

### With Custom kubectl and kubeconfig

```bash
python3 cdw_impala_getconfigs.py \
    --ns impala-1765804600-725v \
    --kubectl ~/bin/kubectl \
    --kubeconfig ~/k8s/my-cluster.yml
```

### Using Environment Variables

```bash
export KUBECONFIG=~/k8s/my-cluster.yml
python3 cdw_impala_getconfigs.py --ns impala-1765804600-725v
```

### Customizing Log Collection

```bash
# Collect last 500 lines of logs per pod
python3 cdw_impala_getconfigs.py --ns impala-1765804600-725v --log-lines 500

# Skip log collection for faster execution
python3 cdw_impala_getconfigs.py --ns impala-1765804600-725v --skip-logs

# Skip describe output for faster execution
python3 cdw_impala_getconfigs.py --ns impala-1765804600-725v --skip-describe
```

### Specifying Output Location

```bash
# Create output bundle in a specific directory
python3 cdw_impala_getconfigs.py --ns impala-1765804600-725v --output /tmp/impala_collections

# The script will create both the directory and a compressed tar.gz archive
```

### Enabling CDP Control Plane Collection

```bash
# Collect information from CDP Control Plane using CDP CLI Beta
python3 cdw_impala_getconfigs.py --ns impala-1765804600-725v --enable-cdp

# With specific CDP profile
python3 cdw_impala_getconfigs.py --ns impala-1765804600-725v --enable-cdp --cdp-profile production

# With explicit environment name (filters to only that environment's CDW clusters)
python3 cdw_impala_getconfigs.py --ns impala-1765804600-725v --enable-cdp --environment-name jdga-sbx-2-cdp-env
```

**How Namespace Matching Works:**

The script uses the Kubernetes namespace to identify the corresponding Virtual Warehouse (VW) in the CDP Control Plane:

1. **Environment Filtering**: If `--environment-name` is provided, only CDW clusters in that environment are considered
2. **VW Matching**: The script searches for Impala Virtual Warehouses whose ID or name matches patterns in the namespace
3. **Cluster Mapping**: Once a matching VW is found, the script collects information from its parent CDW cluster
4. **Namespace Pattern**: Namespaces typically follow patterns like `impala-{timestamp}-{vw-id}` where the last part matches the VW identifier

This ensures that the collected Control Plane information corresponds to the same Impala deployment as the Kubernetes namespace.

## Command-Line Arguments

| Argument              | Description                                                     | Required | Default                                  |
| --------------------- | --------------------------------------------------------------- | -------- | ---------------------------------------- |
| `--ns`, `--namespace` | Kubernetes namespace containing the Impala deployment           | Yes      | -                                        |
| `--kubectl`           | Path to kubectl binary                                          | No       | `~/bin/kubectl` or PATH                  |
| `--kubeconfig`        | Path to kubeconfig file                                         | No       | `KUBECONFIG` env var or `~/.kube/config` |
| `--log-lines`         | Number of log lines to collect per pod                          | No       | 100                                      |
| `--skip-logs`         | Skip collecting pod logs (faster execution)                     | No       | False                                    |
| `--skip-describe`     | Skip collecting kubectl describe output (faster execution)      | No       | False                                    |
| `--output`            | Directory path where to create the output bundle                | No       | Current directory                        |
| `--enable-cdp`        | Enable CDP CLI collection from Cloudera Control Plane           | No       | False                                    |
| `--cdp-profile`       | CDP CLI profile to use                                          | No       | default                                  |
| `--environment-name`  | CDP environment name (filters CDW clusters to this environment) | No       | All environments                         |

## Environment Variables

The script respects the following environment variables:

- **KUBECONFIG**: Path to kubeconfig file (if `--kubeconfig` is not provided)
- **AWS_PROFILE**: Can be used indirectly if kubeconfig references AWS credentials

## kubectl Path Resolution

The script attempts to find kubectl in the following order:

1. Custom path provided via `--kubectl` argument
2. `~/bin/kubectl`
3. `/usr/local/bin/kubectl`
4. `/usr/bin/kubectl`
5. `kubectl` in system PATH

## kubeconfig Path Resolution

The script attempts to find kubeconfig in the following order:

1. Custom path provided via `--kubeconfig` argument
2. `KUBECONFIG` environment variable
3. `~/.kube/config` (default Kubernetes location)

## Output

### Output Structure

The script creates:

1. **Directory**: A timestamped directory containing all collected data
2. **Archive**: A compressed `tar.gz` file with maximum compression (level 9) for easy sharing

The archive is automatically created after collection completes and is placed in the same location as the output directory (or in the directory specified by `--output`).

### Summary Report

The script generates a `SUMMARY.txt` file containing:

- Collection metadata (namespace, timestamp, kubectl/kubeconfig paths)
- Resource counts for all collected resource types
- Directory structure overview

### Resource Files

Each resource type is collected in two formats:

1. **JSON list**: `{resource_type}.json` - Contains the full list of resources
2. **Detailed YAML**: `{resource_type}_details/{resource_name}.yaml` - Individual resource details

### Log Files

Pod logs are collected for all containers in running pods and stored in:

- `pod_logs/{pod_name}_{container_name}.log`

### Archive Compression

The script automatically creates a `tar.gz` archive with maximum compression (level 9) to minimize file size. The archive contains the entire output directory and can be easily shared or transferred.

Archive naming: `{namespace}_{timestamp}.tar.gz`

## Use Cases

### Troubleshooting

Collect comprehensive deployment information for troubleshooting:

```bash
python3 cdw_impala_getconfigs.py --ns impala-1765804600-725v
```

### Configuration Analysis

Analyze all configuration maps and secrets:

```bash
python3 cdw_impala_getconfigs.py --ns impala-1765804600-725v --skip-logs
```

### Performance Investigation

Collect resource information and recent logs:

```bash
python3 cdw_impala_getconfigs.py --ns impala-1765804600-725v --log-lines 1000
```

### Quick Resource Inventory

Fast collection without logs or describe output:

```bash
python3 cdw_impala_getconfigs.py --ns impala-1765804600-725v --skip-logs --skip-describe
```

### Creating Archives for Sharing

Create a compressed bundle in a specific location:

```bash
python3 cdw_impala_getconfigs.py --ns impala-1765804600-725v --output ~/impala_snapshots
```

This will create both the directory and a compressed `tar.gz` archive ready for sharing.

### Complete Collection with CDP Control Plane

Collect both Kubernetes and Control Plane information with comprehensive options:

```bash
python3 cdw_impala_getconfigs.py \
    --ns impala-1765804600-725v \
    --log-lines 500 \
    --kubectl ~/kubectl \
    --kubeconfig ~/k8s/jdga-sbx-2-cdp-env-env-dldbc4.yml \
    --output /tmp/ \
    --enable-cdp \
    --cdp-profile default \
    --environment-name jdga-sbx-2-cdp-env
```

This provides a complete picture of the deployment from both the Kubernetes cluster and the Cloudera Control Plane, including:

- All Kubernetes resources (pods, services, configmaps, secrets, etc.)
- Extended pod logs (500 lines per container)
- Node information
- kubectl describe output
- CDW cluster details
- Virtual Warehouses (especially Impala VWs matching the namespace)
- Database Catalogs
- Hue instances and Data Visualizations
- Upgrade version information
- Compressed archive for easy sharing

## Example Output

```
================================================================================
CDW Impala Deployment Configuration Collector
================================================================================
Namespace: impala-1765804600-725v
Output Directory: /path/to/impala-1765804600-725v_20251203_143022
Kubectl: ~/bin/kubectl
Kubeconfig: ~/k8s/jdga-sbx-1-cdp-env-env-rzks89.yml
================================================================================

Collecting namespace-scoped resources...
  - Collecting pods...
  - Collecting services...
  - Collecting deployments...
  ...

Collecting cluster-scoped resources...
  - Collecting persistentvolumes...
  ...

Collecting node information...
  - Collecting details for node: ip-10-0-1-100.ec2.internal
  ...

Collecting pod logs (last 100 lines)...
  ...

Generating summary report...

================================================================================
Collection complete!
Output directory: /path/to/impala-1765804600-725v_20251203_143022
================================================================================
```

## Error Handling

The script includes comprehensive error handling:

- **kubectl not found**: Exits with error message
- **kubectl not working**: Validates kubectl before collection
- **Resource access errors**: Continues with other resources, logs warnings
- **Timeout protection**: 60-second timeout for kubectl commands
- **Interrupt handling**: Gracefully handles Ctrl+C

## Python Compatibility

The script is compatible with Python 3.6 and higher. It uses:

- `.format()` for string formatting (Python 3.6 compatible)
- Standard library modules only (no external dependencies)
- Type hints (optional, ignored in Python 3.6)

## Best Practices

1. **Run during stable periods**: Collection can take several minutes for large deployments
2. **Review SUMMARY.txt first**: Get an overview before diving into details
3. **Archive output directories**: Keep historical snapshots for comparison
4. **Use --skip-logs for quick checks**: Faster execution when logs aren't needed
5. **Check RBAC permissions**: Ensure you have read access to all resources

## Troubleshooting

### kubectl not found

```bash
# Specify kubectl path explicitly
python3 cdw_impala_getconfigs.py --ns <namespace> --kubectl /path/to/kubectl
```

### Permission denied errors

Ensure your kubeconfig has appropriate RBAC permissions:

```bash
kubectl auth can-i get pods --namespace <namespace>
```

### Timeout errors

For very large deployments, some commands may timeout. The script will continue with other resources.

### Missing resources

Some resource types may not exist in your namespace. The script handles this gracefully and continues.

## License

This script is provided as-is for internal use.
