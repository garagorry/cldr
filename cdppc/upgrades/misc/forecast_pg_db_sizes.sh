#!/usr/bin/env bash

set -euo pipefail

PILLAR_FILE="/srv/pillar/postgresql/postgre.sls"
DEFAULT_PORT=5432
COMPRESSION_RATIO=0.7  # Assume 30% compression typical for text-based dumps

usage() {
  cat <<EOF
Usage: $0 [--help]

This script forecasts the sizes of PostgreSQL databases defined in the Cloudera
pillar file at $PILLAR_FILE by querying each database's size remotely.

Requirements:
  - Must be run as root on a node where Cloudera Manager is running.
  - Requires 'jq' and 'psql' commands available in PATH.
  - Assumes databases allow remote connections using credentials from the pillar file.

Options:
  --help      Show this help message and exit

EOF
}

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $EUID -ne 0 ]]; then
  echo "❌ This script must be run as root. Exiting."
  exit 1
fi

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Check jq availability
if ! command -v jq &>/dev/null; then
  echo "❌ This script requires 'jq'. Install it and retry."
  exit 1
fi

log "🔍 Extracting databases from pillar file: $PILLAR_FILE"

# Read all database definitions from the JSON file
db_entries=$(sed -n '2,$p' "$PILLAR_FILE" | jq -r '
  .postgres | to_entries[]
  | select(.value | type == "object" and .database != null)
  | {
      name: .value.database,
      user: .value.remote_admin,
      password: .value.remote_admin_pw,
      host: .value.remote_db_url,
      port: (.value.remote_db_port // 5432)
    }
')

if [[ -z "$db_entries" ]]; then
  echo "⚠️ No databases found in pillar file."
  exit 0
fi

log "📊 Forecasting database sizes..."

# Loop over each database entry
echo "$db_entries" | jq -c '.' | while read -r db; do
  DB_NAME=$(echo "$db" | jq -r '.name')
  DB_USER=$(echo "$db" | jq -r '.user')
  DB_PASS=$(echo "$db" | jq -r '.password')
  DB_HOST=$(echo "$db" | jq -r '.host')
  DB_PORT=$(echo "$db" | jq -r '.port')

  export PGPASSWORD="$DB_PASS"

  log "📡 Connecting to $DB_NAME on $DB_HOST..."

  size_bytes=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT pg_database_size('$DB_NAME');" 2>/dev/null | tr -d '[:space:]')

  if [[ "$size_bytes" =~ ^[0-9]+$ ]]; then
    size_mb=$(awk "BEGIN {printf \"%.2f\", $size_bytes / 1024 / 1024}")
    est_compressed=$(awk "BEGIN {printf \"%.2f\", $size_mb * $COMPRESSION_RATIO}")
    log "✅ $DB_NAME: ${size_mb} MB (estimated compressed: ${est_compressed} MB)"
  else
    log "❌ Failed to retrieve size for $DB_NAME"
  fi

  unset PGPASSWORD
done

log "🏁 Forecasting complete."
