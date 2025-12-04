# Prometheus Metrics Port Forwarder

Automatically port-forward all Kubernetes pods with Prometheus metrics endpoints to enable local access for monitoring and debugging.

## Overview

This tool discovers all pods in a Kubernetes namespace that have Prometheus metrics annotations and automatically creates port-forward tunnels to make their metrics endpoints accessible on your local machine.

## Features

- **Automatic Discovery**: Finds all pods with `prometheus.io/scrape=true` annotation
- **Port Management**: Automatically assigns unique local ports for each pod
- **Multiple Pod Types**: Handles coordinators, executors, and other pod types with multiple replicas
- **Flexible Configuration**: Supports custom kubectl binary and namespace selection
- **Easy Cleanup**: Simple command to stop all port-forwards

## Quick Start

```bash
# Basic usage (uses default namespace)
./port_forward_all_metrics.sh

# Specify namespace
./port_forward_all_metrics.sh -n <namespace>

# Specify kubectl binary and namespace
./port_forward_all_metrics.sh -k ~/bin/kubectl -n <namespace>

# List available pods with metrics
./port_forward_all_metrics.sh --list

# Stop all port-forwards
./port_forward_all_metrics.sh --stop
```

## Understanding Port Forward Syntax

The `kubectl port-forward` command uses the format:

```bash
kubectl port-forward <pod-name> <local-port>:<pod-port> -n <namespace>
```

### Port Mapping Explained

- **First number (local-port)**: Port on your **local machine** (localhost)
- **Second number (pod-port)**: Port **inside the pod** where the metrics endpoint is listening
- **Why same number?**: It's just convenience - you can use any local port, but using the same number makes it easier to remember

**Example:**

```bash
kubectl port-forward <pod-name> -n <namespace> 25040:25040
```

This creates a tunnel: `localhost:25040` → `<pod-name>:25040`

You could also use:

```bash
kubectl port-forward <pod-name> -n <namespace> 9999:25040
```

This would expose the pod's port 25040 on your local port 9999.

---

## How to Find Port Numbers

The script automatically discovers ports from pod annotations, but you can also find them manually:

### Method 1: Check Pod Annotations

Pods with Prometheus metrics have annotations that specify the port:

```bash
# Get port annotation for a specific pod
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.metadata.annotations.prometheus\.io/port}'

# Get all annotations for a pod
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.metadata.annotations}' | jq

# List all pods with their metrics ports
kubectl get pods -n <namespace> -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.annotations.prometheus\.io/port}{"\n"}{end}'
```

### Method 2: Check Pod Container Ports

```bash
# List all ports exposed by a pod
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[*].ports[*].containerPort}' | tr ' ' '\n' | sort -u
```

### Method 3: Use the Script's List Feature

```bash
./port_forward_all_metrics.sh --list -n <namespace>
```

This will show all pods with metrics endpoints, their ports, and paths.

---

## How It Works

The script:

1. **Discovers Pods**: Finds all pods in the specified namespace with `prometheus.io/scrape=true` annotation
2. **Reads Annotations**: Extracts port and path from pod annotations:
   - `prometheus.io/port`: The port where metrics are exposed
   - `prometheus.io/path`: The path to the metrics endpoint (defaults to `/metrics_prometheus`)
3. **Assigns Local Ports**: Automatically assigns unique local ports, incrementing for multiple replicas
4. **Creates Tunnels**: Starts port-forward processes in the background
5. **Provides Access**: Shows you the exact URLs to access each metrics endpoint

### Port Assignment Strategy

- **First pod of a type**: Uses the pod's metrics port as the local port
- **Additional replicas**: Increments the local port (e.g., 25040, 25041, 25042...)
- **Pod port**: Always uses the actual metrics port from the pod annotation

Example:

- `coordinator-0` → `localhost:25040` (pod port: 25040)
- `coordinator-1` → `localhost:25041` (pod port: 25040)
- `coordinator-2` → `localhost:25042` (pod port: 25040)

---

## Accessing Metrics After Port Forward

Once port-forwarded, access metrics using `curl`:

```bash
# Example: Access metrics from a coordinator pod
curl --silent http://localhost:25040/metrics_prometheus

# Example: Access metrics from an executor pod
curl --silent http://localhost:25000/metrics_prometheus
```

The script will display the exact URLs for all port-forwarded endpoints when it starts.

### Metrics Paths

Common metrics paths:

- `/metrics_prometheus` - Prometheus-formatted metrics (most common)
- `/metrics` - Standard Prometheus metrics endpoint

The path is determined from the `prometheus.io/path` annotation on each pod.

---

## Running Multiple Port Forwards

The script automatically handles multiple port-forwards by running them in the background. However, if you want to manage them manually:

### Option 1: Background Jobs

