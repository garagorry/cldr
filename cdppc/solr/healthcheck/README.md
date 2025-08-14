# ent_solr_health_check.sh

This script performs a comprehensive health check on Solr collections deployed in a Cloudera environment by remotely executing commands via Salt on targeted nodes. It automatically detects the environment type and provides detailed analysis of Solr cluster health.

---

## Description

`ent_solr_health_check.sh` connects to specified Salt minions (nodes) and verifies the health status of Solr collections, including shard and replica states. It requires running on a machine with Salt access and the Solr service configured.

The script automatically detects whether it's running on a Light Duty or Enterprise Data Lake and adjusts its behavior accordingly. It provides comprehensive health analysis including:

- Collections and their overall health status
- Shard states and distribution
- Replica states (active/inactive)
- Leader replica availability
- Visual indicators using emojis for better readability

---

## Features

- **Automatic Environment Detection**: Detects Light Duty vs Enterprise Data Lake automatically
- **Smart Target Selection**: Automatically targets the current node for Light Duty deployments
- **Comprehensive Health Analysis**: Checks collections, shards, replicas, and leader status
- **Enhanced JSON Processing**: Uses `jq` for robust JSON parsing and analysis
- **Visual Feedback**: Emoji-based output for better user experience
- **Flexible Targeting**: Supports custom Salt targets with regex patterns
- **Logging Support**: Optional logging to `/var/log/solr_health_check/`
- **Dry-run Mode**: Preview commands without execution

---

## Usage

```bash
./ent_solr_health_check.sh [options]
```

### Options

| Option | Description                                                | Default                 |
| ------ | ---------------------------------------------------------- | ----------------------- |
| `-t`   | Salt target (minion FQDN or regex)                         | `*core0*.cloudera.site` |
| `-l`   | Enable logging to `/var/log/solr_health_check`             | Disabled                |
| `-n`   | Dry-run mode: prints the Salt command but does not execute | Disabled                |

---

## Examples

- Run health check on default target, no logging:

  ```bash
  ./ent_solr_health_check.sh
  ```

- Run health check on specific node (example FQDN):

  ```bash
  ./ent_solr_health_check.sh -t '*core03*.cloudera.site'
  ```

- Run with logging enabled:

  ```bash
  ./ent_solr_health_check.sh -l
  ```

- Dry-run mode (print command only):

  ```bash
  ./ent_solr_health_check.sh -n
  ```

---

## Environment Detection

The script automatically detects the environment type:

- **Light Duty Data Lake**: Detected when running on a `-master0.*.cloudera.site` node
  - Automatically targets the current node
  - Optimized for single-node deployments
- **Enterprise Data Lake**: Detected for all other environments
  - Uses the specified target pattern (default: `*core0*.cloudera.site`)
  - Supports multi-node cluster analysis

---

## Health Check Details

The script performs the following health checks:

1. **Collection Status**: Lists all collections and their shard states
2. **Replica Health**: Identifies replicas that are not in "active" state
3. **Leader Availability**: Detects shards missing leader replicas
4. **Authentication**: Verifies Solr keytab availability and Kerberos authentication

---

## Requirements

- Salt client installed and configured to connect to your cluster minions
- `jq` installed on the remote nodes to parse JSON
- The script must be executed from a Cloudera Manager Node (Salt Master)
- Remote nodes must be running Solr with Cloudera SCM agent processes
- The Salt target must be the full FQDN or a valid wildcard/regex matching the minion
- `activate_salt_env` script must be available in the PATH

---

## Logging

If logging is enabled via `-l`, logs are stored under:

```
/var/log/solr_health_check/solr_health_check_<timestamp>.log
```

---

## Troubleshooting

- **No minions matched the target:**
  Make sure to provide a fully qualified domain name (FQDN) or a valid wildcard/regex target such as `*core1*.cloudera.site`.

- **Keytab or authentication errors:**
  The script assumes Solr keytabs are available on the targeted minions. Errors will be displayed if keytabs or principals cannot be found or used.

- **Environment detection issues:**
  Ensure the script is running on a properly configured Cloudera node with the correct hostname format.

- **jq dependency:**
  Verify that `jq` is installed on all target nodes for proper JSON parsing.

---
