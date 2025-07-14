# RDS Stop Timer for Cloudera Data Lake

This script stops the Amazon RDS instance associated with a Cloudera Data Lake and measures how long it takes to fully stop.

It uses the Cloudera CDP CLI to extract the RDS DB identifier and the AWS CLI to interact with RDS.

---

## 📌 Features

- Automatically resolves RDS instance from a Cloudera Data Lake CRN
- Uses AWS CLI to stop the RDS instance
- Polls until the instance reaches `stopped` state
- Logs execution details with timestamp to `/var/tmp/logs`
- Supports multi-region and multi-profile AWS environments

---

## 🛠️ Requirements

- `cdp` CLI configured and authenticated
- `aws` CLI installed and configured
- `jq` installed (used to parse JSON)
- Permission to stop the RDS instance associated with the Data Lake

---

## 🚀 Usage

```bash
./poll_stop_rds_datalake.sh --cluster-crn <datalake-crn> [--region <aws-region>] [--profile <aws-profile>]
```

### ✅ Example

```bash
./poll_stop_rds_datalake.sh --cluster-crn crn:cdp:datalake:sa-east-1:123456789012:datalake:abcd1234-5678-90ef-ghij-klmnopqrstuv
```

With a custom region and profile:

```bash
./poll_stop_rds_datalake.sh \
  --cluster-crn crn:cdp:datalake:sa-east-1:123456789012:datalake:abcd1234-5678-90ef-ghij-klmnopqrstuv \
  --region us-west-2 \
  --profile my-aws-profile
```

---

## 🗂️ Logs

Logs are saved to:

```
/var/tmp/logs/stop_rds_<timestamp>.log
```

This includes:

- CLI parameters
- Polling status messages
- Final duration to stop