```bash
# Start port-forwards in background
kubectl port-forward <pod-1> -n <namespace> <local-port-1>:<pod-port-1> &
kubectl port-forward <pod-2> -n <namespace> <local-port-2>:<pod-port-2> &

# List background jobs
jobs

# Stop all port-forwards
kill %1 %2
```

### Option 2: Separate Terminal Windows

Run each port-forward in its own terminal window/tab.

### Option 3: Use tmux/screen

```bash
# Create a new tmux session
tmux new-session -d -s port-forwards

# Split windows and run port-forwards in each
tmux split-window -h
tmux select-pane -t 0
tmux send-keys "kubectl port-forward <pod-name> -n <namespace> <port>:<port>" C-m
```

---

## Troubleshooting

### Port Already in Use

If you get "address already in use", either:

1. Use a different local port: `25040:25040` → `9999:25040`
2. Find and kill the process using the port:
   ```bash
   lsof -i :25040
   kill -9 <PID>
   ```
3. Stop existing port-forwards:
   ```bash
   ./port_forward_all_metrics.sh --stop
   ```

### Pod Not Found

```bash
# Verify pod exists and is running
kubectl get pods -n <namespace> | grep <pod-name>

# Check pod status
kubectl describe pod <pod-name> -n <namespace>
```

### Connection Refused

- Ensure the pod is in `Running` state
- Verify the port number is correct
- Check if the metrics endpoint is actually listening:
  ```bash
  kubectl exec -it <pod-name> -n <namespace> -- netstat -tlnp | grep <port>
  ```

### No Pods Found

- Verify the namespace exists and contains pods
- Check that pods have the `prometheus.io/scrape=true` annotation:
  ```bash
  kubectl get pods -n <namespace> -o json | jq '.items[] | select(.metadata.annotations."prometheus.io/scrape" == "true")'
  ```

---

## Command-Line Options

```bash
./port_forward_all_metrics.sh [OPTIONS]
```

**Options:**

- `-k, --kubectl PATH`: Path to kubectl binary (default: `kubectl`)
- `-n, --namespace NAME`: Kubernetes namespace (required if not set via environment variable)
- `--list, -l`: List all pods with metrics endpoints
- `--stop, -s`: Stop all running port-forwards
- `--help, -h`: Show help message

**Environment Variables:**

- `IMPALA_NAMESPACE`: Default namespace (if not specified via `-n`)
- `KUBECTL`: Default kubectl binary path (if not specified via `-k`)

**Examples:**

```bash
# Basic usage with namespace
./port_forward_all_metrics.sh -n my-namespace

# Use custom kubectl
./port_forward_all_metrics.sh -k ~/bin/kubectl -n my-namespace

# List pods first
./port_forward_all_metrics.sh --list -n my-namespace

# Stop all port-forwards
./port_forward_all_metrics.sh --stop
```

---

## Output Example

When you run the script, you'll see output like:

```
[INFO] Starting port-forward for all Prometheus metrics endpoints in namespace: my-namespace
[INFO] Press Ctrl+C to stop all port-forwards
[INFO] Discovering pods with metrics endpoints...
[INFO] Port-forwarding coordinator-0: localhost:25040 -> coordinator-0:25040
[SUCCESS] Port-forward active: http://localhost:25040/metrics_prometheus (PID: 12345)
[INFO] Port-forwarding coordinator-1: localhost:25041 -> coordinator-1:25040
[SUCCESS] Port-forward active: http://localhost:25041/metrics_prometheus (PID: 12346)
...
[SUCCESS] All port-forwards started!
[INFO] Port-forwards are running in the background.
[INFO] Metrics endpoints are available at:
[INFO]   - Coordinators (ports 25040, 25041):
[INFO]       curl --silent http://localhost:25040/metrics_prometheus
[INFO]       curl --silent http://localhost:25041/metrics_prometheus
[INFO]   - Catalogd (ports 25021, 25022):
[INFO]       curl --silent http://localhost:25021/metrics_prometheus
[INFO]       curl --silent http://localhost:25022/metrics_prometheus
...
```

---

## Requirements

- `kubectl` - Kubernetes command-line tool
- `jq` - JSON processor (for `--list` command)
- `lsof` - For port availability checking (usually pre-installed on macOS/Linux)
- Access to the Kubernetes cluster and namespace

---

## Best Practices

1. **Always specify namespace**: Use `-n` to explicitly set the namespace
2. **Check before starting**: Use `--list` to see what pods will be port-forwarded
3. **Clean up**: Use `--stop` when done to free up ports
4. **Monitor resources**: Port-forwards consume network resources; don't leave them running indefinitely
5. **Use in development**: This tool is best suited for development and debugging, not production monitoring

---

## Related Tools

- **Prometheus**: For production metrics collection and alerting
- **Grafana**: For metrics visualization
- **kubectl port-forward**: The underlying tool used by this script

---

## License

This script is provided as-is for use with Kubernetes clusters.
