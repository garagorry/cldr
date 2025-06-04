### 📄 `README.md`

````markdown
# assign_shared_user.py

A command-line tool to assign the `SharedResourceUser` role to a CDP user, group, or machine user for a specific credential in the Cloudera Data Platform (CDP).

## ✅ Features

- Validates if CDP CLI is installed
- Retrieves the credential CRN based on a given name
- Finds the correct role CRN for `SharedResourceUser`
- Looks up users, groups, or machine users in CDP
- Assigns the role to the desired entity
- Displays real-time progress and informative logs

## 🛠 Prerequisites

- Python 3.6+
- [CDP CLI](https://docs.cloudera.com/cdp/latest/cli/topics/mc-installing-cdp-cli.html) installed and configured
- `jq` installed if you're using CLI tests
- `tqdm` Python package for progress bar

Install `tqdm` via pip if not installed:

```bash
pip install tqdm
````

## 🚀 Usage

```bash
python assign_shared_user.py \
  --credential-name <CREDENTIAL_NAME> \
  --assignee-type <user|group|machine-user> \
  --assignee-name <ASSIGNEE_NAME>
```

### 🔧 Example

```bash
python assign_shared_user.py \
  --credential-name jdga-csa-cred \
  --assignee-type user \
  --assignee-name sid-service-user
```

## 📦 Output

You’ll see logs like:

```
2025-06-04 13:10:22 - INFO - ✅ CDP CLI is available.
2025-06-04 13:10:22 - INFO - 🔍 Fetching CRN for credential: jdga-csa-cred
...
2025-06-04 13:10:23 - INFO - ✅ Role assignment successful.
```

## 📁 Files

* `assign_shared_user.py` – The main script
* `README.md` – This file

## 📄 License

MIT License – do what you want but be cool 😎

````
