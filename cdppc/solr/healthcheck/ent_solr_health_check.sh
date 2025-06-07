#!/bin/bash

# Default target, no logging
# ./ent_solr_health_check.sh

# Custom Salt target (FQDN or regex)
# ./ent_solr_health_check.sh -t 'core03.cloudera.site'

# Enable logging
# ./ent_solr_health_check.sh -l

# Dry-run (just shows the Salt command)
# ./ent_solr_health_check.sh -n

# === Configuration ===
DEFAULT_TARGET='*core0*.cloudera.site'
LOG_DIR="/var/log/solr_health_check"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/solr_health_check_$TIMESTAMP.log"

# === Helper Functions ===
usage() {
  echo "Usage: $0 [-t salt_target] [-l] [-n]"
  echo "  -t <target>      Salt minion FQDN or regex (default: $DEFAULT_TARGET)"
  echo "  -l               Enable logging to $LOG_DIR"
  echo "  -n               Dry-run mode (print command only)"
  exit 1
}

log_msg() {
  echo "$@"
  if [[ "$LOG_ENABLED" == true ]]; then
    mkdir -p "$LOG_DIR"
    echo "$@" >> "$LOG_FILE"
  fi
}

# === Parse Arguments ===
SALT_TARGET="$DEFAULT_TARGET"
LOG_ENABLED=false
DRY_RUN=false

while getopts ":t:ln" opt; do
  case ${opt} in
    t ) SALT_TARGET="$OPTARG" ;;
    l ) LOG_ENABLED=true ;;
    n ) DRY_RUN=true ;;
    * ) usage ;;
  esac
done

# === Execution ===
log_msg "🔍 Target: $SALT_TARGET"
log_msg "📝 Logging: $LOG_ENABLED"
log_msg "🚀 Running command..."

if [[ "$DRY_RUN" == true ]]; then
  echo "[DRY-RUN] Would run:"
  echo "salt \"$SALT_TARGET\" cmd.run '<remote_script>' shell='/bin/bash'"
else
  OUTPUT=$(salt "$SALT_TARGET" cmd.run "$(cat <<'EOF'
SERVICE_NAME=solr-SOLR_SERVER

PROCESS_DIR=$(ls -d /var/run/cloudera-scm-agent/process/*${SERVICE_NAME} 2>/dev/null | tail -n1)
echo "🧩 Selected PROCESS_DIR: $PROCESS_DIR"
KEYTAB="$PROCESS_DIR/solr.keytab"
echo "🔐 Resolved KEYTAB: $KEYTAB"

if [ ! -f "$KEYTAB" ]; then
  echo "❌ Keytab not found: $KEYTAB"
  exit 1
fi

PRINCIPAL=$(klist -kt "$KEYTAB" | tail -n1 | awk '{print $4}')
echo "👤 Using principal: $PRINCIPAL"

kinit -kt "$KEYTAB" "$PRINCIPAL" || { echo "❌ kinit failed"; exit 1; }

TMP_FILE="/tmp/solr_clusterstate_$(hostname -f)_$(date +%s).json"

solrctl cluster --get-clusterstate "$TMP_FILE" || { echo "❌ Failed to get cluster state"; exit 1; }

JSON=$(sed -n "/^{/,\$p" "$TMP_FILE")

echo "$JSON" | jq -r '
  .cluster.collections
  | to_entries[]
  | "✅ Collection: \(.key), Health: \(.value.health)"'

echo "$JSON" | jq -r '
  .cluster.collections
  | to_entries[]
  | . as $col
  | .value.shards
  | to_entries[]
  | . as $shard
  | .value.replicas
  | to_entries[]
  | select(.value.state != "active")
  | "❌ Replica not active: \($col.key)/\($shard.key)/\(.key) => \(.value.state)"'

echo "$JSON" | jq -r '
  .cluster.collections
  | to_entries[]
  | . as $col
  | .value.shards
  | to_entries[]
  | select((.value.replicas | to_entries[] | select(.value.leader == "true")) | length == 0)
  | "❌ Missing leader: \($col.key)/\(.key)"'

rm -f "$TMP_FILE"
EOF
)" shell='/bin/bash' 2>/dev/null)

  echo "$OUTPUT" | tee >(if [[ "$LOG_ENABLED" == true ]]; then tee -a "$LOG_FILE"; fi)

  if echo "$OUTPUT" | grep -q "No minions matched the target"; then
    echo "⚠️  No minions matched. Please provide a fully qualified domain name (FQDN) or a valid wildcard/regex, such as '*core1*.cloudera.site'."
    [[ "$LOG_ENABLED" == true ]] && echo "⚠️  This error was logged in: $LOG_FILE"
    exit 2
  fi

  if [[ "$LOG_ENABLED" == true ]]; then
    echo "📁 Log saved to: $LOG_FILE"
  fi
fi
