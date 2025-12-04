#!/bin/bash

# Port Forward All Impala Metrics Endpoints
# This script automatically port-forwards all Impala pods with metrics endpoints

set -e

# Configuration
NAMESPACE="${IMPALA_NAMESPACE:-impala-1764611655-qscn}"
KUBECTL="${KUBECTL:-kubectl}"

# Parse command-line arguments
ARGS=("$@")
i=0
while [ $i -lt ${#ARGS[@]} ]; do
    case "${ARGS[$i]}" in
        -k|--kubectl)
            if [ $((i+1)) -ge ${#ARGS[@]} ]; then
                echo "Error: -k/--kubectl requires a value" >&2
                exit 1
            fi
            KUBECTL="${ARGS[$((i+1))]}"
            i=$((i+2))
            ;;
        -n|--namespace)
            if [ $((i+1)) -ge ${#ARGS[@]} ]; then
                echo "Error: -n/--namespace requires a value" >&2
                exit 1
            fi
            NAMESPACE="${ARGS[$((i+1))]}"
            i=$((i+2))
            ;;
        *)
            i=$((i+1))
            ;;
    esac
done

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to get metrics port from pod annotations
get_metrics_port() {
    local pod_name=$1
    local port=$($KUBECTL get pod "$pod_name" -n "$NAMESPACE" -o jsonpath='{.metadata.annotations.prometheus\.io/port}' 2>/dev/null)
    
    if [ -z "$port" ]; then
        # Try to get from container ports if annotation not found
        port=$($KUBECTL get pod "$pod_name" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].ports[?(@.name=="metrics")].containerPort}' 2>/dev/null)
    fi
    
    echo "$port"
}

# Function to get metrics path from pod annotations
get_metrics_path() {
    local pod_name=$1
    local path=$($KUBECTL get pod "$pod_name" -n "$NAMESPACE" -o jsonpath='{.metadata.annotations.prometheus\.io/path}' 2>/dev/null)
    echo "${path:-/metrics_prometheus}"
}

# Function to check if port is available
is_port_available() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 1  # Port is in use
    else
        return 0  # Port is available
    fi
}

# Function to port-forward a pod
port_forward_pod() {
    local pod_name=$1
    local pod_port=$2
    local local_port=$3
    local metrics_path=$4
    
    # Check if pod exists
    if ! $KUBECTL get pod "$pod_name" -n "$NAMESPACE" &>/dev/null; then
        warning "Pod $pod_name not found, skipping..."
        return 1
    fi
    
    # Check if pod is running
    local pod_status=$($KUBECTL get pod "$pod_name" -n "$NAMESPACE" -o jsonpath='{.status.phase}')
    if [ "$pod_status" != "Running" ]; then
        warning "Pod $pod_name is not Running (status: $pod_status), skipping..."
        return 1
    fi
    
    # Validate pod_port is not empty
    if [ -z "$pod_port" ] || [ "$pod_port" = "null" ]; then
        error "Pod port is empty or invalid for $pod_name, cannot create port-forward"
        return 1
    fi
    
    # Check if local port is available
    if ! is_port_available "$local_port"; then
        warning "Local port $local_port is already in use, skipping $pod_name..."
        return 1
    fi
    
    # Start port-forward in background
    info "Port-forwarding $pod_name: localhost:$local_port -> $pod_name:$pod_port"
    $KUBECTL port-forward "$pod_name" -n "$NAMESPACE" "$local_port:$pod_port" > /dev/null 2>&1 &
    local pf_pid=$!
    
    # Wait a moment to check if port-forward started successfully
    sleep 2
    if kill -0 $pf_pid 2>/dev/null; then
        # Verify the port-forward process is running
        # Don't test the endpoint immediately as it may take time to establish
        # The port-forward process running is sufficient indication it's working
        success "Port-forward active: http://localhost:$local_port$metrics_path (PID: $pf_pid)"
        echo "$pf_pid" >> /tmp/impala_port_forward_pids.txt
        return 0
    else
        error "Failed to start port-forward for $pod_name"
        return 1
    fi
}

# Main execution
main() {
    info "Starting port-forward for all Impala metrics endpoints in namespace: $NAMESPACE"
    info "Press Ctrl+C to stop all port-forwards"
    
    # Clean up any existing PID file
    rm -f /tmp/impala_port_forward_pids.txt
    touch /tmp/impala_port_forward_pids.txt
    
    # Trap Ctrl+C to cleanup
    trap 'cleanup' INT TERM
    
    # Get all pods in namespace
    info "Discovering pods with metrics endpoints..."
    
    # Track ports for summary
    local coordinator_ports=()
    local catalogd_ports=()
    local statestored_ports=()
    local executor_ports=()
    local huebackend_ports=()
    local huefrontend_ports=()
    
    # Coordinator pods
    local coordinator_index=0
    for pod in $($KUBECTL get pods -n "$NAMESPACE" -o name | grep -E "coordinator-[0-9]+" | sed 's|pod/||'); do
        pod_port=$(get_metrics_port "$pod")
        if [ -z "$pod_port" ]; then
            pod_port=25040  # Default for coordinator
        fi
        metrics_path=$(get_metrics_path "$pod")
        local_port=$((25040 + coordinator_index))
        if port_forward_pod "$pod" "$pod_port" "$local_port" "$metrics_path"; then
            coordinator_ports+=("$local_port")
        fi
        ((coordinator_index++))
    done
    
    # Catalogd pods
    local catalogd_index=0
    for pod in $($KUBECTL get pods -n "$NAMESPACE" -o name | grep -E "catalogd-[0-9]+" | sed 's|pod/||'); do
        pod_port=$(get_metrics_port "$pod")
        if [ -z "$pod_port" ]; then
            pod_port=25021  # Default for catalogd
        fi
        metrics_path=$(get_metrics_path "$pod")
        local_port=$((25021 + catalogd_index))
        if port_forward_pod "$pod" "$pod_port" "$local_port" "$metrics_path"; then
            catalogd_ports+=("$local_port")
        fi
        ((catalogd_index++))
    done
    
    # Statestored pods
    local statestored_index=0
    for pod in $($KUBECTL get pods -n "$NAMESPACE" -o name | grep -E "statestored-[0-9]+" | sed 's|pod/||'); do
        pod_port=$(get_metrics_port "$pod")
        if [ -z "$pod_port" ]; then
            pod_port=25011  # Default for statestored
        fi
        metrics_path=$(get_metrics_path "$pod")
        local_port=$((25011 + statestored_index))
        if port_forward_pod "$pod" "$pod_port" "$local_port" "$metrics_path"; then
            statestored_ports+=("$local_port")
        fi
        ((statestored_index++))
    done
    
    # Executor pods
    local executor_index=0
    for pod in $($KUBECTL get pods -n "$NAMESPACE" -o name | grep -E "impala-executor-[0-9]+-[0-9]+" | sed 's|pod/||'); do
        pod_port=$(get_metrics_port "$pod")
        if [ -z "$pod_port" ]; then
            pod_port=25000  # Default for executor
        fi
        metrics_path=$(get_metrics_path "$pod")
        local_port=$((25000 + executor_index))
        if port_forward_pod "$pod" "$pod_port" "$local_port" "$metrics_path"; then
            executor_ports+=("$local_port")
        fi
        ((executor_index++))
    done
    
    # Autoscaler
    local autoscaler_forwarded=false
    for pod in $($KUBECTL get pods -n "$NAMESPACE" -o name | grep "impala-autoscaler" | sed 's|pod/||'); do
        pod_port=$(get_metrics_port "$pod")
        if [ -z "$pod_port" ]; then
            pod_port=25030  # Default for autoscaler
        fi
        metrics_path=$(get_metrics_path "$pod")
        if port_forward_pod "$pod" "$pod_port" "25030" "$metrics_path"; then
            autoscaler_forwarded=true
        fi
    done
    
    # Hue backend
    local huebackend_index=0
    for pod in $($KUBECTL get pods -n "$NAMESPACE" -o name | grep "huebackend" | sed 's|pod/||'); do
        pod_port=$(get_metrics_port "$pod")
        if [ -z "$pod_port" ]; then
            # Try to get http port, or any port from the first container
            pod_port=$($KUBECTL get pod "$pod" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].ports[?(@.name=="http")].containerPort}' 2>/dev/null)
            if [ -z "$pod_port" ]; then
                # Try to get any port from the first container
                pod_port=$($KUBECTL get pod "$pod" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].ports[0].containerPort}' 2>/dev/null)
            fi
            # Default to 8888 if still empty
            if [ -z "$pod_port" ]; then
                pod_port="8888"
            fi
        fi
        metrics_path=$(get_metrics_path "$pod")
        local_port=$((8888 + huebackend_index))
        if port_forward_pod "$pod" "$pod_port" "$local_port" "$metrics_path"; then
            huebackend_ports+=("$local_port")
        fi
        ((huebackend_index++))
    done
    
    # Hue frontend
    local huefrontend_index=0
    for pod in $($KUBECTL get pods -n "$NAMESPACE" -o name | grep "huefrontend" | sed 's|pod/||'); do
        pod_port=$(get_metrics_port "$pod")
        if [ -z "$pod_port" ]; then
            # Try to get http port, or any port from the first container
            pod_port=$($KUBECTL get pod "$pod" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].ports[?(@.name=="http")].containerPort}' 2>/dev/null)
            if [ -z "$pod_port" ]; then
                # Try to get any port from the first container
                pod_port=$($KUBECTL get pod "$pod" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].ports[0].containerPort}' 2>/dev/null)
            fi
            # Default to 8889 if still empty
            if [ -z "$pod_port" ]; then
                pod_port="8889"
            fi
        fi
        metrics_path=$(get_metrics_path "$pod")
        local_port=$((8889 + huefrontend_index))
        if port_forward_pod "$pod" "$pod_port" "$local_port" "$metrics_path"; then
            huefrontend_ports+=("$local_port")
        fi
        ((huefrontend_index++))
    done
    
    info ""
    success "All port-forwards started!"
    info "Port-forwards are running in the background."
    
    # Create input file for cdw_impala_multinode_monitor.py
    local endpoints_file="prometheus_endpoints_${NAMESPACE}.txt"
    > "$endpoints_file"  # Clear/create file
    
    # Write coordinator endpoints
    local idx=0
    for port in "${coordinator_ports[@]}"; do
        echo "coordinator,${idx},http://localhost:${port}/metrics_prometheus" >> "$endpoints_file"
        ((idx++))
    done
    
    # Write catalogd endpoints
    idx=0
    for port in "${catalogd_ports[@]}"; do
        echo "catalogd,${idx},http://localhost:${port}/metrics_prometheus" >> "$endpoints_file"
        ((idx++))
    done
    
    # Write statestored endpoints
    idx=0
    for port in "${statestored_ports[@]}"; do
        echo "statestored,${idx},http://localhost:${port}/metrics_prometheus" >> "$endpoints_file"
        ((idx++))
    done
    
    # Write executor endpoints
    idx=0
    for port in "${executor_ports[@]}"; do
        echo "executor,${idx},http://localhost:${port}/metrics_prometheus" >> "$endpoints_file"
        ((idx++))
    done
    
    # Write autoscaler endpoint (if forwarded)
    if [ "$autoscaler_forwarded" = true ]; then
        echo "autoscaler,0,http://localhost:25030/metrics_prometheus" >> "$endpoints_file"
    fi
    
    # Write hue backend endpoints
    idx=0
    for port in "${huebackend_ports[@]}"; do
        echo "huebackend,${idx},http://localhost:${port}/metrics" >> "$endpoints_file"
        ((idx++))
    done
    
    # Write hue frontend endpoints
    idx=0
    for port in "${huefrontend_ports[@]}"; do
        echo "huefrontend,${idx},http://localhost:${port}/metrics" >> "$endpoints_file"
        ((idx++))
    done
    success "Created endpoints file: $endpoints_file"
    info "Metrics endpoints are available at:"
    
    # Display coordinator ports
    if [ ${#coordinator_ports[@]} -gt 0 ]; then
        if [ ${#coordinator_ports[@]} -eq 1 ]; then
            info "  - Coordinator: curl --silent http://localhost:${coordinator_ports[0]}/metrics_prometheus"
        else
            local ports_str=$(IFS=", "; echo "${coordinator_ports[*]}")
            info "  - Coordinators (ports ${ports_str}):"
            for port in "${coordinator_ports[@]}"; do
                info "      curl --silent http://localhost:${port}/metrics_prometheus"
            done
        fi
    fi
    
    # Display catalogd ports
    if [ ${#catalogd_ports[@]} -gt 0 ]; then
        if [ ${#catalogd_ports[@]} -eq 1 ]; then
            info "  - Catalogd: curl --silent http://localhost:${catalogd_ports[0]}/metrics_prometheus"
        else
            local ports_str=$(IFS=", "; echo "${catalogd_ports[*]}")
            info "  - Catalogd (ports ${ports_str}):"
            for port in "${catalogd_ports[@]}"; do
                info "      curl --silent http://localhost:${port}/metrics_prometheus"
            done
        fi
    fi
    
    # Display statestored ports
    if [ ${#statestored_ports[@]} -gt 0 ]; then
        if [ ${#statestored_ports[@]} -eq 1 ]; then
            info "  - Statestored: curl --silent http://localhost:${statestored_ports[0]}/metrics_prometheus"
        else
            local ports_str=$(IFS=", "; echo "${statestored_ports[*]}")
            info "  - Statestored (ports ${ports_str}):"
            for port in "${statestored_ports[@]}"; do
                info "      curl --silent http://localhost:${port}/metrics_prometheus"
            done
        fi
    fi
    
    # Display executor ports
    if [ ${#executor_ports[@]} -gt 0 ]; then
        if [ ${#executor_ports[@]} -eq 1 ]; then
            info "  - Executor: curl --silent http://localhost:${executor_ports[0]}/metrics_prometheus"
        else
            local ports_str=$(IFS=", "; echo "${executor_ports[*]}")
            info "  - Executors (ports ${ports_str}):"
            for port in "${executor_ports[@]}"; do
                info "      curl --silent http://localhost:${port}/metrics_prometheus"
            done
        fi
    fi
    
    info "  - Autoscaler: curl --silent http://localhost:25030/metrics_prometheus"
    
    # Display huebackend ports
    if [ ${#huebackend_ports[@]} -gt 0 ]; then
        if [ ${#huebackend_ports[@]} -eq 1 ]; then
            info "  - Hue Backend: curl --silent http://localhost:${huebackend_ports[0]}/metrics"
        else
            local ports_str=$(IFS=", "; echo "${huebackend_ports[*]}")
            info "  - Hue Backend (ports ${ports_str}):"
            for port in "${huebackend_ports[@]}"; do
                info "      curl --silent http://localhost:${port}/metrics"
            done
        fi
    fi
    
    # Display huefrontend ports
    if [ ${#huefrontend_ports[@]} -gt 0 ]; then
        if [ ${#huefrontend_ports[@]} -eq 1 ]; then
            info "  - Hue Frontend: curl --silent http://localhost:${huefrontend_ports[0]}/metrics"
        else
            local ports_str=$(IFS=", "; echo "${huefrontend_ports[*]}")
            info "  - Hue Frontend (ports ${ports_str}):"
            for port in "${huefrontend_ports[@]}"; do
                info "      curl --silent http://localhost:${port}/metrics"
            done
        fi
    fi
    
    info ""
    info "Endpoints file created: $endpoints_file"
    info "Use this file as input to cdw_impala_multinode_monitor.py"
    info ""
    info "To stop all port-forwards, run: $0 --stop"
    info "Or press Ctrl+C"
    
    # Wait for user interrupt
    wait
}

# Cleanup function
cleanup() {
    info ""
    info "Stopping all port-forwards..."
    if [ -f /tmp/impala_port_forward_pids.txt ]; then
        while read pid; do
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null && success "Stopped port-forward (PID: $pid)" || warning "Could not stop PID: $pid"
            fi
        done < /tmp/impala_port_forward_pids.txt
        rm -f /tmp/impala_port_forward_pids.txt
    fi
    # Also kill any kubectl port-forward processes
    pkill -f "$KUBECTL port-forward.*$NAMESPACE" 2>/dev/null && success "Cleaned up remaining port-forwards" || true
    exit 0
}

# Check for stop/list/help after parsing -k and -n
# Check all remaining arguments for stop/list/help
STOP_MODE=false
LIST_MODE=false
HELP_MODE=false
for arg in "${ARGS[@]}"; do
    case "$arg" in
        --stop|-s)
            STOP_MODE=true
            ;;
        --list|-l)
            LIST_MODE=true
            ;;
        --help|-h)
            HELP_MODE=true
            ;;
    esac
done

# Stop mode
if [ "$STOP_MODE" = true ]; then
    cleanup
    exit 0
fi

# List mode
if [ "$LIST_MODE" = true ]; then
    info "Pods with metrics endpoints in namespace: $NAMESPACE"
    echo ""
    $KUBECTL get pods -n "$NAMESPACE" -o json | jq -r '.items[] | select(.metadata.annotations."prometheus.io/scrape" == "true") | "\(.metadata.name)\t\(.metadata.annotations."prometheus.io/port" // "N/A")\t\(.metadata.annotations."prometheus.io/path" // "/metrics_prometheus")"'
    exit 0
fi

# Help
if [ "$HELP_MODE" = true ]; then
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Port-forward all Impala metrics endpoints"
    echo ""
    echo "Options:"
    echo "  -k, --kubectl PATH    Path to kubectl binary (default: kubectl)"
    echo "  -n, --namespace NAME  Kubernetes namespace (default: impala-1764611655-qscn)"
    echo "  --stop, -s            Stop all running port-forwards"
    echo "  --list, -l            List all pods with metrics endpoints"
    echo "  --help, -h            Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  IMPALA_NAMESPACE      Kubernetes namespace (default: impala-1764611655-qscn)"
    echo "  KUBECTL               kubectl command path (default: kubectl)"
    echo ""
    echo "Examples:"
    echo "  $0 -k ~/bin/kubectl -n impala-1764611655-qscn"
    echo "  $0 --namespace my-namespace"
    echo "  $0 -k /usr/local/bin/kubectl"
    echo ""
    exit 0
fi

# Run main function
main

