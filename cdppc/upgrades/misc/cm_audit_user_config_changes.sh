#!/usr/bin/env bash

set -euo pipefail

# === Config ===
CM_SERVER_DB_FILE="/etc/cloudera-scm-server/db.properties"
TIMESTAMP=$(date +'%Y%m%d%H%M%S')
OUTPUT_FILE="/tmp/CM_non-default_s$(hostname -f)_${TIMESTAMP}.txt"
LOG_FILE="/tmp/cm_user_audit_${TIMESTAMP}.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# === Get DB parameters ===
if [[ ! -f "$CM_SERVER_DB_FILE" ]]; then
  log "❌ Cannot find $CM_SERVER_DB_FILE. Exiting."
  exit 1
fi

export CM_DB_HOST=$(awk -F= '/db.host/ {print $NF}' "$CM_SERVER_DB_FILE")
export CM_DB_NAME=$(awk -F= '/db.name/ {print $NF}' "$CM_SERVER_DB_FILE")
export CM_DB_USER=$(awk -F= '/db.user/ {print $NF}' "$CM_SERVER_DB_FILE")
export PGPASSWORD=$(awk -F= '/db.password/ {print $NF}' "$CM_SERVER_DB_FILE")

# === Validate PostgreSQL connectivity ===
log "🔍 Checking PostgreSQL availability on $CM_DB_HOST..."
if ! psql -h "$CM_DB_HOST" -U "$CM_DB_USER" -d "$CM_DB_NAME" -c '\q' &>/dev/null; then
  log "❌ Failed to connect to PostgreSQL. Exiting."
  exit 1
fi
log "✅ Connection to PostgreSQL successful."

# === SQL Query ===
SQL_QUERY=$(cat <<EOF
SELECT
    u.user_id,
    u.user_name,
    r.revision_id,
    r.timestamp,
    r.message,
    ca.config_id,
    ca.revtype,
    ca.attr,
    ca.value
FROM
    users u
JOIN
    revisions r
ON
    u.user_id = r.user_id
JOIN
    configs_aud ca
ON
    r.revision_id = ca.rev
WHERE
    u.user_name NOT IN ('cloudbreak', 'cmmgmt')
ORDER BY
    r.timestamp DESC;
EOF
)

log "🚀 Running CM user config audit query..."
echo "$SQL_QUERY" | psql -h "$CM_DB_HOST" -U "$CM_DB_USER" -d "$CM_DB_NAME" | tee -a "$OUTPUT_FILE" >>"$LOG_FILE" 2>&1
log "✅ Query results saved to $OUTPUT_FILE"