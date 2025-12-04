# Port Forwarding for Impala Metrics Endpoints

## Understanding Port Forward Syntax

The `kubectl port-forward` command uses the format:

```bash
kubectl port-forward <pod-name> <local-port>:<pod-port> -n <namespace>
```

### Why `25040:25040`?

- **First number (25040)**: Port on your **local machine** (localhost)
- **Second number (25040)**: Port **inside the pod** where the metrics endpoint is listening
- **Why same number?**: It's just convenience - you can use any local port, but using the same number makes it easier to remember

**Example:**

```bash
kubectl port-forward coordinator-0 -n impala-1764611655-qscn 25040:25040
```

This creates a tunnel: `localhost:25040` → `coordinator-0:25040`

You could also use:

```bash
kubectl port-forward coordinator-0 -n impala-1764611655-qscn 9999:25040
```

This would expose the pod's port 25040 on your local port 9999.

---

## How to Find Port Numbers

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

### Method 3: Reference Documentation

Based on the Prometheus architecture documentation, here are the standard ports:

---

## Impala Pod Metrics Ports Reference

| Pod Type              | Metrics Port | Metrics Path          | Example Pod Names                                  |
| --------------------- | ------------ | --------------------- | -------------------------------------------------- |
| **coordinator**       | `25040`      | `/metrics_prometheus` | coordinator-0, coordinator-1                       |
| **catalogd**          | `25021`      | `/metrics_prometheus` | catalogd-0, catalogd-1                             |
| **statestored**       | `25011`      | `/metrics_prometheus` | statestored-0, statestored-1                       |
| **impala-executor**   | `25000`      | `/metrics_prometheus` | impala-executor-000-0, impala-executor-000-1, etc. |
| **impala-autoscaler** | `25030`      | `/metrics_prometheus` | impala-autoscaler-668ff8745d-zwfn2                 |
| **huebackend**        | (varies)     | `/metrics`            | huebackend-0                                       |
| **huefrontend**       | (varies)     | `/metrics`            | huefrontend-6766d5c66b-m9pwz                       |

---

## Port Forward Commands for All Pods

### Coordinator Pods

```bash
# Coordinator-0
kubectl port-forward coordinator-0 -n impala-1764611655-qscn 25040:25040

# Coordinator-1
kubectl port-forward coordinator-1 -n impala-1764611655-qscn 25041:25040
```

### Catalogd Pods

```bash
# Catalogd-0
kubectl port-forward catalogd-0 -n impala-1764611655-qscn 25021:25021

# Catalogd-1
kubectl port-forward catalogd-1 -n impala-1764611655-qscn 25022:25021
```

### Statestored Pods

```bash
# Statestored-0
kubectl port-forward statestored-0 -n impala-1764611655-qscn 25011:25011

# Statestored-1
kubectl port-forward statestored-1 -n impala-1764611655-qscn 25012:25011
```

### Executor Pods

```bash
# Executor-000-0
kubectl port-forward impala-executor-000-0 -n impala-1764611655-qscn 25000:25000

# Executor-000-1
kubectl port-forward impala-executor-000-1 -n impala-1764611655-qscn 25001:25000

# Executor-001-0 (if exists)
kubectl port-forward impala-executor-001-0 -n impala-1764611655-qscn 25002:25000
```

### Autoscaler

```bash
kubectl port-forward impala-autoscaler-668ff8745d-zwfn2 -n impala-1764611655-qscn 25030:25030
```

### Hue Pods

```bash
# First, find the port (may vary)
HUE_BACKEND_PORT=$(kubectl get pod huebackend-0 -n impala-1764611655-qscn -o jsonpath='{.spec.containers[0].ports[?(@.name=="http")].containerPort}')
kubectl port-forward huebackend-0 -n impala-1764611655-qscn 8888:${HUE_BACKEND_PORT:-8888}

HUE_FRONTEND_PORT=$(kubectl get pod huefrontend-6766d5c66b-m9pwz -n impala-1764611655-qscn -o jsonpath='{.spec.containers[0].ports[?(@.name=="http")].containerPort}')
kubectl port-forward huefrontend-6766d5c66b-m9pwz -n impala-1764611655-qscn 8889:${HUE_FRONTEND_PORT:-8888}
```

