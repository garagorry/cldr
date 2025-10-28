# CDP Discovery Tool - API Reference

This document details the CDP CLI commands used by each discovery module.

## Environment & FreeIPA

### Commands

```bash
cdp environments describe-environment --environment-name <name>
cdp environments get-freeipa-upgrade-options --environment <name>
```

### Discovered Data

- Environment metadata and configuration
- FreeIPA instances
- Network configuration
- Security settings
- Upgrade options and available versions

## DataLake

### Commands

```bash
cdp datalake list-datalakes --environment-name <name>
cdp datalake describe-datalake --datalake-name <name>
cdp datalake describe-database-server --cluster-crn <crn>
cdp datalake get-cluster-service-status --datalake-name <name>
cdp datalake get-runtime-versions --datalake-name <name>
cdp datahub describe-recipe --recipe-name <name>
```

### Discovered Data

- Datalake configuration and status
- Instance groups with detailed compute specs
- Runtime version (current and upgrade candidates)
- Database server configuration
- Service status
- Custom recipes per instance group

## DataHub

### Commands

```bash
cdp datahub list-clusters --environment-name <name>
cdp datahub describe-cluster --cluster-name <name>
cdp datahub list-cluster-templates
cdp datahub describe-cluster-template --cluster-template-name <name>
cdp datahub describe-recipe --recipe-name <name>
cdp datahub get-cluster-service-status --cluster-name <name>
cdp datahub list-cluster-lifecycle-events --cluster-name <name>
```

### Discovered Data

- Cluster configuration and status
- Instance groups per cluster
- Runtime versions (current and upgrade candidates)
- Cluster templates
- Custom recipes per cluster
- Service status
- Lifecycle events

## CDE (Cloudera Data Engineering)

### Commands

```bash
cdp de list-services --profile <profile>
cdp de describe-service --cluster-id <id>
cdp de list-vcs --cluster-id <id>
cdp de describe-vc --cluster-id <id> --vc-id <vc-id>
cdp de get-kubeconfig --cluster-id <id> --access-key <key>
cdp de list-vc-backup --cluster-id <id>
cdp de get-service-init-logs --cluster-id <id>
```

### Discovered Data

- Service configuration
- Service version and upgrade status
- Virtual clusters (VCs)
- VC configurations and resource quotas
- Kubeconfig for kubectl access
- Backup information
- Service initialization logs

## CAI (Cloudera AI/ML)

### Commands

```bash
cdp ml list-workspaces --profile <profile>
cdp ml describe-workspace --workspace-crn <crn>
cdp ml get-latest-workspace-version --workspace-crn <crn>
cdp ml list-workspace-backups --workspace-crn <crn>
cdp ml get-workspace-access --workspace-crn <crn>
cdp ml list-ml-serving-apps --cluster-id <id>
cdp ml describe-ml-serving-app --cluster-id <id> --app-crn <crn>
cdp ml list-model-registries --workspace-crn <crn>
```

### Discovered Data

- Workspace configuration
- Network settings (subnets, LB subnets, authorized IPs)
- Quota information
- Workspace version (current and upgradeable)
- Health information
- Backups
- Access control (users and groups)
- ML Serving applications
- Model registries

## CDW (Cloudera Data Warehouse)

### Commands

```bash
cdp dw list-clusters --profile <profile>
cdp dw describe-cluster --cluster-id <id>
cdp dw list-dbcs --cluster-id <id>
cdp dw describe-dbc --cluster-id <id> --dbc-id <dbc-id>
cdp dw list-vws --cluster-id <id>
cdp dw describe-vw --cluster-id <id> --vw-id <vw-id>
cdp dw get-upgrade-dbc-versions --cluster-id <id> --dbc-id <dbc-id>
cdp dw get-upgrade-vw-versions --cluster-id <id> --vw-id <vw-id>
cdp dw list-data-visualizations --cluster-id <id>
cdp dw list-hues --cluster-id <id>
```

### Discovered Data

- Cluster configuration
- Database Catalogs (DBCs) with current and upgrade versions
- Virtual Warehouses (VWs) with current and upgrade versions
- Data Visualization instances
- Hue instances
- Compute resources and configurations

