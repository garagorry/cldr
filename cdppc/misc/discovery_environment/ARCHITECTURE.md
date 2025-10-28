# Architecture

## Design Overview

The CDP Discovery Tool uses a modular architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                   Entry Point (main.py)                  │
│                 - CLI argument parsing                   │
│                 - Orchestration                          │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   ┌─────────┐    ┌──────────┐    ┌───────────┐
   │ Common  │    │ Modules  │    │ Exporters │
   │         │    │          │    │           │
   │ Config  │◄───┤ Discover │───►│ JSON/CSV  │
   │ Client  │    │ Services │    │           │
   │ Utils   │    │          │    │           │
   └─────────┘    └──────────┘    └───────────┘
        │                │                │
        └────────────────┴────────────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │   CDP CLI    │
                  │   (External) │
                  └──────────────┘
```

## Core Components

### 1. Entry Points

**discover.py**

- Main entry point for direct execution
- Handles Python path setup for imports

**main.py**

- Orchestrates discovery workflow
- Manages configuration and service discovery modules
- Generates summary reports

### 2. Common Utilities (`common/`)

**cdp_client.py**

- Wraps all CDP CLI commands
- Handles command construction and execution
- Manages CDP profiles
- Returns (result, error) tuples

**config.py**

- Configuration management
- Service filtering logic
- Output directory handling

**utils.py**

- Shared utilities (logging, spinners, archiving)
- Command execution with subprocess
- JSON parsing and error handling

### 3. Discovery Modules (`modules/`)

Each module follows the same pattern:

```python
class ServiceDiscovery:
    def __init__(self, client, config):
        """Initialize with CDP client and configuration."""

    def discover(self):
        """Main discovery method. Returns dict with results."""

    def _discover_single_resource(self, resource):
        """Discover details for individual resource."""

    def _save_results(self, data, output_dir):
        """Save results as JSON and CSV."""
```

**Modules:**

- `environment.py` - Environment + FreeIPA
- `datalake.py` - DataLake
- `datahub.py` - DataHub
- `cde.py` - Cloudera Data Engineering
- `cai.py` - Cloudera AI/ML
- `cdw.py` - Cloudera Data Warehouse
- `cdf.py` - Cloudera DataFlow
- `cod.py` - Operational Database

### 4. Exporters (`exporters/`)

**json_exporter.py**

- Saves data as formatted JSON
- Handles nested structures

**csv_exporter.py**

- Flattens nested JSON for CSV export
- Handles instance groups with dynamic fieldnames
- Creates spreadsheet-friendly output

## Data Flow

```
1. User runs discover.py
2. Main parses arguments → DiscoveryConfig
3. CDPClient initialized with profile
4. Orchestrator initializes discovery modules
5. For each enabled service:
   a. Module calls CDPClient methods
   b. CDPClient executes CDP CLI commands
   c. Module processes results
   d. Exporters save JSON + CSV
6. Create tar.gz archive
7. Print summary
```

## Key Design Patterns

### 1. Dependency Injection

Modules receive `CDPClient` and `DiscoveryConfig` via constructor:

```python
client = CDPClient(profile="default")
config = DiscoveryConfig(environment_name="my-env")
module = DatalakeDiscovery(client, config)
```

### 2. Error Handling

CDP CLI commands return tuples:

```python
result, error = client.describe_environment(name)
if not result:
    log(f"Error: {error}")
    return
```

### 3. Modular Discovery

Each service is independent and can be enabled/disabled:

```python
# Only discover CDE and CDW
--include-services cde cdw
```

### 4. Consistent Output Structure

Every service creates its own directory with standard files:

```
<service>/
  ├── <resource-name>/
  │   ├── <resource>.json      # Full API response
  │   ├── <resource>.csv       # Flattened data
  │   └── details/             # Additional details
```

## Extension Pattern

To add a new service:

### 1. Add CDP Client Method

```python
# In common/cdp_client.py
def describe_new_service(self, service_id):
    """Describe a new service."""
    return self.execute(
        "service-name",
        "describe-service",
        task_name=f"Describing service {service_id}",
        service_id=service_id
    )
```

### 2. Create Discovery Module

```python
# In modules/new_service.py
class NewServiceDiscovery:
    def __init__(self, client, config):
        self.client = client
        self.config = config
        self.exporter = CSVExporter()

    def discover(self):
        """Discover all instances of new service."""
        results = {'services': [], 'success': False}

        # List services
        services_json, err = self.client.list_new_services()
        if not services_json:
            return results

        # Process each service
        for service in services_json.get('services', []):
            service_info = self._discover_single_service(service)
            results['services'].append(service_info)

        results['success'] = True
        return results

    def _discover_single_service(self, service):
        """Discover details for a single service."""
        # Get details
        # Save to files
        # Return summary
        pass
```

### 3. Register in Orchestrator

```python
# In main.py
from modules import NewServiceDiscovery

self.discovery_modules = {
    # ... existing modules ...
    'newservice': NewServiceDiscovery(self.client, self.config)
}
```

## Configuration Management

Configuration is centralized in `DiscoveryConfig`:

```python
config = DiscoveryConfig(
    environment_name="my-env",    # Required
    profile="default",             # CDP CLI profile
    output_dir=None,               # Auto-generated if None
    include_services=[],           # Empty = all services
    exclude_services=[],           # Skip specific services
    debug=False                    # Enable debug output
)
```

## Error Resilience

The tool continues even when individual resources fail:

- Failed API calls are logged but don't stop discovery
- Missing services are skipped gracefully
- Partial results are still saved and archived

## Performance Considerations

- **Sequential Execution**: API calls are sequential to avoid rate limiting
- **Spinner Feedback**: Visual feedback for long-running operations
- **Streaming Output**: Results saved immediately after discovery
- **Time Complexity**: O(n) where n = number of resources

## Testing Approach

The tool is designed for easy testing:

1. **Mock CDPClient**: Replace with mock returning test data
2. **Test Modules**: Each module can be tested independently
3. **Integration Tests**: Run against test environment

Example:

```python
from unittest.mock import Mock
from modules import DatalakeDiscovery

mock_client = Mock()
mock_client.list_datalakes.return_value = ({"datalakes": []}, None)

config = DiscoveryConfig(environment_name="test")
discovery = DatalakeDiscovery(mock_client, config)
results = discovery.discover()

assert results['success'] == True
```

## Multi-Cloud Compatibility

The architecture is cloud-agnostic:

- Uses CDP Control Plane APIs (unified across clouds)
- Filters by environment name (works on any cloud)
- Adapts to missing services gracefully

## Security Considerations

- Uses CDP CLI credentials from `~/.cdp/credentials`
- Supports multiple profiles for different accounts
- No credentials stored in code
- Output may contain sensitive data (handle appropriately)

## Concurrency Model

Currently single-threaded for simplicity and API rate limiting.

## Logging Strategy

- **INFO**: Major milestones (starting discovery, found X resources)
- **DEBUG**: Detailed command output, API responses
- **ERROR**: Failures (logged but don't stop execution)
