# ent_solr_health_check.sh

This script performs a health check on Solr collections deployed in a Cloudera environment by remotely executing commands via Salt on targeted nodes.

---

## Description

`ent_solr_health_check.sh` connects to specified Salt minions (nodes) and verifies the health status of Solr collections, including shard and replica states. It requires running on a machine with Salt access and the Solr service configured.

The script outputs summary information on:

- Collections and their overall health
- Replicas that are not active
- Shards missing a leader replica

---

## Usage

```bash
./ent_solr_health_check.sh [options]
````

### Options

| Option | Description                                                | Default                 |
| ------ | ---------------------------------------------------------- | ----------------------- |
| `-t`   | Salt target (minion FQDN or regex)                         | `*core0*.cloudera.site` |
| `-l`   | Enable logging to `/var/log/solr_health_check`             | Disabled                |
| `-n`   | Dry-run mode: prints the Salt command but does not execute | Disabled                |

---

## Examples

* Run health check on default target, no logging:

  ```bash
  ./ent_solr_health_check.sh
  ```

* Run health check on specific node (example FQDN):

  ```bash
  ./ent_solr_health_check.sh -t '*core03*.cloudera.site'
  ```

* Run with logging enabled:

  ```bash
  ./ent_solr_health_check.sh -l
  ```

* Dry-run mode (print command only):

  ```bash
  ./ent_solr_health_check.sh -n
  ```

---

## Requirements

* Salt client installed and configured to connect to your cluster minions.
* `jq` installed on the remote nodes to parse JSON.
* The script must be executed from a Cloudera Manager Node - The Salt Master
* Remote nodes must be running Solr with Cloudera SCM agent processes.
* The Salt target must be the full FQDN or a valid wildcard/regex matching the minion.

---

## Logging

If logging is enabled via `-l`, logs are stored under:

```
/var/log/solr_health_check/solr_health_check_<timestamp>.log
```

---

## Troubleshooting

* **No minions matched the target:**
  Make sure to provide a fully qualified domain name (FQDN) or a valid wildcard/regex target such as `*core1*.cloudera.site`.

* **Keytab or authentication errors:**
  The script assumes Solr keytabs are available on the targeted minions. Errors will be displayed if keytabs or principals cannot be found or used.

---
