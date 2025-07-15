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

The script must be executed on a Cloudera Manager host as `root`. It requires the following tools to be installed:

- `curl`
- `jq`
- `xmlstarlet`
- `psql` (PostgreSQL client, for reading CM database)

The script depends on the `xmlstarlet` utility along with several essential system libraries. While these packages and their dependencies are planned to be included in the Cloudera On Cloud repository, you can manually download and install them from RPM packages as needed.

### Required RPM Packages (RHEL 8.x base)

The following RPM packages are required for proper execution of the script and its dependencies:

- basesystem-11-5.el8.noarch.rpm
- bash-4.4.20-5.el8.x86_64.rpm
- filesystem-3.8-6.el8.x86_64.rpm
- glibc-2.28-251.el8_10.16.x86_64.rpm
- glibc-all-langpacks-2.28-251.el8_10.16.x86_64.rpm
- glibc-common-2.28-251.el8_10.16.x86_64.rpm
- glibc-gconv-extra-2.28-251.el8_10.16.x86_64.rpm
- libgcrypt-1.8.5-7.el8_6.x86_64.rpm
- libgpg-error-1.31-1.el8.x86_64.rpm
- libselinux-2.9-10.el8_10.x86_64.rpm
- libsepol-2.9-3.el8.x86_64.rpm
- libxml2-2.9.7-19.el8_10.x86_64.rpm
- libxslt-1.1.32-6.1.el8_10.x86_64.rpm
- ncurses-base-6.1-10.20180224.el8.noarch.rpm
- ncurses-libs-6.1-10.20180224.el8.x86_64.rpm
- pcre2-10.32-3.el8_6.x86_64.rpm
- redhat-release-8.10-0.3.el8.x86_64.rpm
- redhat-release-eula-8.10-0.3.el8.x86_64.rpm
- setup-2.12.2-9.el8.noarch.rpm
- tzdata-2025b-1.el8.noarch.rpm
- xmlstarlet-1.6.1-20.el8.x86_64.rpm
- xz-libs-5.2.4-4.el8_6.x86_64.rpm
- zlib-1.2.11-25.el8.x86_64.rpm

---

## Installing `xmlstarlet` on RHEL 8.x

A full set of RPMs (including dependencies) can be downloaded and installed using the steps below:

### 🧰 Automated Installation

```bash
# Step 1: Create working directory
mkdir -p /var/tmp/xmlstarlet-rpms
cd /var/tmp/xmlstarlet-rpms

# Step 2: Download required packages
export BASE_URL="https://github.com/garagorry/cldr/raw/refs/heads/main/cdppc/upgrades/misc/tmp_rpms/xmlstarlet-rpms"
for package in \
basesystem-11-5.el8.noarch.rpm \
bash-4.4.20-5.el8.x86_64.rpm \
filesystem-3.8-6.el8.x86_64.rpm \
glibc-2.28-251.el8_10.16.x86_64.rpm \
glibc-all-langpacks-2.28-251.el8_10.16.x86_64.rpm \
glibc-common-2.28-251.el8_10.16.x86_64.rpm \
glibc-gconv-extra-2.28-251.el8_10.16.x86_64.rpm \
libgcrypt-1.8.5-7.el8_6.x86_64.rpm \
libgpg-error-1.31-1.el8.x86_64.rpm \
libselinux-2.9-10.el8_10.x86_64.rpm \
libsepol-2.9-3.el8.x86_64.rpm \
libxml2-2.9.7-19.el8_10.x86_64.rpm \
libxslt-1.1.32-6.1.el8_10.x86_64.rpm \
ncurses-base-6.1-10.20180224.el8.noarch.rpm \
ncurses-libs-6.1-10.20180224.el8.x86_64.rpm \
pcre2-10.32-3.el8_6.x86_64.rpm \
redhat-release-8.10-0.3.el8.x86_64.rpm \
redhat-release-eula-8.10-0.3.el8.x86_64.rpm \
setup-2.12.2-9.el8.noarch.rpm \
tzdata-2025b-1.el8.noarch.rpm \
xmlstarlet-1.6.1-20.el8.x86_64.rpm \
xz-libs-5.2.4-4.el8_6.x86_64.rpm \
zlib-1.2.11-25.el8.x86_64.rpm ; do
    wget ${BASE_URL}/${package}
done

# Step 3: Install xmlstarlet and its dependencies
yum localinstall -y xmlstarlet-1.6.1-20.el8.x86_64.rpm
```

### ✅ Validate Installation

```bash
xmlstarlet --version
```

> **Note:** These RPM files can be organized within a local directory such as `/var/tmp/xmlstarlet-rpms/` for convenience.

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
