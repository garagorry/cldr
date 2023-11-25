# DEPLOYING A CDPPC POC FOR BNP

This script will deploy an environment using the lastest version available.

## Requirements

### Python & Virtualenv

- Install virtualenv

```
sudo apt-get update
sudo apt-get install -y virtualenv unzip jq git
```

- Create the virtualenv tree

```
mkdir -p ~/cdpcli/{cdpcli-beta,cdpclienv}
```

### CDP CLI client setup

To set up the CDP client, complete the following tasks:

- [Generating an API access key](https://docs.cloudera.com/cdp-public-cloud/cloud/cli/topics/mc-cli-generating-an-api-access-key.html "Generating an API access key")
- [Installing CDP client](https://docs.cloudera.com/cdp-public-cloud/cloud/cli/topics/mc-installing-cdp-client.html "Installing CDP client")
- [Configuring CDP client](https://docs.cloudera.com/cdp-public-cloud/cloud/cli/topics/mc-configuring-cdp-client-with-the-api-access-key.html "Configuring CDP client")
- [Configuring CLI autocomplete](https://docs.cloudera.com/cdp-public-cloud/cloud/cli/topics/mc-configure-cli-autocomplete.html "Configuring CLI autocomplete")

#### Example:

- Public CDP CLI (std)

```
virtualenv ~/cdpcli/cdpclienv
source ~/cdpcli/cdpclienv/bin/activate
pip install cdpcli
pip install --upgrade cdpcli
deactivate
```

- Beta CDP CLI

```
virtualenv ~/cdpcli/cdpcli-beta
source ~/cdpcli/cdpcli-beta/bin/activate
pip3 install cdpcli-beta
pip3 install cdpcli-beta --upgrade
```

- [Configuring CLI autocomplete](https://docs.cloudera.com/cdp-public-cloud/cloud/cli/topics/mc-configure-cli-autocomplete.html "Configuring CLI autocomplete")

```
echo "complete -C $(which cdp_completer) cdp" | tee -a ~/.bash_profile
source ~/.bash_profile
```

- [Configuring CDP client](https://docs.cloudera.com/cdp-public-cloud/cloud/cli/topics/mc-configuring-cdp-client-with-the-api-access-key.html "Configuring CDP client")

  To create a new default configuration for CDP Public Cloud:

```
$ cdp configure
```

```
CDP Access Key ID [None]: 6e7eba99.....8cd455f54986
CDP Private Key [None]: tQZVC4G..../O3ATG38=
CDP Region [None]: west-1
CDP Endpoint URL (blank for public cloud) [None]:
```

_cdp_region_

The region for CDP API services. By default, the config file is found at\*\* ~/.cdp/config.

**possible values are:**

- **us-west-1 (default value)**
- eu-1
- ap-1
- usg-1

### Azure CLI

-[Install the Azure CLI on Linux](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-linux?pivots=apt "Install the Azure CLI on Linux")

```
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
az login
az account set --subscription xxxxxxxxxxxxxxxxxxxxxx
az account show | jq -r .id
```

### Update the Property file

Update the property file with the values that adjust to your requirements.
**_cdppc-az-poc-property-file.txt_**

### Azure Permissions [1]

The script will create a custom role in the Azure subscription or it will use a built-in role (contributor). These are the options available:

- **default**
  - The default role allows for the default set of operations including everything that the minimal role allows for.
- **minimal**
  - The minimal role only allows for Environment, Data Lake and Data Hub creation!
- **def1**
  - [Role definition 1](https://docs.cloudera.com/cdp-public-cloud/cloud/requirements-azure/topics/mc-azure-credential.html#pnavId2 "Role definition 1")
- **def2**
  - [Role definition 2](https://docs.cloudera.com/cdp-public-cloud/cloud/requirements-azure/topics/mc-azure-credential.html#pnavId3 "Role definition 2")
- **def3**
  - [Role definition 3](https://docs.cloudera.com/cdp-public-cloud/cloud/requirements-azure/topics/mc-azure-credential.html#pnavId4 "Role definition 3")

### Deployment Options [2]

- It can be used to create the pre-requisites on Azure for an Environment with Service Endpoints or Private Endpoints.
- It can be used to deploy a RAZ/Non-RAZ Data Lake.
- It always deploy the latyest version available.
- It can be used to deploy a default cluster template/definition for a choosen Datahub.

##### The options available are:

    - pre
    - cred
    - freeipa-no-custom-img
    - freeipa-pep-no-custom-img
    - freeipa-no-custom-img-priv
    - freeipa-pep-no-custom-img-priv
    - dl-raz-runtime
    - dl-no-raz-runtime
    - dh-runtime

**Syntax:**

```
./cdppc-az-poc-main.sh [1] [2]
```

### Datahub Deployment Considerations

When you deploy a Datahub using a default cluster template you need to match the Cluster Definition for the template choosen.

- To get the current Default Cluster Templates for the Current RunTime Version.

```bash
cdp datahub list-cluster-templates  | jq -r '.clusterTemplates[] | select( .status | contains("DEFAULT")) | "\(.clusterTemplateName)"' | grep ${RUN_TIME} | grep -v SDX | sort -k2
```

- To get the current Default Cluster Definitions for Templates using the Current RunTime Version.

```bash
cdp datahub list-cluster-definitions  | jq -r '.clusterDefinitions[].clusterDefinitionName'  | awk "/${RUN_TIME}/ && /Azure/" | sort -k2
```

**_Example:_**

_Cluster Template_

**7.2.17 - Data Engineering: Apache Spark3**

_Cluster Definition_

**7.2.17 - Data Engineering Spark3 for Azure**

## Working Example:

The following sequence creates an environment using private endpoints for Azure PostgreSQL/Storage Account, with Private IPs and a Raz enabled Data Lake:

- Pre-requisites:

```bash
./cdppc-az-poc-main.sh def2 pre
```

In this step you should select RAZ or Non-RAZ pre-requisites.

- CDP Credential

```bash
./cdppc-az-poc-main.sh def2 cred
```

- CDP Environment

```bash
./cdppc-az-poc-main.sh def2 freeipa-no-custom-img-priv
```

- CDP Data Lake

```bash
./cdppc-az-poc-main.sh def2 dl-raz-runtime
```

- CDP Data Engineering Cluster

```bash
./cdppc-az-poc-main.sh def2 dh-runtime
```

In this step you will use:

_Cluster Template_

1. 7.2.17 - COD Edge Node
2. 7.2.17 - Data Discovery and Exploration
3. 7.2.17 - Data Engineering: Apache Spark, Apache Hive, Apache Oozie
   **4) 7.2.17 - Data Engineering: Apache Spark3**
4. 7.2.17 - Data Engineering: HA: Apache Spark, Apache Hive, Apache Oozie
5. 7.2.17 - Data Engineering: HA: Apache Spark3, Apache Hive, Apache Oozie
6. 7.2.17 - Data Mart: Apache Impala, Hue
7. 7.2.17 - Edge Flow Management Light Duty
8. 7.2.17 - Flow Management Heavy Duty with Apache NiFi, Apache NiFi Registry, Schema Registry
9. 7.2.17 - Flow Management Light Duty with Apache NiFi, Apache NiFi Registry, Schema Registry
10. 7.2.17 - Real-time Data Mart: Apache Impala, Hue, Apache Kudu, Apache Spark
11. 7.2.17 - Real-time Data Mart: Apache Impala, Hue, Apache Kudu, Apache Spark3
12. 7.2.17 - Search Analytics
13. 7.2.17 - Streaming Analytics Heavy Duty with Apache Flink
14. 7.2.17 - Streaming Analytics Light Duty with Apache Flink
15. 7.2.17 - Streams Messaging Heavy Duty: Apache Kafka, Schema Registry, Streams Messaging Manager, Streams Replication Manager, Cruise Control
16. 7.2.17 - Streams Messaging High Availability: Apache Kafka, Schema Registry, Streams Messaging Manager, Streams Replication Manager, Cruise Control
17. 7.2.17 - Streams Messaging Light Duty: Apache Kafka, Schema Registry, Streams Messaging Manager, Streams Replication Manager, Cruise Control

_Cluster Definition_

1. 7.2.17 - COD Edge Node for Azure
2. 7.2.17 - Data Discovery and Exploration for Azure
3. 7.2.17 - Data Engineering HA - Spark3 for Azure
4. 7.2.17 - Data Engineering HA for Azure
   **5) 7.2.17 - Data Engineering Spark3 for Azure**
5. 7.2.17 - Data Engineering for Azure
6. 7.2.17 - Data Mart for Azure
7. 7.2.17 - Edge Flow Management Light Duty for Azure
8. 7.2.17 - Flow Management Heavy Duty for Azure
9. 7.2.17 - Flow Management Light Duty for Azure
10. 7.2.17 - Real-time Data Mart - Spark3 for Azure
11. 7.2.17 - Real-time Data Mart for Azure
12. 7.2.17 - Streaming Analytics Heavy Duty for Azure
13. 7.2.17 - Streaming Analytics Light Duty for Azure
14. 7.2.17 - Streams Messaging Heavy Duty for Azure
15. 7.2.17 - Streams Messaging High Availability for Azure
16. 7.2.17 - Streams Messaging Light Duty for Azure
