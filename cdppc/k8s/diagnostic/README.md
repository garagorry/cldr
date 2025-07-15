# Kubernetes Cluster Diagnostic Collector

This tool collects essential diagnostics from a Kubernetes cluster for troubleshooting, audits, or support cases. The outputs are saved to a timestamped directory and compressed into a `.tar.gz` archive for easy sharing.

---

## 🔧 Requirements

- Python 3.6+
- `kubectl` installed and configured
- Access to a valid `kubeconfig` file for the target cluster

---

## 🚀 Usage

### Basic Command

```bash
python3 k8s_cluster_diagnostic.py --kubeconfig /path/to/kubeconfig
```

### Optional: Custom Output Directory

```bash
python3 k8s_cluster_diagnostic.py --kubeconfig /path/to/kubeconfig --output-dir /tmp/k8s-support
```

- If `--output-dir` is not specified, the default location will be:

  ```
  /var/tmp/<cluster-name>-<timestamp>
  ```

- The output directory is automatically archived as:

  ```
  <output-dir>.tar.gz
  ```

---

## 📂 Collected Information

The following resources are collected from the cluster:

- Cluster config (`kubectl config view`)
- Nodes, Pods (with wide output)
- Namespaces, Services
- Deployments, DaemonSets, ReplicaSets
- Persistent Volumes (PV) and Claims (PVC)
- Events across all namespaces
- All ConfigMaps and their descriptions
- Full `kubectl cluster-info dump`

Each resource is saved into its own file under the output directory.

---

## 📦 Example Output

```
/var/tmp/my-cluster-20250715-103001/
├── my-cluster_all_pods.txt
├── my-cluster_all_nodes.txt
├── my-cluster_namespaces.txt
├── my-cluster_services.txt
├── ...
├── my-cluster_default_myconfigmap_describeConfigMap.txt
└── my-cluster_config.json

Archive:
  /var/tmp/my-cluster-20250715-103001.tar.gz
```

---

## 🔐 Sharing Considerations

Before sharing the archive externally:

- **Review outputs** for sensitive information (secrets, internal URLs, etc.)
- **Do not** send the raw `kubeconfig` file — it is not included in the archive.

---

## 🛠 Support & Customization

This script is modular and can be extended to gather more cluster data (e.g., logs, metrics, custom CRDs). Feel free to adapt to your operational or support workflows.
