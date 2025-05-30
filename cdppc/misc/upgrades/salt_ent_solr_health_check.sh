source activate_salt_env
salt '*core0*.cloudera.site' cmd.run '
SERVICE_NAME=solr-SOLR_SERVER
PROCESS_DIR=$(ls -d /var/run/cloudera-scm-agent/process/*${SERVICE_NAME} 2>/dev/null | tail -n1)
echo "🧩 Selected PROCESS_DIR: $PROCESS_DIR"
KEYTAB="$PROCESS_DIR/solr.keytab"
echo "🔐 Resolved KEYTAB: $KEYTAB"

if [ ! -f "$KEYTAB" ]; then
  echo "❌ Keytab not found: $KEYTAB"
  exit 1
fi

PRINCIPAL=$(klist -kt "$KEYTAB" | tail -n1 | awk "{print \$4}")
echo "👤 Using principal: $PRINCIPAL"

kinit -kt "$KEYTAB" "$PRINCIPAL" || { echo "❌ kinit failed"; exit 1; }

TMP_FILE="/tmp/solr_clusterstate_$(hostname -f)_$(date +%s).json"

solrctl cluster --get-clusterstate "$TMP_FILE" || { echo "❌ Failed to get cluster state"; exit 1; }

JSON=$(sed -n "/^{/,\$p" "$TMP_FILE")

echo "$JSON" | jq -r "
.cluster.collections
| to_entries[]
| \"✅ Collection: \(.key), Health: \(.value.health)\""

echo "$JSON" | jq -r "
.cluster.collections
| to_entries[]
| . as \$col
| .value.shards
| to_entries[]
| . as \$shard
| .value.replicas
| to_entries[]
| select(.value.state != \"active\")
| \"❌ Replica not active: \(\$col.key)/\(\$shard.key)/\(.key) => \(.value.state)\""

echo "$JSON" | jq -r "
.cluster.collections
| to_entries[]
| . as \$col
| .value.shards
| to_entries[]
| select((.value.replicas | to_entries[] | select(.value.leader == \"true\")) | length == 0)
| \"❌ Missing leader: \(\$col.key)/\(.key)\""

rm -f "$TMP_FILE"
' shell='/bin/bash' 2>/dev/null
