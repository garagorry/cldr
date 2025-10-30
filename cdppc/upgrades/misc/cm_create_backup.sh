#!/usr/bin/env bash

set -euo pipefail

# === Defaults ===
CLDR_BASE_FOLDER="/hadoopfs/fs1/CLDR/"
COMPRESS=true
ESTIMATE_SIZE=false
PILLAR_FILE="/srv/pillar/postgresql/postgre.sls"
USE_PILLAR=true
DEBUG=false
CONNECT_TIMEOUT=3
EXCLUDE_LABELS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      echo "Usage: $0 [options]"
      echo ""
      echo "Back up all CDP service PostgreSQL databases defined in: $PILLAR_FILE"
      echo "Backups are stored under: <base>/BACKUP/<timestamp>/<db_label>/"
      echo ""
      echo "Options:"
      echo "  --no-compress              Disable gzip compression of dump files"
      echo "  --estimate-size            Only estimate DB sizes; do not create dumps"
      echo "  --base-folder <path>       Base folder for backups (default: $CLDR_BASE_FOLDER)"
      echo "  --cm-only                  Backup only Cloudera Manager DB from db.properties"
      echo "  --exclude <lbls>           Comma-separated labels to exclude (can repeat)"
      echo "  --connect-timeout <secs>   Connectivity check timeout (default: $CONNECT_TIMEOUT)"
      echo "  --debug                    Verbose debug logging"
      echo "  -h, --help                 Show this help message and exit"
      exit 0
      ;;
    --no-compress)
      COMPRESS=false
      shift
      ;;
    --estimate-size)
      ESTIMATE_SIZE=true
      shift
      ;;
    --base-folder)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "❌ --base-folder requires a path argument"
        echo "Try '$0 --help' for usage."
        exit 1
      fi
      CLDR_BASE_FOLDER="$2"
      shift 2
      ;;
    --exclude)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "❌ --exclude requires a comma-separated list of labels"
        echo "Example: $0 --exclude hive,knox_gateway"
        exit 1
      fi
      IFS=',' read -r -a __tmp_excludes <<< "$2"
      EXCLUDE_LABELS+=("${__tmp_excludes[@]}")
      shift 2
      ;;
    --cm-only)
      USE_PILLAR=false
      shift
      ;;
    --debug)
      DEBUG=true
      shift
      ;;
    --connect-timeout)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "❌ --connect-timeout requires a numeric value in seconds"
        echo "Example: $0 --connect-timeout 5"
        exit 1
      fi
      CONNECT_TIMEOUT="$2"
      shift 2
      ;;
    *)
      echo "❌ Unknown option: $1"
      echo "Try '$0 --help' for usage."
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

debug() {
  if $DEBUG; then
    # Write debug to log and stderr (avoid contaminating stdout used for data pipes)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🐞 $*" | tee -a "$LOG_FILE" >&2
  fi
}

