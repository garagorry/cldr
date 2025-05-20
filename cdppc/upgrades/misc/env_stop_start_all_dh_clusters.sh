#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "Usage: $0 <environment-name> <start|stop> <poll-interval-seconds> <timeout-minutes> [--dry-run]"
  exit 1
}

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

spinner() {
  local pid=$1
  local delay=0.1
  local spinstr='|/-\'
  while kill -0 "$pid" 2>/dev/null; do
    local temp=${spinstr#?}
    printf " [%c]  " "$spinstr"
    local spinstr=$temp${spinstr%"$temp"}
    sleep $delay
    printf "\b\b\b\b\b\b"
  done
}

poll_cluster_status() {
  local cluster="$1"
  local target_status="$2"
  local log_file="$3"
  local poll_interval="$4"
  local timeout_minutes="$5"

  local timeout_seconds=$((timeout_minutes * 60))
  local start_time=$(date +%s)

  while true; do
    status=$(cdp datahub describe-cluster --cluster-name "$cluster" 2>/dev/null | jq -r '.cluster.status')
    now=$(date +%s)
    elapsed=$((now - start_time))

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cluster $cluster status: $status (Elapsed: ${elapsed}s)" >>"$log_file"

    if [[ "$status" == "$target_status" ]]; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cluster $cluster reached target status: $status" >>"$log_file"
      break
    fi

    if (( elapsed >= timeout_seconds )); then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] TIMEOUT: Cluster $cluster did not reach '$target_status' in ${timeout_minutes} minutes. Last status: $status" >>"$log_file"
      break
    fi

    sleep "$poll_interval"
  done
}

if [ "$#" -lt 4 ] || [ "$#" -gt 5 ]; then
  usage
fi

ENV_NAME="$1"
ACTION="$2"
POLL_INTERVAL="$3"
POLL_TIMEOUT_MINUTES="$4"
DRY_RUN="${5:-}"

START_STATUS="AVAILABLE"
STOP_STATUS="STOPPED"

if [[ "$ACTION" != "start" && "$ACTION" != "stop" ]]; then
  log "Invalid action: $ACTION. Use 'start' or 'stop'."
  usage
fi

if [[ -n "$DRY_RUN" && "$DRY_RUN" != "--dry-run" ]]; then
  log "Invalid fifth argument: $DRY_RUN"
  usage
fi

IS_DRY_RUN=false
if [[ "$DRY_RUN" == "--dry-run" ]]; then
  IS_DRY_RUN=true
  log "Running in DRY-RUN mode. No actions will be executed."
fi

LOG_DIR="/tmp/logs-${ENV_NAME}-${ACTION}-$(date +%Y%m%d%H%M%S)"
mkdir -p "$LOG_DIR"

log "Fetching DataHub clusters for environment: $ENV_NAME..."
CLUSTERS=$(cdp datahub list-clusters --environment-name "$ENV_NAME" 2>/dev/null | jq -r '.clusters[].clusterName')

if [ -z "$CLUSTERS" ]; then
  log "No DataHub clusters found in environment: $ENV_NAME"
  exit 0
fi

declare -A CLUSTER_OPS
log "${IS_DRY_RUN:+(dry-run)} Preparing to $ACTION clusters..."

for cluster in $CLUSTERS; do
  LOG_FILE="${LOG_DIR}/${cluster}.log"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $ACTION planned for cluster: $cluster" | tee "$LOG_FILE"

  if [ "$ACTION" == "stop" ]; then
    TARGET_STATUS="$STOP_STATUS"
    if [[ "$IS_DRY_RUN" == false ]]; then
      op_id=$(cdp datahub stop-cluster --cluster-name "$cluster" 2>/dev/null | jq -r '.operationId')
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] Operation ID: $op_id" >>"$LOG_FILE"
    else
      echo "DRY-RUN: Would stop cluster: $cluster" >>"$LOG_FILE"
    fi
  else
    TARGET_STATUS="$START_STATUS"
    if [[ "$IS_DRY_RUN" == false ]]; then
      op_id=$(cdp datahub start-cluster --cluster-name "$cluster" 2>/dev/null | jq -r '.operationId')
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] Operation ID: $op_id" >>"$LOG_FILE"
    else
      echo "DRY-RUN: Would start cluster: $cluster" >>"$LOG_FILE"
    fi
  fi

  CLUSTER_OPS["$cluster"]="$TARGET_STATUS"
done

if [[ "$IS_DRY_RUN" == false ]]; then
  log "Monitoring cluster statuses (interval: ${POLL_INTERVAL}s, timeout: ${POLL_TIMEOUT_MINUTES}m)..."
  PIDS=()

  for cluster in "${!CLUSTER_OPS[@]}"; do
    poll_cluster_status "$cluster" "${CLUSTER_OPS[$cluster]}" "${LOG_DIR}/${cluster}.log" "$POLL_INTERVAL" "$POLL_TIMEOUT_MINUTES" &
    PIDS+=($!)
  done

  for pid in "${PIDS[@]}"; do
    spinner "$pid"
    wait "$pid"
  done

  log "Polling complete. Final cluster statuses:"
  SUCCESS=()
  FAILURE=()

  for cluster in "${!CLUSTER_OPS[@]}"; do
    FINAL_STATUS=$(cdp datahub describe-cluster --cluster-name "$cluster" 2>/dev/null | jq -r '.cluster.status')
    EXPECTED_STATUS="${CLUSTER_OPS[$cluster]}"

    if [[ "$FINAL_STATUS" == "$EXPECTED_STATUS" ]]; then
      log "✅ $cluster is in expected status: $FINAL_STATUS"
      SUCCESS+=("$cluster")
    else
      log "❌ $cluster is in unexpected status: $FINAL_STATUS (expected: $EXPECTED_STATUS)"
      FAILURE+=("$cluster")
    fi
  done

  log "Summary:"
  log "  Successful: ${#SUCCESS[@]}"
  log "  Failed/Timeout: ${#FAILURE[@]}"

  if [ "${#FAILURE[@]}" -ne 0 ]; then
    log "Failures:"
    for failed in "${FAILURE[@]}"; do
      log "  - $failed (see: ${LOG_DIR}/${failed}.log)"
    done
    exit 1
  fi

  log "All clusters have successfully reached the desired state."
else
  log "DRY-RUN completed. No operations were executed. Logs in: $LOG_DIR"
fi
