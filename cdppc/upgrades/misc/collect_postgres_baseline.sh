#!/usr/bin/env bash
#
CONFIG_FILE="/srv/pillar/postgresql/postgre.sls"
export OUTPUT_DIR="/tmp/$(hostname -f)/$(date +"%Y%m%d%H%M%S")/baseline_reports"
mkdir -p "${OUTPUT_DIR}"

for cmd in jq psql pg_dump; do
  if ! command -v $cmd &> /dev/null; then
    echo "[ERROR] $cmd not found. Please install it."
    exit 1
  fi
done

DB_KEYS=$(sed '1d' ${CONFIG_FILE} | jq -r '.postgres | to_entries[] | select(.value | type == "object") | .key')

echo "[INFO] Found databases: $DB_KEYS"

for KEY in $DB_KEYS; do
  echo "[INFO] Processing $KEY..."

  DB_NAME=$(sed '1d' ${CONFIG_FILE} | jq -r ".postgres.\"$KEY\".database")
  DB_USER=$(sed '1d' ${CONFIG_FILE} | jq -r ".postgres.\"$KEY\".user")
  DB_PASS=$(sed '1d' ${CONFIG_FILE} | jq -r ".postgres.\"$KEY\".password")
  DB_HOST=$(sed '1d' ${CONFIG_FILE} | jq -r ".postgres.\"$KEY\".remote_db_url")
  DB_PORT=$(sed '1d' ${CONFIG_FILE} | jq -r ".postgres.\"$KEY\".remote_db_port")

  REPORT_FILE="${OUTPUT_DIR}/${KEY}_baseline.txt"
  SCHEMA_FILE="${OUTPUT_DIR}/${KEY}_schema.sql"

  echo "[INFO] Connecting to ${DB_NAME} at ${DB_HOST}:${DB_PORT} as ${DB_USER}"
  export PGPASSWORD="${DB_PASS}"

  {
    echo "### RDS PostgreSQL Baseline Report - $KEY"
    echo "Database: ${DB_NAME}"
    echo "Host: ${DB_HOST}"
    echo "Port: ${DB_PORT}"
    echo "User: ${DB_USER}"
    echo "Generated: $(date)"

    echo -e "\n---[ DB Settings (SHOW ALL) ]---"
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "SHOW ALL;" --pset=expanded=on

    echo -e "\n---[ pg_settings ]---"
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT * FROM pg_settings;" --pset=expanded=on

    echo -e "\n---[ Users & Roles (\du) ]---"
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "\du"

    echo -e "\n---[ Active Connections + State Info ]---"
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
      -c "SELECT pid AS process_id, usename AS username, datname AS database_name, client_addr AS client_address, application_name, backend_start, state, state_change FROM pg_stat_activity;" --pset=expanded=on

    echo -e "\n---[ Table Privileges (GRANTS) ]---"
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
      -c "SELECT grantee, table_schema, table_name, privilege_type FROM information_schema.role_table_grants ORDER BY grantee, table_schema, table_name;" --pset=expanded=on

    echo -e "\n---[ Schema Summary ]---"
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
      -c "SELECT table_schema, table_name FROM information_schema.tables WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema') ORDER BY table_schema, table_name;" --pset=expanded=on

    echo -e "\n---[ Installed Extensions ]---"
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT * FROM pg_extension;" --pset=expanded=on

    echo -e "\n---[ Locks ]---"
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT * FROM pg_locks;" --pset=expanded=on

    echo -e "\n---[ Database Size ]---"
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT pg_size_pretty(pg_database_size('${DB_NAME}'));" --pset=expanded=on
  } > "${REPORT_FILE}" 2>&1

  echo "[INFO] Dumping schema to ${SCHEMA_FILE}..."
  pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -s -d "${DB_NAME}" > "${SCHEMA_FILE}" 2>> "${REPORT_FILE}"

  echo "[SUCCESS] Report: ${REPORT_FILE}"
  echo "[SUCCESS] Schema: ${SCHEMA_FILE}"
done

echo "[DONE] All database reports and schemas collected in ${OUTPUT_DIR}"