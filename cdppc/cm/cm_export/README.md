# cm_export_all_service_configs.sh

This script exports **Cloudera Manager service and role configurations** into a flattened, sanitized CSV format for analysis, backup, or auditing purposes.

---

## 🎯 Purpose

- Extracts all service- and role-level configuration values from a Cloudera Manager cluster.
- Handles **nested XML config values** and expands them into individual key-value pairs.
- **Sanitizes sensitive values** (passwords, tokens, credentials, etc.).
- Stores results in a single CSV: `all_services_config.csv`.
- Creates a compressed archive with all JSON config exports and the CSV.

---

## 📦 Output Example

```

/tmp/<host>/<timestamp>/
├── ServiceConfigs/
│   └── <host>*<cluster>*<service>*config.json
├── roleConfigGroups/
│   └── <host>*<cluster>\_<role>*config.json
├── all\_services\_config.csv
└── ServiceConfigs\_roleConfigGroups*<timestamp>.tgz

```

---

## 🛠️ Prerequisites

Ensure the following tools are installed:

- `curl`
- `jq`
- `xmlstarlet`
- `psql` (PostgreSQL client, for reading CM database)

To install on RHEL/CentOS:

```bash
sudo dnf install curl jq xmlstarlet postgresql -y
```

---

## 🔐 Requirements

- Run the script as **root**:
  `sudo -i` before execution.
- Cloudera API redaction must be disabled.

To disable API redaction:

```bash
sudo vi /etc/default/cloudera-scm-server
# Add or modify the line:
CMF_JAVA_OPTS="-Dcom.cloudera.api.redaction=false"

# Restart CM:
sudo systemctl restart cloudera-scm-server
```

---

## 🚀 How to Run

```bash
sudo ./cm_export_all_service_configs.sh
```

You will be prompted for:

- Cloudera **Workload username**
- **Workload password** (hidden input)

---

## 📤 Output

The final archive will be displayed and contains:

- `ServiceConfigs/*.json`
- `roleConfigGroups/*.json`
- `all_services_config.csv`

---

## 🧪 Sample CSV Output

| type    | service_or_role | property                | value         |
| ------- | --------------- | ----------------------- | ------------- |
| service | HDFS            | dfs.datanode.data.dir   | /data/dfs     |
| role    | HDFS-DATANODE   | log.dir                 | /var/log/hdfs |
| service | HIVE            | hive.metastore.password | \*\*\*\*      |

---

## 📝 Notes

- Sensitive fields are automatically masked.
- Output folder is generated under `/tmp/<hostname>/<timestamp>`.