## CDF (Cloudera DataFlow)

### Commands

```bash
cdp df list-services --profile <profile>
cdp df describe-service --service-crn <crn>
cdp df list-deployments --service-crn <crn>
cdp df describe-deployment --deployment-crn <crn>
cdp df list-flow-definitions --service-crn <crn>
cdp df describe-flow --flow-crn <crn>
cdp df list-projects --service-crn <crn>
cdp df describe-project --project-crn <crn>
cdp df list-readyflows
cdp df describe-readyflow --readyflow-crn <crn>
```

### Discovered Data

- Service configuration
- Workload version
- Deployment count
- Active deployments with NiFi versions
- Flow definitions
- Projects
- ReadyFlows (pre-built templates)

## COD (Operational Database)

### Commands

```bash
cdp opdb list-databases --environment-name <name>
cdp opdb describe-database --environment-name <env> --database-name <name>
cdp datahub describe-recipe --recipe-name <name>
```

### Discovered Data

- Database configuration
- Instance details
- Storage configuration
- Custom recipes per database

## Recipe Management

All recipes use the unified command regardless of service type:

```bash
cdp datahub describe-recipe --recipe-name <name>
```

### Recipe Storage

Recipes are stored in the respective service's output folder:

- **FreeIPA recipes** → `environment/recipes/`
- **DataLake recipes** → `datalake/<datalake-name>/recipes/`
- **DataHub recipes** → `datahub/<cluster-name>/recipes/`
- **COD recipes** → `cod/<database-name>/recipes/`

Each recipe is saved as:

- `<recipe-name>.json` - Full recipe metadata
- `<recipe-name>_<type>.sh` - Recipe script (pre/post-install, pre-termination)

## Version Tracking

The tool tracks versions and upgrade candidates for:

- **DataLake**: Current runtime and available upgrades
- **DataHub**: Current runtime and available upgrades
- **CDE**: Service version and upgrade status
- **CAI**: Workspace version and latest available
- **CDW DBCs**: Current version and upgrade candidates
- **CDW VWs**: Current version and upgrade candidates
- **CDF Deployments**: NiFi version per deployment

## Implementation Notes

### Error Handling

All CDP CLI commands handle errors gracefully:

- Returns `(None, error_message)` on failure
- Continues discovery even if individual resources fail
- Logs errors in debug mode

### Filtering

Services are filtered by environment using:

- Environment name matching
- Environment CRN matching
- Both strategies ensure correct resource association

### Output Formats

- **JSON**: Complete raw API responses
- **CSV**: Flattened data for spreadsheet analysis
- **Shell Scripts**: Extracted recipes as executable scripts

### Spinner UX

Long-running commands show a spinner with task description for better user experience.

## CDP CLI Profiles

All commands support CDP CLI profiles via `--profile <name>` flag:

```bash
# Default profile
python3 discover.py --environment-name my-env

# Specific profile
python3 discover.py --environment-name my-env --profile production
```

## Multi-Cloud Support

The tool works across AWS, Azure, and GCP. Some services have limited availability:

| Service     | AWS | Azure | GCP     |
| ----------- | --- | ----- | ------- |
| Environment | ✅  | ✅    | ✅      |
| DataLake    | ✅  | ✅    | ✅      |
| DataHub     | ✅  | ✅    | ✅      |
| CDE         | ✅  | ✅    | ✅      |
| CAI         | ✅  | ✅    | Limited |
| CDW         | ✅  | ✅    | Limited |
| CDF         | ✅  | ✅    | Limited |
| COD         | ✅  | ✅    | Limited |

## Extending the Tool

To add discovery for a new resource:

1. Add method to `cdp_client.py`:

```python
def describe_new_resource(self, resource_id):
    return self.execute("service", "describe-resource", resource_id=resource_id)
```

2. Add discovery logic to appropriate module
3. Export as JSON and CSV
4. Update this reference

## API Rate Limiting

The tool makes sequential API calls to avoid rate limiting. For large environments:

- Expect 5-10 seconds per DataHub cluster
- Expect 3-5 seconds per CDE/CDW/CAI resource
- Total time scales linearly with resource count
