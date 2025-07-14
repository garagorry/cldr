# RDS Stop Poller for Cloudera Data Lake

This lightweight script polls AWS for the status of an RDS instance associated with a Cloudera Data Lake, until it reaches the `stopped` state. It automatically resolves the RDS DB identifier using the Cloudera CDP CLI and supports AWS CLI region/profile targeting.

---

## 🔧 Features

- Extracts RDS DB identifier from a given Cloudera Data Lake CRN
- Polls AWS every 10 seconds until the instance is in `stopped` state
- Displays real-time status with timestamps
- Outputs final instance details in a readable table format
- Supports optional AWS `--region` and `--profile`

---

## 🛠️ Prerequisites

- [CDP CLI](https://docs.cloudera.com/cdp-public-cloud/cloud/cli/topics/mc-installing-cdp-client.html) configured and authenticated
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) installed and configured
- `jq` installed for JSON parsing
- AWS permissions to describe RDS instances

---

## 🚀 Usage

```bash
./poll_rds_until_stopped.sh --cluster-crn <datalake-crn> [--region <aws-region>] [--profile <aws-profile>]
```

### ✅ Example

```bash
./poll_rds_until_stopped.sh \
  --cluster-crn crn:cdp:datalake:sa-east-1:123456789012:datalake:abcd1234-efgh-5678-ijkl-90mnopqrstuv
```

With a specific AWS region and profile:

```bash
./poll_rds_until_stopped.sh \
  --cluster-crn crn:cdp:datalake:... \
  --region us-west-2 \
  --profile prod-account
```

---

## 💡 Notes

- The script **does not issue a stop command**; it assumes the RDS instance is already in the process of stopping.
- Use in conjunction with a separate flow that initiates the stop, or when validating RDS shutdown status after automated operations.
