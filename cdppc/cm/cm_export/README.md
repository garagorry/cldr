# cm_export_all_service_configs.sh

This script exports **Cloudera Manager service and role configurations** into a flattened, sanitized CSV format for analysis, backup, or auditing purposes.

---

## 🎯 Purpose

- Extracts all service- and role-level configuration values from a Cloudera Manager cluster.
- Handles **nested XML config values** and expands them into individual key-value pairs.
- **Sanitizes sensitive values** (passwords, tokens, credentials, etc.).
- **Processes role config groups** with multi-line properties as single entities.
- Creates **individual PUT payloads** for each property within role config groups.
- Stores results in a single CSV: `all_services_config.csv`.
- Creates a compressed archive with all JSON config exports and the CSV.

---

## 📦 Output Example

```
/tmp/<host>/<timestamp>/
├── ServiceConfigs/
│   └── <host>*<cluster>*<service>*config.json
├── roleConfigGroups/
│   └── <host>*<cluster>_<role>*config.json
├── api_control_files/
│   ├── service_configs/
│   │   ├── get_service_config_calls.csv
│   │   └── put_service_config_calls.csv
│   └── role_configs/
│       ├── get_role_config_calls.csv
│       └── put_role_config_calls.csv
├── all_services_config.csv
└── ServiceConfigs_roleConfigGroups*<timestamp>.tgz
```

---

## 🛠️ Prerequisites

The script must be executed on a Cloudera Manager host as `root`. It requires the following tools to be installed:

- `curl`
- `jq`
- `xmlstarlet`
- `psql` (PostgreSQL client, for reading CM database)

The script depends on the `xmlstarlet` utility along with several essential system libraries. While these packages and their dependencies are planned to be included in the Cloudera On Cloud repository, you can manually download and install them from RPM packages as needed.

### Required RPM Packages (RHEL 8.x base)

The following RPM packages are required for proper execution of the script and its dependencies:

- xmlstarlet-1.6.1-20.el8.x86_64.rpm

## Installing `xmlstarlet` on RHEL 8.x

```bash
# Install xmlstarlet and its dependencies
yum localinstall -y https://github.com/garagorry/cldr/raw/refs/heads/main/cdppc/upgrades/misc/tmp_rpms/xmlstarlet-rpms/xmlstarlet-1.6.1-20.el8.x86_64.rpm
```

### ✅ Validate Installation

```bash
xmlstarlet --version
```

Once installed, you can execute the extraction script safely on your Cloudera Manager host.

---

## 🔐 Requirements

- Run the script as **root**:
  `sudo -i` before execution.
- Cloudera API redaction must be disabled.

To disable API redaction:

```bash
sudo vi /etc/default/cloudera-scm-server
# Add or modify the line:
# export CMF_JAVA_OPTS with "-Dcom.cloudera.api.redaction=false"
export CMF_JAVA_OPTS="-Xmx4G -XX:MaxPermSize=256m -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp -Dcom.sun.management.jmxremote.ssl.enabled.protocols=TLSv1.2 -Dcom.cloudera.api.redaction=false"

# Restart CM:
systemctl restart cloudera-scm-server && ( tail -f -n0 /var/log/cloudera-scm-server/cloudera-scm-server.log  & ) | grep -q -i 'started jetty server'
```

---

## 🚀 How to Run

```bash
#  ./cm_export_all_service_configs.sh
```

You will be prompted for:

- Cloudera **Workload username**
- **Workload password** (hidden input)

---

## 📤 Output

The final archive will be displayed and contains:

- `ServiceConfigs/*.json`
- `roleConfigGroups/*.json`
- `api_control_files/` - GET and PUT API call templates
- `all_services_config.csv`

---

## 🧪 Sample CSV Output

| type    | service_or_role         | property                                            | value                                                                                                                                                                                       |
| ------- | ----------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| service | HDFS                    | dfs.datanode.data.dir                               | /data/dfs                                                                                                                                                                                   |
| role    | HDFS-DATANODE           | log.dir                                             | /var/log/hdfs                                                                                                                                                                               |
| service | HIVE                    | hive.metastore.password                             | \*\*\*\*                                                                                                                                                                                    |
| role    | atlas-ATLAS_SERVER-BASE | conf/atlas-application.properties_role_safety_valve | atlas.audit.persistEntityDefinition=false\natlas.audit.hbase.entity.spark_process.attributes.exclude=details,sparkPlanDescription\natlas.server.ha.zookeeper.session.timeout.ms=450000\n... |

---

## 🔧 Recent Updates & Enhancements

### Role Config Groups Processing

The script has been enhanced to properly handle role config groups with multi-line properties:

#### **Before vs. After**

- **Before**: The script only processed simple key-value pairs for role configs
- **After**: Now handles both simple properties and complex multi-line properties (like `conf/atlas-application.properties_role_safety_valve`)

#### **Individual PUT Payloads**

