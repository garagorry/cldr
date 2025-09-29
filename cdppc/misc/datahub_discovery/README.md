# CDP Environment Discovery: DataHub, Datalake, and FreeIPA

This Python tool automates discovery, inspection, and export of resources within a CDP environment. It queries the CDP CLI for DataHub clusters, Datalakes, and FreeIPA details, gathers metadata, and exports JSON/CSV summaries. You can discover all DataHub clusters in an environment or target a specific cluster using the `--datahub-name` parameter. A timestamped output folder is created and compressed into a `.tar.gz` at the end.

---

## 🔧 Features

- Discovers resources in a CDP environment:
  - **Environment**: describe and flatten to CSV; FreeIPA upgrade options; FreeIPA instance groups to CSV
  - **Datalake**: list/describe, DB server, available/runtime images, instance groups to CSV, recipes discovery+export
  - **DataHub**: list/describe all clusters or a specific cluster, instance groups to CSV, upgrade images, DB server, recipes discovery+export
- Extracts instance group + volume metadata into:
  - Per-entity CSV (per DataHub cluster / per Datalake)
  - Aggregated CSVs across all DataHubs and across all Datalakes
- Retrieves and pretty-prints cluster template content (when applicable)
- Handles COD clusters by mapping DataHub `clusterName` to OPDB `databaseName` and describing the COD database
- Creates a timestamped output directory and a final `.tar.gz` archive
- Spinner indicators for long-running operations

---

## 🧪 Requirements

- Python 3.6+
- CDP CLI installed and configured with valid credentials
  - Validate with `cdp environments list-environments`

### 🔑 Note on CDP CLI

Ensure the **CDP CLI is installed and configured**. The script uses (among others):

- Environments: `cdp environments describe-environment`, `cdp environments get-freeipa-upgrade-options`
- DataHub: `list-clusters`, `describe-cluster`, `describe-cluster-template`, `upgrade-cluster --show-available-images`, `upgrade-cluster --show-latest-available-image-per-runtime`, `describe-database-server`, `describe-recipe`
- Datalake: `list-datalakes`, `describe-datalake`, `describe-database-server`, `upgrade-datalake --show-available-images`, `upgrade-datalake --show-latest-available-image-per-runtime`, `describe-recipe`
- OPDB/COD: `opdb list-databases`, `opdb describe-database`

````

## 🚀 Usage

```bash
python discovery_datahubs_per_env.py \
  --environment-name <env_name> \
  [--datahub-name <datahub_name>] \
  [--output-dir <path_prefix>] \
  [--profile <cdp_profile>] \
  [--debug]
```

Examples:

```bash
# Discover all DataHub clusters in an environment (original functionality)
python discovery_datahubs_per_env.py --environment-name ENV_PROD_USW1

# Discover a specific DataHub cluster
python discovery_datahubs_per_env.py \
  --environment-name ENV_PROD_USW1 \
  --datahub-name my-cluster

# Custom output folder prefix + profile + debug
python discovery_datahubs_per_env.py \
  --environment-name ENV_PROD_USW1 \
  --datahub-name my-cluster \
  --output-dir ./datahubs_output_ENV_PROD_USW1 \
  --profile prod \
  --debug
```

---

## 📦 How to Run on a Cloudera Manager Node with Virtual Environment

You can safely run this tool from a Cloudera Manager node without affecting the system Python:

```bash
# Switch to root
sudo -i

# Create a virtual environment under the root user's home
python3.11 -m venv ~/py3

# Activate the environment
source ~/py3/bin/activate

# Upgrade pip
pip install --upgrade pip

# No extra packages are strictly required, but you can install any optional packages here
# Example (if parsing from PostgreSQL output in extensions): pip install psycopg2-binary

# Create a scripts directory (optional)
mkdir ~/scripts

# Place the script in that directory
vi ~/scripts/discovery_datahubs_per_env.py

# Run the script
python3.11 ~/scripts/discovery_datahubs_per_env.py --environment-name <env_name>
```

💡 **Note:** Ensure `cdp` CLI is installed and configured for the root user or the user running the script.
Run `cdp environments list-environments` to validate access.

---

## 📂 Output

