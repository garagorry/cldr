#!/bin/bash
set -euo pipefail

log() {
  echo "[$(date '+%F %T')] $*"
}

get_latest_keytab() {
  local service="$1"
  local keytab_name="$2"
  local keytab_dir
  keytab_dir=$(ls -1rdth /var/run/cloudera-scm-agent/process/*${service} 2>/dev/null | tail -n 1)
  if [[ -z "$keytab_dir" ]]; then
    log "ERROR: No process directory found for $service"
    exit 1
  fi
  echo "${keytab_dir}/${keytab_name}"
}

kinit_with_keytab() {
  local keytab="$1"
  local principal
  principal=$(klist -kt "$keytab" | tail -n 1 | awk '{print $4}')
  if [[ -z "$principal" ]]; then
    log "ERROR: No principal found in $keytab"
    exit 1
  fi
  log "Authenticating as $principal"
  kinit -kt "$keytab" "$principal"
}

# --- Step 1: Prepare HDFS backup location ---
log "Preparing HDFS backup location"
kdestroy || true

hdfs_keytab=$(get_latest_keytab "hdfs-DATANODE" "hdfs.keytab")
kinit_with_keytab "$hdfs_keytab"

timestamp=$(date +"%Y%m%d%H%M%S")
backup_location="/user/solr/backup/${timestamp}"

hdfs dfs -mkdir -p "${backup_location}"
hdfs dfs -chown solr:solr "${backup_location}"

# --- Step 2: Trigger Solr Collection Backup ---
log "Triggering Solr collection backup"
kdestroy || true

solr_keytab=$(get_latest_keytab "solr-SOLR_SERVER" "solr.keytab")
kinit_with_keytab "$solr_keytab"

solr_host="$(hostname -f)"
solr_endpoint="https://${solr_host}:8985"

# List collections
log "Retrieving Solr collections from ${solr_endpoint}"
collections=$(curl --silent --location --negotiate --insecure --user : \
  "${solr_endpoint}/solr/admin/collections?action=LIST&wt=json" | \
  jq -r '.collections[]')

if [[ -z "$collections" ]]; then
  log "ERROR: No collections found"
  exit 1
fi

# Backup each collection
for collection in $collections; do
  log "Backing up collection: $collection"
  curl --silent --location --negotiate --insecure --user : \
    "${solr_endpoint}/solr/admin/collections" \
    --data-urlencode "action=BACKUP" \
    --data-urlencode "collection=${collection}" \
    --data-urlencode "name=${collection}_backup" \
    --data-urlencode "location=${backup_location}" \
    --data-urlencode "wt=json"
done

# --- Step 3: Show backup location ---
log "Backup complete. Contents of backup directory:"
hdfs dfs -ls "${backup_location}"
