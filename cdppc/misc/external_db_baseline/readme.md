# Hive Metastore Statistics Collector

This tool extracts summary statistics from a PostgreSQL-based Hive Metastore (e.g., used in Cloudera CDP), such as table counts, partition details, and types of tables.

## Features

- Connects to PostgreSQL using parameters extracted from a SaltStack `.sls` pillar file.
- Runs a set of pre-defined Hive Metastore SQL queries.
- Outputs results in structured JSON format.
- Includes logging and basic error handling.

## Requirements

- Python 3.6+
- PostgreSQL client library (`psycopg2`)
- `jq` installed on the host (used to parse the `.sls` file)
- `sed` (usually pre-installed on Linux systems)

## Installation

```bash
pip install psycopg2-binary
pip install tqdm
```

## Usage

```bash
python3 hive_metastore_stats.py [-o OUTPUT_FILE]
```

### Options

- `-o`, `--output`: Path to save the JSON output. Defaults to `./hive_stats_<timestamp>.json`.

### Example

```bash
python3 hive_metastore_stats.py -o /tmp/hive_stats.json
```

## Running from Cloudera Manager Node (Virtual Environment)

To safely execute the script on the **Active Cloudera Manager node** without affecting the system Python, you can use a dedicated Python 3.11 virtual environment:

```bash
# Switch to root
sudo -i

# Create a virtual environment under the root user's home
python3.11 -m venv ~/py3

# Activate the environment
source ~/py3/bin/activate

# Upgrade pip and setup tools
pip install --upgrade pip
pip install --upgrade pip setuptools wheel

# Install required package
pip install psycopg2-binary

# Create a scripts directory (optional)
mkdir ~/scripts

# Place the script in that directory
vi ~/scripts/db_sql_validation.py

# Run the script
python3.11 ~/scripts/db_sql_validation.py
```

> 💡 You can also use `-o /tmp/output.json` to specify a custom path for the output file.

## Assumptions

- The script reads connection parameters from the Salt pillar file located at:

  ```
  /srv/pillar/postgresql/postgre.sls
  ```

- The file is expected to contain the following structure (example):

  ```yaml
  hive:
    remote_admin: hive_user
    remote_admin_pw: secret
    remote_db_port: 5432
    remote_db_url: db.internal
    database: metastore
  ```

## Output

The resulting JSON will contain entries like:

```json
{
  "total_tables": [
    {
      "total_tables": 1240
    }
  ],
  "external_tables": [
    {
      "external_table_count": 378
    }
  ]
}
```
