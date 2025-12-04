# CDW Impala Multi-Node Metrics Collector

Collects Prometheus metrics from multiple CDW Impala endpoints simultaneously at regular intervals during normal operations, performance issues, or under pressure scenarios.

## Overview

This tool reads an endpoints file created by the port forwarding script and collects metrics from all configured Prometheus endpoints in parallel. It's designed to run during:

- **Normal operations** - To establish baseline metrics
- **Performance issues** - To capture metrics during incidents or performance degradation
- **Under pressure** - To collect metrics during load testing or stress scenarios

The collector creates timestamped metrics files that can be analyzed later by the report generator.

## Prerequisites

1. **Port Forwarding Active**: You must have the port forwarding script running from `01-prometheus_port_forwarder` before starting the metrics collection.

2. **Endpoints File**: The port forwarding script creates an endpoints file (e.g., `prometheus_endpoints_<namespace>.txt`) that this tool reads to discover all available endpoints.

3. **Python 3**: Python 3.6 or higher is required.

4. **curl**: The tool uses `curl` to fetch metrics from the endpoints.

## Quick Start

```bash
# Basic usage with default settings (5s interval, 60s duration)
python3 cdw_impala_multinode_monitor.py -f prometheus_endpoints_<namespace>.txt

# Custom collection duration for performance testing (5 minute collection with 10s intervals)
python3 cdw_impala_multinode_monitor.py -f prometheus_endpoints_<namespace>.txt -i 10 -t 300

# Specify custom output directory
python3 cdw_impala_multinode_monitor.py -f prometheus_endpoints_<namespace>.txt -o my_metrics_collection
```

## Command-Line Options

```bash
python3 cdw_impala_multinode_monitor.py [OPTIONS]
```

### Required Arguments

- `-f, --file PATH`: Path to endpoints file created by `port_forward_all_metrics.sh`
  - Format: `prometheus_endpoints_<namespace>.txt`
  - Example: `prometheus_endpoints_impala-1764611655-qscn.txt`

### Optional Arguments

- `-i, --interval SECONDS`: Collection interval in seconds (default: `5`)

  - How often to collect metrics from each endpoint
  - Lower values provide more granular data but generate larger files

- `-t, --duration SECONDS`: Total collection duration in seconds (default: `60`)

  - How long to run the collection
  - Use longer durations for performance testing scenarios

- `-o, --output-dir PATH`: Output directory for collected metrics files (default: `prometheus_metrics_collected`)

  - All metrics files will be saved in this directory
  - Directory will be created if it doesn't exist

- `-n, --namespace NAME`: Kubernetes namespace (default: `impala-1764611655-qscn`)

  - Used for reference and logging (endpoints are already configured in the file)

- `-b, --kubectl PATH`: Path to kubectl binary (default: `kubectl`)

  - Only used for reference/logging purposes

- `-k, --kubeconfig PATH`: Path to kubeconfig file
  - Only used for reference/logging purposes

## Usage Examples

### Collect Baseline Metrics (Short Duration)

Collect metrics for 2 minutes with 5-second intervals:

```bash
python3 cdw_impala_multinode_monitor.py \
  -f prometheus_endpoints_impala-1764611655-qscn.txt \
  -i 5 \
  -t 120 \
  -o baseline_metrics
```

### Collect During Performance Issue (Long Duration)

Monitor during an active performance issue for 30 minutes:

```bash
python3 cdw_impala_multinode_monitor.py \
  -f prometheus_endpoints_impala-1764611655-qscn.txt \
  -i 10 \
  -t 1800 \
  -o performance_issue_$(date +%Y%m%d_%H%M%S)
```

### Load Testing Scenario

Collect metrics during load testing with frequent sampling:

```bash
python3 cdw_impala_multinode_monitor.py \
  -f prometheus_endpoints_impala-1764611655-qscn.txt \
  -i 3 \
  -t 3600 \
  -o load_test_$(date +%Y%m%d_%H%M%S)
```

## How It Works

1. **Reads Endpoints File**: Parses the endpoints file to discover all available metrics endpoints

   - Format: `endpoint_type,index,http://localhost:port/metrics_path`
   - Example: `coordinator,0,http://localhost:25040/metrics_prometheus`

2. **Parallel Collection**: Creates a separate thread for each endpoint to collect metrics concurrently

3. **Timed Collection**: Collects metrics at the specified interval until the duration elapses

4. **File Output**: Creates one file per endpoint:

   - Format: `metrics_{endpoint_type}_{index}.txt`
   - Example: `metrics_coordinator_0.txt`, `metrics_executor_1.txt`

5. **Graceful Shutdown**: Supports Ctrl+C to stop collection gracefully, ensuring all data is saved

## Output Files

Each metrics file contains:

- **Header**: Collection metadata (start time, endpoint info, interval, duration)
- **Timestamped Metrics**: Each collection includes:
  - ISO timestamp
  - Elapsed time since start
  - Full Prometheus metrics output
- **Footer**: Summary (end time, total collections, successful collections)

### File Format Example

