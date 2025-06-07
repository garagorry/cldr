#!/usr/bin/env bash

set -euo pipefail

# === Defaults ===
CLDR_BASE_FOLDER="/hadoopfs/fs1/CLDR/"
COMPRESS=true
ESTIMATE_SIZE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-compress)
      COMPRESS=false
      shift
      ;;
    --estimate-size)
      ESTIMATE_SIZE=true
      shift
      ;;
    --base-folder)
      CLDR_BASE_FOLDER="$2"
      shift 2
      ;;
    *)
      echo "❌ Unknown option: $1"
      echo "Usage: $0 [--no-compress] [--estimate-size] [--base-folder <path>]"
      exit 1
      ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "❌ This script must be run as root. Exiting."
  exit 1
fi

# === Timestamped Backup Folder ===
TIMESTAMP=$(date +'%Y%m%d%H%M%S')
BACKUP_DIR="${CLDR_BASE_FOLDER}/BACKUP/${TIMESTAMP}"
mkdir -p "$BACKUP_DIR"
LOG_FILE="${BACKUP_DIR}/cm_db_backup_${TIMESTAMP}.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

get_db_params() {
  CM_SERVER_DB_FILE="/etc/cloudera-scm-server/db.properties"
  if [[ ! -f "$CM_SERVER_DB_FILE" ]]; then
    log "❌ Cannot find $CM_SERVER_DB_FILE. Exiting."
    exit 1
  fi
  CM_DB_HOST=$(awk -F= '/db.host/ {print $NF}' "$CM_SERVER_DB_FILE")
  CM_DB_NAME=$(awk -F= '/db.name/ {print $NF}' "$CM_SERVER_DB_FILE")
  CM_DB_USER=$(awk -F= '/db.user/ {print $NF}' "$CM_SERVER_DB_FILE")
  export PGPASSWORD=$(awk -F= '/db.password/ {print $NF}' "$CM_SERVER_DB_FILE")
}

check_postgres_running() {
  log "🔍 Validating PostgreSQL availability on host: $CM_DB_HOST"

  if [[ "$CM_DB_HOST" == "localhost" || "$CM_DB_HOST" == "127.0.0.1" ]]; then
    if command -v pg_isready &>/dev/null; then
      if ! pg_isready -q; then
        log "❌ PostgreSQL is not ready locally on $CM_DB_HOST. Exiting."
        exit 1
      fi
    elif ! pgrep -x "postgres" &>/dev/null; then
      log "❌ PostgreSQL is not running locally (no pg_isready or pgrep match). Exiting."
      exit 1
    fi
  else
    if command -v nc &>/dev/null; then
      if ! nc -z -w 3 "$CM_DB_HOST" 5432; then
        log "❌ Cannot reach PostgreSQL on $CM_DB_HOST:5432 (nc failed). Exiting."
        exit 1
      fi
    else
      if ! timeout 3 bash -c "</dev/tcp/${CM_DB_HOST}/5432" &>/dev/null; then
        log "❌ Cannot reach PostgreSQL on $CM_DB_HOST:5432 (bash TCP test failed). Exiting."
        exit 1
      fi
    fi
  fi

  log "✅ PostgreSQL is reachable on $CM_DB_HOST"
}

estimate_size() {
  log "📊 Estimating size of Cloudera Manager PostgreSQL database..."
  SIZE_BYTES=$(psql -h "$CM_DB_HOST" -U "$CM_DB_USER" -d "$CM_DB_NAME" -t -c "SELECT pg_database_size('$CM_DB_NAME');" | tr -d '[:space:]')
  if [[ -z "$SIZE_BYTES" || ! "$SIZE_BYTES" =~ ^[0-9]+$ ]]; then
    log "❌ Failed to estimate database size"
    exit 1
  fi
  SIZE_MB=$(echo "scale=2; $SIZE_BYTES / 1024 / 1024" | bc)
  log "📐 Estimated DB Size: $SIZE_MB MB"
  if $COMPRESS; then
    ESTIMATED_COMPRESSED_MB=$(echo "scale=2; $SIZE_MB * 0.3" | bc)
    log "📉 Estimated Compressed Size (~30%): $ESTIMATED_COMPRESSED_MB MB"
  fi
}

run_backup() {
  log "🚀 Starting Cloudera Manager DB backup"
  log "Base folder: $CLDR_BASE_FOLDER"
  log "Compression enabled: $COMPRESS"
  log "Backup path: $BACKUP_DIR"

  # === Plain text dump ===
  PLAIN_DUMP="${BACKUP_DIR}/${CM_DB_NAME}_${TIMESTAMP}_plain"
  log "📦 Dumping plain text to $PLAIN_DUMP"
  pg_dump --host="$CM_DB_HOST" --username="$CM_DB_USER" --dbname="$CM_DB_NAME" --format=plain --file="$PLAIN_DUMP" 2>>"$LOG_FILE"
  if $COMPRESS; then gzip "$PLAIN_DUMP" && log "🗜 Compressed to ${PLAIN_DUMP}.gz"; fi

  # === Schema-only dump ===
  SCHEMA_DUMP="${BACKUP_DIR}/${CM_DB_NAME}_${TIMESTAMP}_schema.sql"
  log "📦 Dumping schema to $SCHEMA_DUMP"
  pg_dump --host="$CM_DB_HOST" --username="$CM_DB_USER" --schema-only --no-owner --no-privileges --file="$SCHEMA_DUMP" 2>>"$LOG_FILE"
  if $COMPRESS; then gzip "$SCHEMA_DUMP" && log "🗜 Compressed to ${SCHEMA_DUMP}.gz"; fi

  # === Full binary dump ===
  FULL_DUMP="${BACKUP_DIR}/${CM_DB_NAME}_${TIMESTAMP}_full_binary"
  log "📦 Dumping binary format to $FULL_DUMP"
  pg_dump --host="$CM_DB_HOST" --username="$CM_DB_USER" --dbname="$CM_DB_NAME" -F c --no-owner --no-privileges --verbose --file="$FULL_DUMP" 2>>"$LOG_FILE"
  if $COMPRESS; then gzip "$FULL_DUMP" && log "🗜 Compressed to ${FULL_DUMP}.gz"; fi

  log "✅ Backup completed successfully."
}

# === Main ===
get_db_params
check_postgres_running

if $ESTIMATE_SIZE; then
  estimate_size
else
  run_backup
fi
