# CDP DataHub Cluster Discovery and Instance Group Export Tool

This Python script automates the discovery, inspection, and export of Cloudera DataHub cluster information within a specified CDP environment. It queries the CDP CLI for DataHub clusters, gathers detailed metadata, and exports JSON and CSV summaries.

## 🔧 Features

- Discovers all DataHub clusters in a given environment
- Describes each cluster and its resources
- Extracts instance group and node information into:
  - **Per-cluster CSV** with detailed instance + volume metadata
  - **Global CSV** aggregating all instance groups
- Retrieves:
  - Available upgrade images
  - Latest runtime image per runtime
  - Database server metadata (if available)
  - Cluster template metadata with parsed and formatted `clusterTemplateContent`
- Adds spinner indicators for long-running operations
- Organized output structure per execution

## 🧪 Requirements

- Python 3.6+
- CDP CLI must be configured and authenticated
- Required access to the `cdp datahub` APIs

## 🚀 Usage

```bash
python discovery_datahubs_per_env.py <environment-name>
```

Example:

```bash
python discovery_datahubs_per_env.py ENV_PROD_USW1
```

## 📂 Output

The script generates a timestamped directory like:

```
datahubs_output_ENV_PROD_USW1_20250711XXXXXX/
├── ENVIRONMENT_ENV_ENV_PROD_USW1_DH_<cluster>_<timestamp>.json
├── ENVIRONMENT_ENV_ENV_PROD_USW1_DH_<cluster>_InstanceGroups_<timestamp>.csv
├── ENVIRONMENT_ENV_ENV_PROD_USW1_DH_<cluster>_Template_<timestamp>.json
├── ENVIRONMENT_ENV_ENV_PROD_USW1_DH_<cluster>_AvailableImages_<timestamp>.json
├── ENVIRONMENT_ENV_ENV_PROD_USW1_DH_<cluster>_RunTimeAvailableImages_<timestamp>.json
├── ENVIRONMENT_ENV_ENV_PROD_USW1_DH_<cluster>_DB_<timestamp>.json
├── ALL_ENV_ENV_PROD_USW1_InstanceGroups_<timestamp>.csv
```

## 📊 CSV Fields

| Field                 | Description                                 |
| --------------------- | ------------------------------------------- |
| environment           | CDP environment name                        |
| clusterName           | DataHub cluster name                        |
| instanceGroupName     | Instance group name (e.g., leader, worker)  |
| nodeGroupRole         | Role of the node in the cluster             |
| instanceId            | Cloud provider instance ID                  |
| instanceType          | CDP role type (e.g., CORE, GATEWAY_PRIMARY) |
| instanceVmType        | VM type (e.g., m5.2xlarge)                  |
| privateIp/publicIp    | Network IPs                                 |
| volumeCount/Size/Type | EBS volume details                          |
| fqdn                  | Host FQDN                                   |
| status                | Instance status (e.g., SERVICES_HEALTHY)    |

## 📘 Notes

- The script pretty-prints and parses the `clusterTemplateContent` embedded JSON field.
- Output is safe to version or attach to Support tickets for upgrade planning.
- This is especially useful for Cloudera PS/CSA/SE teams performing environment diagnostics.