The script creates a timestamped output directory (default: `/tmp/discovery_datahubs-<timestamp>` or `<output-dir>-<timestamp>`) and a `.tar.gz` archive. Structure example:

```
discovery_datahubs-<timestamp>/
├── environment/
│   ├── ENVIRONMENT_ENV_<env>_<timestamp>.json
│   ├── ENVIRONMENT_ENV_<env>_<timestamp>.csv
│   ├── ENVIRONMENT_ENV_<env>_FreeIPAUpgradeOptions_<timestamp>.json
│   └── ENVIRONMENT_ENV_<env>_FreeIPAInstanceGroups_<timestamp>.csv
├── datalake/
│   └── <datalakeName>/
│       ├── ENVIRONMENT_ENV_<env>_DL_<datalakeName>_<timestamp>.json
│       ├── ENVIRONMENT_ENV_<env>_DL_<datalakeName>_DB_<timestamp>.json
│       ├── ENVIRONMENT_ENV_<env>_DL_<datalakeName>_AvailableImages_<timestamp>.json
│       ├── ENVIRONMENT_ENV_<env>_DL_<datalakeName>_RunTimeAvailableImages_<timestamp>.json
│       ├── ENVIRONMENT_ENV_<env>_DL_<datalakeName>_InstanceGroups_<timestamp>.csv
│       └── recipes/
│           ├── recipe_<name>.json
│           └── recipe_<name>.sh
├── <DataHubClusterName>/
│   ├── ENVIRONMENT_ENV_<env>_DH_<cluster>_<timestamp>.json
│   ├── ENVIRONMENT_ENV_<env>_DH_<cluster>_InstanceGroups_<timestamp>.csv
│   ├── ENVIRONMENT_ENV_<env>_DH_<cluster>_Template_<timestamp>.json
│   ├── ENVIRONMENT_ENV_<env>_DH_<cluster>_AvailableImages_<timestamp>.json
│   ├── ENVIRONMENT_ENV_<env>_DH_<cluster>_RunTimeAvailableImages_<timestamp>.json
│   ├── ENVIRONMENT_ENV_<env>_DH_<cluster>_DB_<timestamp>.json
│   ├── ENVIRONMENT_ENV_<env>_DH_<cluster>_COD_<timestamp>.json   # only for COD clusters
│   └── recipes/
│       ├── recipe_<name>.json
│       └── recipe_<name>.sh
├── ALL_<env>_datahub_instance_groups.csv          # when discovering all clusters
├── <env>_<cluster>_datahub_instance_groups.csv    # when discovering specific cluster
├── ALL_<env>_datalake_instance_groups.csv
└── discovery_datahubs-<timestamp>.tar.gz
```

---

## 📊 CSV Fields

Columns vary by resource type; inspect headers in generated CSVs for full detail. Common fields include:

- DataHub: `environment`, `clusterName`, `instanceGroupName`, `nodeGroupRole`, `instanceId`, `instanceType`, `instanceVmType`, `privateIp`, `publicIp`, `fqdn`, `status`, `statusReason`, `volumeCount`, `volumeType`, `volumeSize`
- Datalake: `environment`, `datalakeName`, `instanceGroupName`, `instanceId`, `discoveryFQDN`, `instanceStatus`, `instanceTypeVal`, `instanceVmType`, `availabilityZone`, `subnetId`, `volumeCount`, `volumeType`, `volumeSize`
- FreeIPA: `environment`, `freeipaInstanceGroupName`, `instanceId`, `instanceStatus`, `instanceType`, `instanceVmType`, `lifeCycle`, `privateIP`, `publicIP`, `discoveryFQDN`, `volumeCount`, `volumeType`, `volumeSize`

---

## 📘 Notes

- The script pretty-prints and parses the `clusterTemplateContent` embedded JSON field when present.
- Recipes are described and saved as both JSON and shell script content (if available).
- A final `.tar.gz` archive of the output directory is created for easy sharing.
- When using `--datahub-name`, the script validates that the specified cluster exists and provides helpful error messages if not found.
- CSV output files are named differently when targeting a specific cluster vs. all clusters for easy identification.
- Suitable for audits, upgrade planning, and environment diagnostics.

---
````
