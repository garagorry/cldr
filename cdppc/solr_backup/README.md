# Solr Collection Backup to HDFS

This script automates the process of backing up all Solr collections into HDFS using Solr’s collection backup API. It authenticates via Kerberos and supports environments managed by Cloudera Manager.

## 📌 Requirements

- Must be executed **as root**
- Must be run **from a Solr node** (a host where `solr-SOLR_SERVER` is running)
- Environment must have:
  - `kinit`, `kdestroy`, and `klist` available
  - `hdfs` CLI access
  - Kerberos keytabs managed under `/var/run/cloudera-scm-agent/process/`
  - Solr running with Kerberos and configured with backup support (e.g., HDFS or FS repository)

## 🔐 Permissions

This script requires **root access** to:

- Locate and use service keytabs (e.g., `solr.keytab`, `hdfs.keytab`)
- Perform Kerberos authentication with service principals

## ⚙️ What It Does

1. **Authenticates as HDFS service user** to create the backup directory in HDFS.
2. **Creates a unique timestamped backup location** under `/user/solr/backup/`.
3. **Authenticates as Solr service user** to interact with the Solr collections API.
4. **Backs up all collections** found in the SolrCloud instance to the specified HDFS location.
5. **Lists the contents** of the created backup directory for verification.

## 🚀 Usage

Run the script as root:

```bash
chmod +x ./solr_backup_to_hdfs.sh
./solr_backup_to_hdfs.sh
````

## 📝 Notes

* Backup location format: `/user/solr/backup/YYYYMMDDHHMMSS`
* Script uses `jq` for JSON parsing. Install via:

  ```bash
  sudo yum install -y jq   # RHEL/CentOS
  sudo apt install -y jq   # Debian/Ubuntu
  ```

## 🧪 Example Output

```bash
[2025-05-31 10:15:22] Preparing HDFS backup location
[2025-05-31 10:15:25] Triggering Solr collection backup
[2025-05-31 10:15:27] Backing up collection: logs
[2025-05-31 10:15:32] Backing up collection: metrics
[2025-05-31 10:15:35] Backup complete. Contents of backup directory:
Found 4 items
drwxrwxrwx   - solr solr          0 2025-05-31 23:44 /user/solr/backup/20250531234412/edge_index_backup
drwxrwxrwx   - solr solr          0 2025-05-31 23:44 /user/solr/backup/20250531234412/fulltext_index_backup
drwxrwxrwx   - solr solr          0 2025-05-31 23:44 /user/solr/backup/20250531234412/ranger_audits_backup
drwxrwxrwx   - solr solr          0 2025-05-31 23:44 /user/solr/backup/20250531234412/vertex_index_backup
```

## 📂 Backup Location Example

```
hdfs://<namenode>/user/solr/backup/20250531101522/
/user/solr/backup/20250531101522/
```