- **Before**: Single PUT command per role config group
- **After**: Individual PUT command for each property within a role config group (each property gets its own PUT call with its complete value)

#### **Proper CSV Generation**

- **Before**: Limited role config information in CSV
- **After**: Complete role config properties with individual entries for each property

### Example Role Config Output

#### **For Simple Property**

```
PUT /api/v53/clusters/CLUSTER/services/atlas/roleConfigGroups/atlas-ATLAS_SERVER-BASE/config
{
  "items": [
    {
      "name": "ATLAS_SERVER_role_env_safety_valve",
      "value": "ATLAS_CUSTOM_OPTS=-XX:MaxNewSize=3461m"
    }
  ]
}
```

#### **For Multi-line Property**

```
PUT /api/v53/clusters/CLUSTER/services/atlas/roleConfigGroups/atlas-ATLAS_SERVER-BASE/config
{
  "items": [
    {
      "name": "conf/atlas-application.properties_role_safety_valve",
      "value": "atlas.audit.persistEntityDefinition=false\natlas.audit.hbase.entity.spark_process.attributes.exclude=details,sparkPlanDescription\natlas.server.ha.zookeeper.session.timeout.ms=450000\n..."
    }
  ]
}
```

---

## 📋 CSV Output Structure

The script now generates:

1. **Master CSV**: Contains all properties with type, service/role, property name, value, and API URI
2. **Control Files**:
   - `get_service_config_calls.csv` - GET API calls for each service config
   - `put_service_config_calls.csv` - PUT API calls for each service config property
   - `get_role_config_calls.csv` - GET API calls for each role config group
   - `put_role_config_calls.csv` - PUT API calls for each individual property

---

## ✅ Benefits

1. **Granular Control**: Each property can be updated individually
2. **Better Audit Trail**: Complete visibility into all service and role config properties
3. **Proper API Payloads**: Correct JSON structure for Cloudera Manager API calls
4. **Multi-line Support**: Handles complex properties with newline-separated values as single properties (not split into individual lines)
5. **Consistent Processing**: Same logic used for both service and role configs
6. **Improved Readability**: JSON payloads are properly formatted with line breaks for easier debugging
7. **API Control Files**: Ready-to-use GET and PUT command templates for automation

---

## 🛠️ Technical Details

### JSON Formatting Fix

The script now generates properly formatted, multi-line JSON payloads instead of single-line JSON for both service and role configs:

**Before (Single Line)**:

```bash
SERVICE_PUT_CMD="curl ... -d '{\"items\":[{\"name\":\"${key}\",\"value\":\"${val_cleaned}\"}]}'"
ROLE_PUT_CMD="curl ... -d '{\"items\":[{\"name\":\"${key}\",\"value\":\"${val_cleaned}\"}]}'"
```

**After (Multi-line)**:

```bash
SERVICE_PUT_CMD="curl ... -d '{
  \"items\": [
    {
      \"name\": \"${key}\",
      \"value\": \"${val_cleaned}\"
    }
  ]
}'"

ROLE_PUT_CMD="curl ... -d '{
  \"items\": [
    {
      \"name\": \"${key}\",
      \"value\": \"${val_cleaned}\"
    }
  ]
}'"
```

**Benefits**:

- **Readability**: JSON payloads are easier to read and debug
- **Standards**: Follows standard JSON formatting conventions
- **Maintenance**: Easier to maintain and modify the script
- **Validation**: Still generates valid JSON that can be parsed by APIs
- **Consistency**: Both service and role configs use the same formatting style

### Multi-line Value Handling

The `sanitize_role_value` function now properly converts actual newlines to `\n` escape sequences for JSON compatibility:

```bash
sanitize_role_value() {
    local val="$1"
    # Use jq to properly escape the value for JSON (this handles newlines correctly)
    # Remove the outer quotes that jq adds since we're building JSON manually
    printf '%s' "$val" | sed 's/{{CM_AUTO_TLS}}/****/g' | sed 's/"/""/g' | jq -Rs . | sed 's/^"//;s/"$//'
}
```

**Key changes**:

- **Newline conversion**: `jq -Rs .` automatically converts actual newlines to `\n` escape sequences
- **JSON compatibility**: Ensures the generated JSON payload is valid and can be parsed by JSON parsers
- **Regex preservation**: Maintains regex patterns like `sandbox_.*\..*` without breaking JSON syntax
- **Reliable escaping**: Uses `jq` which is designed to handle JSON escaping properly
- **Quote handling**: Removes outer quotes from jq output since we're building JSON structure manually

---

## 📝 Notes

- Sensitive fields are automatically masked.
- Output folder is generated under `/tmp/<hostname>/<timestamp>`.
- Multi-line properties in role configs are preserved as single entities with `\n` separators.
- Generated PUT commands are ready for direct use with Cloudera Manager API.
- All JSON payloads are properly formatted and valid for API consumption.