```
================================================================================
Collection started: 2024-01-15T14:30:00.123456
Endpoint: coordinator-0
URL: http://localhost:25040/metrics_prometheus
Interval: 5s, Duration: 60s
================================================================================

# Timestamp: 2024-01-15T14:30:00.123456
# Elapsed: 0.00s
impala_rpc_method_hs2_http_TCLIService_ExecuteStatement_call_duration{quantile="0.5"} 0.125
impala_rpc_method_hs2_http_TCLIService_ExecuteStatement_call_duration{quantile="0.95"} 0.450
...

# Timestamp: 2024-01-15T14:30:05.234567
# Elapsed: 5.11s
impala_rpc_method_hs2_http_TCLIService_ExecuteStatement_call_duration{quantile="0.5"} 0.130
...

================================================================================
Collection ended: 2024-01-15T14:31:00.345678
Total collections: 12, Successful: 12
================================================================================
```

## Monitoring Collection

The tool provides real-time feedback:

- **Colored Output**: Uses colors to indicate status (green=success, yellow=warning, red=error, blue=info)
- **Progress Updates**: Shows which endpoints are being monitored
- **Summary**: Displays collection statistics at the end

### Example Output

```
[14:30:00] CDW Impala Multi-Node Monitor
[14:30:00] ================================================================================
[14:30:00] Endpoints file: prometheus_endpoints_impala-1764611655-qscn.txt
[14:30:00] Number of endpoints: 6
[14:30:00] Collection interval: 5 seconds
[14:30:00] Total duration: 60 seconds
[14:30:00] Expected collections per endpoint: ~12
[14:30:00] Output directory: /path/to/prometheus_metrics_collected
[14:30:00] ================================================================================
[14:30:00] Starting collection for coordinator-0 -> metrics_coordinator_0.txt
[14:30:00] Starting collection for executor-0 -> metrics_executor_0.txt
...
[14:31:00] Completed collection for coordinator-0: 12/12 successful
[14:31:00] ================================================================================
[14:31:00] Collection Summary
[14:31:00] ================================================================================
[14:31:00] coordinator-0: 12 successful collections -> metrics_coordinator_0.txt
[14:31:00] Total endpoints monitored: 6
[14:31:00] Total successful collections: 72
[14:31:00] Metrics files saved to: /path/to/prometheus_metrics_collected
```

## Best Practices

1. **Ensure Port Forwarding is Active**: The port forwarding script must be running in another terminal before starting collection.

2. **Choose Appropriate Intervals**:

   - **Short intervals (3-5s)**: For detailed analysis during active issues
   - **Medium intervals (10-15s)**: For general monitoring and load testing
   - **Long intervals (30-60s)**: For baseline monitoring over long periods

3. **Collection Duration**:

   - **Baseline**: 2-5 minutes is usually sufficient
   - **Performance Issues**: 15-30 minutes to capture the full incident
   - **Load Testing**: Match the duration of your load test

4. **Organize Output Directories**: Use descriptive directory names with timestamps:

   ```bash
   -o baseline_20240115_143000
   -o performance_issue_20240115_150000
   -o load_test_20240115_160000
   ```

5. **Monitor During Issues**: Start collection as soon as you notice a performance issue, don't wait.

6. **Save for Analysis**: Keep collected metrics files for later analysis using the report generator.

## Troubleshooting

### No Endpoints Found

**Error**: `No valid endpoints found in <file>`

**Solutions**:

- Verify the endpoints file exists and was created by the port forwarding script
- Check that port forwarding is still active
- Ensure the file path is correct

### Failed to Fetch Metrics

**Warning**: `ERROR: Failed to fetch metrics`

**Solutions**:

- Verify port forwarding is still active in the other terminal
- Check if the endpoint URL is accessible: `curl http://localhost:<port>/metrics_prometheus`
- Verify the endpoint is running and healthy

### Collection Stopped Early

**Possible Causes**:

- Port forwarding stopped
- Network interruption
- Endpoint became unavailable

**Solution**: Restart port forwarding and rerun collection

### No Metrics Collected

**Error**: `No metrics were collected successfully`

**Solutions**:

- Check that port forwarding is active
- Verify endpoints are accessible with curl
- Check network connectivity
- Review error messages in the output for specific failures

## Stopping Collection

The tool supports graceful shutdown:

- **Ctrl+C**: Press Ctrl+C to stop collection gracefully
- The tool will:
  - Stop collecting new metrics
  - Wait for current collections to complete
  - Save all collected data to files
  - Display a summary

All data collected before stopping is preserved.

## Next Steps

After collecting metrics, use the report generator to analyze the data:

```bash
cd ../03-metrics_report
python3 cdw_impala_multinode_monitor_report.py -d ../02-multinode_metrics_collector/prometheus_metrics_collected
```

## Requirements

- Python 3.6+
- `curl` command-line tool
- Active port forwarding from `01-prometheus_port_forwarder`
- Endpoints file created by the port forwarding script

## Related Tools

- **Port Forwarding**: `01-prometheus_port_forwarder/port_forward_all_metrics.sh`
- **Report Generator**: `03-metrics_report/cdw_impala_multinode_monitor_report.py`

## License

This tool is provided as-is for use with CDW Impala deployments.