get_pillar_databases() {
  if [[ ! -f "$PILLAR_FILE" ]]; then
    log "❌ Cannot find pillar file: $PILLAR_FILE. Exiting."
    exit 1
  fi
  
  # Check if jq is available
  if ! command -v jq &>/dev/null; then
    log "❌ jq is required to parse the pillar file. Please install jq. Exiting."
    exit 1
  fi
  
  log "📖 Reading database configurations from $PILLAR_FILE" >&2
  
  # Some pillar files start with a shebang-like marker (e.g. #!json). Remove that line before parsing.
  # Also tolerate missing host/port by defaulting to localhost:5432.
  DB_CONFIGS=$(sed '1{/^#!/d;}' "$PILLAR_FILE" | jq -r '.postgres
    | to_entries
    | map(select(.value | type == "object" and has("database") and has("user") and has("password")))
    | .[]
    | "\(.key)|\(.value.database)|\(.value.user)|\(.value.password)|\((.value.remote_db_url // "localhost"))|\((.value.remote_db_port // 5432))"' 2>/dev/null)
  
  if [[ -z "$DB_CONFIGS" ]]; then
    log "⚠️  No valid database configurations found in $PILLAR_FILE"
    exit 1
  fi

  # Debug: show sanitized configs
  if $DEBUG; then
    debug "Sanitized database entries from pillar:"
    while IFS='|' read -r _label _name _user _pass _host _port; do
      [[ -z "${_label}${_name}${_user}${_host}${_port}" ]] && continue
      debug "cfg label=${_label} db=${_name} user=${_user} host=${_host:-localhost} port=${_port:-5432}"
    done < <(printf '%s\n' "$DB_CONFIGS")
  fi
  
  echo "$DB_CONFIGS"
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
  local db_host="${1:-$CM_DB_HOST}"
  local db_port="${2:-5432}"
  
  log "🔍 Validating PostgreSQL availability on host: $db_host:$db_port (timeout=${CONNECT_TIMEOUT}s)"
  debug "connectivity check using $(command -v nc >/dev/null 2>&1 && echo nc || echo bash /dev/tcp)"

  if [[ "$db_host" == "localhost" || "$db_host" == "127.0.0.1" ]]; then
    if command -v pg_isready &>/dev/null; then
      if ! pg_isready -q; then
        log "❌ PostgreSQL is not ready locally on $db_host."
        return 1
      fi
    elif ! pgrep -x "postgres" &>/dev/null; then
      log "❌ PostgreSQL is not running locally (no pg_isready or pgrep match)."
      return 1
    fi
  else
    if command -v nc &>/dev/null; then
      if ! nc -z -w "$CONNECT_TIMEOUT" "$db_host" "$db_port"; then
        log "❌ Cannot reach PostgreSQL on $db_host:$db_port (nc failed)."
        return 1
      fi
    else
      if ! timeout "$CONNECT_TIMEOUT" bash -c "</dev/tcp/${db_host}/${db_port}" &>/dev/null; then
        log "❌ Cannot reach PostgreSQL on $db_host:$db_port (bash TCP test failed)."
        return 1
      fi
    fi
  fi

  log "✅ PostgreSQL is reachable on $db_host:$db_port"
}

estimate_size() {
  local db_host="$1"
  local db_user="$2"
  local db_name="$3"
  local db_password="$4"
  
  log "📊 Estimating size of database: $db_name"
  export PGPASSWORD="$db_password"
  
  SIZE_BYTES=$(psql -h "$db_host" -U "$db_user" -d "$db_name" -t -c "SELECT pg_database_size('$db_name');" 2>/dev/null | tr -d '[:space:]')
  if [[ -z "$SIZE_BYTES" || ! "$SIZE_BYTES" =~ ^[0-9]+$ ]]; then
    log "❌ Failed to estimate database size for $db_name"
    return 1
  fi
  SIZE_MB=$(echo "scale=2; $SIZE_BYTES / 1024 / 1024" | bc)
  log "📐 Estimated DB Size for $db_name: $SIZE_MB MB"
  if $COMPRESS; then
    ESTIMATED_COMPRESSED_MB=$(echo "scale=2; $SIZE_MB * 0.3" | bc)
    log "📉 Estimated Compressed Size (~30%): $ESTIMATED_COMPRESSED_MB MB"
  fi
}

run_backup() {
  local db_host="$1"
  local db_user="$2"
  local db_name="$3"
  local db_password="$4"
  local db_label="${5:-$db_name}"
  
  log "🚀 Starting backup for database: $db_label ($db_name)"
  export PGPASSWORD="$db_password"

  # Per-database target directory under the timestamped backup folder
  local TARGET_DIR="${BACKUP_DIR}/${db_label}"
  mkdir -p "$TARGET_DIR"

  # === Plain text dump ===
  PLAIN_DUMP="${TARGET_DIR}/${db_label}_${TIMESTAMP}_plain"
  log "📦 Dumping plain text to $PLAIN_DUMP"
  debug "pg_dump plain: host=$db_host user=$db_user db=$db_name out=$PLAIN_DUMP"
  if pg_dump --host="$db_host" --username="$db_user" --dbname="$db_name" --format=plain --file="$PLAIN_DUMP" 2>>"$LOG_FILE"; then
    if $COMPRESS; then 
      gzip "$PLAIN_DUMP" && log "🗜 Compressed to ${PLAIN_DUMP}.gz"
    fi
  else
    log "⚠️  Failed to create plain dump for $db_label"
  fi

  # === Schema-only dump ===
  SCHEMA_DUMP="${TARGET_DIR}/${db_label}_${TIMESTAMP}_schema.sql"
  log "📦 Dumping schema to $SCHEMA_DUMP"
  debug "pg_dump schema-only: host=$db_host user=$db_user db=$db_name out=$SCHEMA_DUMP"
  if pg_dump --host="$db_host" --username="$db_user" --dbname="$db_name" --schema-only --no-owner --no-privileges --file="$SCHEMA_DUMP" 2>>"$LOG_FILE"; then
    if $COMPRESS; then 
      gzip "$SCHEMA_DUMP" && log "🗜 Compressed to ${SCHEMA_DUMP}.gz"
    fi
  else
    log "⚠️  Failed to create schema dump for $db_label"
  fi

  # === Full binary dump ===
  FULL_DUMP="${TARGET_DIR}/${db_label}_${TIMESTAMP}_full_binary"
  log "📦 Dumping binary format to $FULL_DUMP"
  debug "pg_dump custom: host=$db_host user=$db_user db=$db_name out=$FULL_DUMP"
  if pg_dump --host="$db_host" --username="$db_user" --dbname="$db_name" -F c --no-owner --no-privileges --verbose --file="$FULL_DUMP" 2>>"$LOG_FILE"; then
    if $COMPRESS; then 
      gzip "$FULL_DUMP" && log "🗜 Compressed to ${FULL_DUMP}.gz"
    fi
  else
    log "⚠️  Failed to create binary dump for $db_label"
  fi

  log "✅ Backup completed for $db_label (folder: $TARGET_DIR)"
}

# === Main ===
log "🚀 Starting database backup process"
log "Base folder: $CLDR_BASE_FOLDER"
log "Compression enabled: $COMPRESS"
log "Backup path: $BACKUP_DIR"

# If debug is enabled, turn on bash xtrace to stderr (portable PS4)
if $DEBUG; then
  export PS4='xtrace: '
  set -x
fi

if $USE_PILLAR; then
  # Use pillar file for multiple databases
  log "📋 Using pillar file: $PILLAR_FILE"
  DB_CONFIGS=$(get_pillar_databases)
  
  DB_COUNT=0
  # Read lines safely into an array to avoid subshell/IFS edge-cases
  mapfile -t __DB_LINES < <(printf '%s\n' "$DB_CONFIGS")
  __RAW_COUNT=${#__DB_LINES[@]}
  debug "Detected ${__RAW_COUNT} entries before exclusion"

  # Apply exclusion filter up-front to get accurate progress counts
  __FILTERED_LINES=()
  for __pre_line in "${__DB_LINES[@]}"; do
    IFS='|' read -r __lbl __name __u __p __h __pt <<< "$__pre_line" || continue
    if [[ ${#EXCLUDE_LABELS[@]} -gt 0 ]]; then
      __skip=false
      for __ex in "${EXCLUDE_LABELS[@]}"; do
        if [[ "$__lbl" == "$__ex" || "$__name" == "$__ex" ]]; then
          __skip=true
          break
        fi
      done
      $__skip && continue
    fi
    __FILTERED_LINES+=("$__pre_line")
  done

  # Replace with filtered lines and compute total to process
  __DB_LINES=("${__FILTERED_LINES[@]}")
  TOTAL_DBS=${#__DB_LINES[@]}
  log "📊 Backing up $TOTAL_DBS database(s) (after exclusions)"
  debug "Looping over ${TOTAL_DBS} entries"
  # Disable exit-on-error within the loop to avoid silent aborts on non-critical commands
  set +e
  for __line in "${__DB_LINES[@]}"; do
    debug "Parsing entry: $__line"
    IFS='|' read -r db_label db_name db_user db_password db_host db_port <<< "$__line" || {
      debug "read failed for line; skipping"
      continue
    }
    debug "Parsed fields: label=$db_label name=$db_name user=$db_user host=${db_host:-} port=${db_port:-}"
    # Skip empty lines
    [[ -z "${db_label}" && -z "${db_name}" ]] && continue

    # Exclusion filter (match by label or name)
    if [[ ${#EXCLUDE_LABELS[@]} -gt 0 ]]; then
      for __ex in "${EXCLUDE_LABELS[@]}"; do
        if [[ "$db_label" == "$__ex" || "$db_name" == "$__ex" ]]; then
          log "⏭ Skipping $db_label due to exclude list"
          continue 2
        fi
      done
    fi

    # Normalize host/port if null or empty
    [[ -z "${db_host}" || "${db_host}" == "null" ]] && db_host="localhost"
    [[ -z "${db_port}" || "${db_port}" == "null" ]] && db_port=5432

    ((DB_COUNT++))
    debug "About to log processing header for $db_label ($DB_COUNT/$TOTAL_DBS)"
    log "" || true
    log "========================================"
    log "Processing database $DB_COUNT/$TOTAL_DBS: $db_label"
    log "Host: $db_host  Port: $db_port  User: $db_user  DB: $db_name"
    log "========================================"
    
    # Check if database host is reachable
    if ! check_postgres_running "$db_host" "$db_port"; then
      log "⚠️  Skipping $db_label due to connectivity issues"
      continue
    fi
    
    if $ESTIMATE_SIZE; then
      estimate_size "$db_host" "$db_user" "$db_name" "$db_password" || log "⚠️  Size estimation failed for $db_label"
    else
      run_backup "$db_host" "$db_user" "$db_name" "$db_password" "$db_label"
    fi
  done
  # Re-enable exit-on-error after processing
  set -e
  
  log ""
  log "========================================"
  log "✅ All database backups completed"
  log "========================================"
else
  # Use CM properties file (old behavior)
  log "📋 Using Cloudera Manager properties file (--cm-only mode)"
  get_db_params
  check_postgres_running "$CM_DB_HOST" 5432
  
  if $ESTIMATE_SIZE; then
    estimate_size "$CM_DB_HOST" "$CM_DB_USER" "$CM_DB_NAME" "$PGPASSWORD"
  else
    run_backup "$CM_DB_HOST" "$CM_DB_USER" "$CM_DB_NAME" "$PGPASSWORD" "clouderamanager"
  fi
fi

log ""
log "📁 Backup location: $BACKUP_DIR"
log "📄 Log file: $LOG_FILE"
