# Cloudera Manager Configuration Export Script

## Overview

`cm_export_all_service_configs.sh` is a Cloudera-focused Bash utility designed to automate the **secure extraction** of service and role configuration properties directly from a **running Cloudera Manager (CM) host**.

This script is ideal for:

- 🔍 **Auditing configurations**
- 💾 **Creating a sanitized backup**
- 📦 **Packaging configs for transfer or offline analysis**

It connects to the Cloudera Manager API, gathers configuration data (including embedded XML properties), **sanitizes sensitive information**, and outputs a structured CSV report along with raw JSON files — all packaged into a `.tgz` archive.

---

## Key Features

- 🔐 **Sensitive value masking** (e.g., passwords, tokens, keys)
- 📁 **CSV report generation** for all service and role configurations
- 📦 **Outputs a portable archive** for auditing or support
- 📄 Handles nested XML `<property>` entries within config values

---

## Prerequisites

The script must be executed on a Cloudera Manager host as `root`. It requires the following tools to be installed:

- `curl`
- `jq`
- `xmlstarlet`

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

## Usage

Run the script as root on a Cloudera Manager host:

```bash
./cm_export_all_service_configs.sh
```

You will be prompted for your **Workload username and password**. The script will:

1. Connect to the Cloudera Manager API
2. Detect the cluster name from the SCM DB
3. Fetch service- and role-level configurations
4. Sanitize any sensitive data
5. Write all output to:
   `/tmp/<hostname>/<timestamp>/`
6. Generate and display a `.tgz` archive with all exported data

---

## Output

The script produces the following:

- `ServiceConfigs/` – Raw service config JSONs
- `roleConfigGroups/` – Raw role config JSONs
- `all_services_config.csv` – Flattened and sanitized CSV with all properties
- `ServiceConfigs_roleConfigGroups_<timestamp>.tgz` – Compressed archive with all of the above

---

## Example Use Cases

- 🔒 Security reviews (verifying sensitive keys are masked)
- 📋 Audit trails for cluster snapshots
- 🚀 Migration or upgrade planning (offline config review)
- 💼 Sharing with Cloudera Support

---

## Notes

- If Cloudera Manager is using **API redaction**, the script will prompt you to disable it temporarily by setting:

  ```bash
  -Dcom.cloudera.api.redaction=false
  ```

- Make sure the script has access to `/etc/cloudera-scm-server/db.properties` to query the active cluster.
