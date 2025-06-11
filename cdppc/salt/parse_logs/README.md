# Salt Log Hourly Parser

This Python script processes Salt master/minion logs by grouping entries per hour and compressing them. It also generates summary files identifying which hourly logs contain warnings or errors.

## 🔧 Features

- Accepts a Salt log file as input using `--file`
- Groups logs into hourly buckets (`YYYY-MM-DD HH`)
- Outputs compressed `.log.gz` files per hour
- Optional `--output-dir` to specify a parent directory
  - If omitted, defaults to `/var/tmp/salt/`
  - All output is saved under `logs_<timestamp>/` inside the chosen base directory
- Generates:
  - `error_files.log`: files that contain `[ERROR]`
  - `warning_files.log`: files that contain `[WARNING]`
- Shows a progress bar using `tqdm` for large files
- Checks file existence and read permissions

## 📥 Usage

```bash
./parse_salt_logs.py --file /var/log/salt/master
````

With custom output directory:

```bash
./parse_salt_logs.py --file /var/log/salt/master --output-dir /tmp/salt_logs
```

Example structure:

```
/tmp/salt_logs/logs_20250611094530/
├── 2025-06-07_03.log.gz
├── 2025-06-07_04.log.gz
├── error_files.log
├── warning_files.log
```

## 📦 Requirements

Install dependencies:

```bash
pip install tqdm
```

## 🛠 Permissions

Make sure the script is executable:

```bash
chmod +x parse_salt_logs.py
```

## 🧪 Testing

You can test with a sample Salt log (`/var/log/salt/master`) or any large log file using a similar datetime format.