---

## Accessing Metrics After Port Forward

Once port-forwarded, access metrics at:

### Impala Components (Prometheus format)

```bash
# Coordinator
curl --silent http://localhost:25040/metrics_prometheus

# Catalogd
curl --silent http://localhost:25021/metrics_prometheus

# Statestored
curl --silent http://localhost:25011/metrics_prometheus

# Executor
curl --silent http://localhost:25000/metrics_prometheus

# Autoscaler
curl --silent http://localhost:25030/metrics_prometheus
```

### Hue Components

```bash
# Hue Backend
curl --silent http://localhost:8888/metrics

# Hue Frontend
curl --silent http://localhost:8889/metrics
```

---

## Running Multiple Port Forwards

Port-forward commands run in the foreground. To run multiple simultaneously:

### Option 1: Background Jobs

```bash
# Start all port-forwards in background
kubectl port-forward coordinator-0 -n impala-1764611655-qscn 25040:25040 &
kubectl port-forward coordinator-1 -n impala-1764611655-qscn 25041:25040 &
kubectl port-forward catalogd-0 -n impala-1764611655-qscn 25021:25021 &
kubectl port-forward catalogd-1 -n impala-1764611655-qscn 25022:25021 &
kubectl port-forward statestored-0 -n impala-1764611655-qscn 25011:25011 &
kubectl port-forward statestored-1 -n impala-1764611655-qscn 25012:25011 &
kubectl port-forward impala-executor-000-0 -n impala-1764611655-qscn 25000:25000 &
kubectl port-forward impala-executor-000-1 -n impala-1764611655-qscn 25001:25000 &
kubectl port-forward impala-autoscaler-668ff8745d-zwfn2 -n impala-1764611655-qscn 25030:25030 &

# List background jobs
jobs

# Stop all port-forwards
kill %1 %2 %3 %4 %5 %6 %7 %8 %9
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
tmux send-keys "kubectl port-forward coordinator-0 -n impala-1764611655-qscn 25040:25040" C-m
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

### Pod Not Found

```bash
# Verify pod exists and is running
kubectl get pods -n impala-1764611655-qscn | grep <pod-name>

# Check pod status
kubectl describe pod <pod-name> -n impala-1764611655-qscn
```

### Connection Refused

- Ensure the pod is in `Running` state
- Verify the port number is correct
- Check if the metrics endpoint is actually listening:
  ```bash
  kubectl exec -it <pod-name> -n impala-1764611655-qscn -- netstat -tlnp | grep <port>
  ```

---

## Quick Reference: Port Mapping Summary

```
Local Port → Pod Port → Component
25040      → 25040    → coordinator-0
25041      → 25040    → coordinator-1
25021      → 25021    → catalogd-0
25022      → 25021    → catalogd-1
25011      → 25011    → statestored-0
25012      → 25011    → statestored-1
25000      → 25000    → impala-executor-000-0
25001      → 25000    → impala-executor-000-1
25030      → 25030    → impala-autoscaler
```

---

## Next Steps

See `port_forward_all_metrics.sh` script for automated port-forwarding of all pods.

### Using the Automated Script

The script supports command-line arguments:

```bash
# Basic usage
./port_forward_all_metrics.sh

# Specify kubectl binary
./port_forward_all_metrics.sh -k ~/bin/kubectl

# Specify namespace
./port_forward_all_metrics.sh -n impala-1764611655-qscn

# Combine options
./port_forward_all_metrics.sh -k ~/bin/kubectl -n impala-1764611655-qscn

# List pods with metrics
./port_forward_all_metrics.sh --list

# Stop all port-forwards
./port_forward_all_metrics.sh --stop
```

**Options:**

- `-k, --kubectl PATH`: Path to kubectl binary (default: `kubectl`)
- `-n, --namespace NAME`: Kubernetes namespace (default: `impala-1764611655-qscn`)
- `--list, -l`: List all pods with metrics endpoints
- `--stop, -s`: Stop all running port-forwards
- `--help, -h`: Show help message
