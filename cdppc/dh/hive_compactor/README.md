# Hive Compactor Configuration Recipe

This directory contains a recipe script for configuring Hive Compactor settings during cluster creation in Cloudera Manager.

## Recipe: configure_hive_compactor.sh

### Description

This recipe configures the `hive_compactor_worker_threads` parameter for the Hive service during cluster creation. It sets the worker threads to 0, which disables the Hive compactor functionality.

### Usage

#### 1. Template Variables

The script uses Cloudera recipe template variables that are automatically populated during cluster creation:

- `{{{ general.primaryGatewayInstanceDiscoveryFQDN }}}`: Cloudera Manager hostname
- `{{{ general.cmUserName }}}`: Cloudera Manager username
- `{{{ general.cmPassword }}}`: Cloudera Manager password
- `{{{ general.clusterName }}}`: Name of the cluster
- `HIVE_COMPACTOR_WORKER_THREADS`: Number of worker threads (hardcoded to 0)

#### 2. Dynamic API Version

The script automatically retrieves the Cloudera Manager API version by calling the `/api/version` endpoint, ensuring compatibility with different CM versions.

#### 3. Adding to Cluster Templates

To use this recipe in your cluster templates, add it to the `recipeNames` array in your instance groups:

```json
{
  "instanceGroups": [
    {
      "name": "master",
      "recipeNames": ["configure_hive_compactor"]
    }
  ]
}
```

#### 4. Service Discovery

The script dynamically discovers available services in the cluster and verifies that the `hive_on_tez` service exists before attempting configuration.

### API Endpoints

The script makes the following Cloudera Manager API calls:

#### 1. Get API Version

```
GET /api/version
```

#### 2. Configure Hive Compactor

```
PUT /api/${CM_API_VERSION}/clusters/${CLUSTER_NAME}/services/hive_on_tez/config
```

With the following payload:

```json
{
  "items": [
    {
      "name": "hive_compactor_worker_threads",
      "value": 0
    }
  ]
}
```

#### 3. Restart Hive Service

```
POST /api/${CM_API_VERSION}/clusters/${CLUSTER_NAME}/services/hive_on_tez/commands/restart
```

### Prerequisites

1. **Cloudera Manager**: The script requires access to a running Cloudera Manager instance
2. **Cluster**: The target cluster must exist and have the Hive service (hive_on_tez) installed
3. **Authentication**: Valid Cloudera Manager credentials
4. **Network Access**: The host running the script must have network access to Cloudera Manager

### Error Handling

The script includes comprehensive error handling:

- Validates Cloudera Manager accessibility and retrieves API version
- Checks if the cluster exists
- Dynamically discovers services and verifies the Hive service is installed
- Validates template variables are properly resolved
- Provides detailed error messages for troubleshooting
- Uses `set -euo pipefail` for strict error handling
- Automatically restarts the Hive service after configuration

### Logging

All operations are logged with timestamps to stderr, making it easy to track the execution progress and debug any issues.

### Security Considerations

- Store sensitive credentials (passwords) securely
- Consider using Cloudera Manager's credential management features
- Ensure the script runs with appropriate permissions
- Review network security settings for API access
