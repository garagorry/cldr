#!/bin/bash
set -euo pipefail

spinner() {
  local pid=$1
  local delay=0.1
  local spinstr='|/-\'
  while kill -0 "$pid" 2>/dev/null; do
    for (( i=0; i<${#spinstr}; i++ )); do
      printf "\r⏳ %c Processing..." "${spinstr:i:1}"
      sleep $delay
    done
  done
  printf "\r"
}

echo "🔍 Starting Atlas Kafka lineage check..."

ATLAS_KT=$(find /run/cloudera-scm-agent/process -wholename "*atlas-ATLAS_SERVER/atlas.keytab" 2>/dev/null | head -n 1)

if [[ -z "$ATLAS_KT" ]]; then
  echo "❌ ERROR: Atlas keytab file not found under /run/cloudera-scm-agent/process!"
  exit 1
fi

if [[ ! -f jaas.conf ]]; then
  ATLAS_PRINCIPAL=$(klist -kt "${ATLAS_KT}" | grep -o -m 1 "atlas\/\S*")
  printf "KafkaClient {\n\tcom.sun.security.auth.module.Krb5LoginModule required\n\tuseKeyTab=true\n\tkeyTab=\"%s\"\n\tprincipal=\"%s\";\n};\n" \
    "${ATLAS_KT}" "${ATLAS_PRINCIPAL}" > jaas.conf
fi

if [[ ! -f client.config ]]; then
  printf "security.protocol=SASL_SSL\nsasl.kerberos.service.name=kafka\n" > client.config
fi

KAFKA_SERVER=$(grep --line-buffered -oP "atlas.kafka.bootstrap.servers=\K.*" /etc/atlas/conf/atlas-application.properties | awk -F',' '{print $1}')

if [[ -z "$KAFKA_SERVER" ]]; then
  echo "❌ ERROR: Could not find Kafka bootstrap server in atlas-application.properties"
  exit 1
fi

export KAFKA_HEAP_OPTS="-Xms512m -Xmx1g"
export KAFKA_OPTS="-Djava.security.auth.login.config=${PWD}/jaas.conf"

echo "🔐 Authenticating with kinit..."
kinit -kt "$ATLAS_KT" "atlas/$(hostname -f)" 2>/dev/null || {
  echo "❌ kinit failed"
  exit 1
}
echo "✅ kinit successful"

echo "⏳ Fetching Atlas lineage info (this may take a while)..."
/opt/cloudera/parcels/CDH/lib/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server "${KAFKA_SERVER}" --describe --group atlas --command-config="${PWD}/client.config" 2>/dev/null &
PID=$!
spinner $PID
wait $PID

# Capture lineage info, extracting topic and lag
LINEAGE_INFO=$(/opt/cloudera/parcels/CDH/lib/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server "${KAFKA_SERVER}" --describe --group atlas --command-config="${PWD}/client.config" 2>/dev/null | awk '{print $2, $6}')

if [[ -z "$LINEAGE_INFO" ]]; then
  echo "*ERROR*: Unable to get lineage info for Atlas. Please look at the created configuration files to make sure they look correct."
  exit 1
fi

echo "📊 Parsing lineage information..."

LINEAGE_LAG_VALS=($LINEAGE_INFO)
NUM_LAG_VALS=${#LINEAGE_LAG_VALS[@]}
OUT_OF_DATE_TOPICS=""

for (( i = 2; i < NUM_LAG_VALS; i += 2 )); do
  lag_index=$((i + 1))
  if [[ "${LINEAGE_LAG_VALS[$lag_index]}" != "-" && "${LINEAGE_LAG_VALS[$lag_index]}" != "0" ]]; then
    OUT_OF_DATE_TOPICS+="${LINEAGE_LAG_VALS[$i]}, "
  fi
done

if [[ -z "$OUT_OF_DATE_TOPICS" ]]; then
  echo "✅ Atlas is up to date! Feel free to continue with the resize/upgrade."
else
  echo "⚠️ The following Atlas topics are not up to date: ${OUT_OF_DATE_TOPICS%??}!"
  echo "Please wait until Atlas is entirely up to date before continuing with the resize/upgrade."
fi
