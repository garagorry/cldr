# CDW Impala Performance Monitoring

This directory contains tools for monitoring and analyzing CDW Impala performance metrics. The tools are designed to be used in a specific sequence to collect and analyze performance data.

## Workflow Overview

The performance monitoring process consists of **three sequential steps** that must be executed in order:

1. **Port Forwarding** - Enable access to Prometheus metrics endpoints
2. **Metrics Collection** - Collect metrics during normal operations and performance issues
3. **Report Generation** - Analyze collected data to generate performance reports

## Step 1: Enable Port Forwarding

**Directory:** `01-prometheus_port_forwarder`

Before collecting metrics, you need to enable port forwarding in a terminal to access the Prometheus metrics endpoints from your local machine.

This step creates port-forward tunnels to all Kubernetes pods with Prometheus metrics endpoints, making them accessible locally.

### Quick Start

```bash
cd 01-prometheus_port_forwarder
./port_forward_all_metrics.sh -n <namespace>
```

**Important:** Keep this terminal session running while collecting metrics. The port-forward connections must remain active for the metrics collector to function.

See the [01-prometheus_port_forwarder/README.md](01-prometheus_port_forwarder/README.md) for detailed documentation.

## Step 2: Metrics Collection

**Directory:** `02-multinode_metrics_collector`

Once port forwarding is active, execute the metrics collector during:

- **Normal operations** - To establish baseline metrics
- **Performance issues** - To capture metrics during incidents or performance degradation
- **Under pressure** - To collect metrics during load testing or stress scenarios

The collector will gather Prometheus metrics from all configured endpoints at regular intervals and save them to files for later analysis.

### Quick Start

```bash
cd 02-multinode_metrics_collector
python3 cdw_impala_multinode_monitor.py -f ../01-prometheus_port_forwarder/prometheus_endpoints_<namespace>.txt [options]
```

The collector creates timestamped output files that can be analyzed later (report generator coming soon).

See the [02-multinode_metrics_collector/README.md](02-multinode_metrics_collector/README.md) for detailed documentation.

## Step 3: Report Generation

**Directory:** `03-metrics_report` (Work in Progress)

With the files created by the metrics collector, you will be able to run the report generator to analyze the collected data and identify performance bottlenecks, issues, and trends.

**Note:** The report generator is currently under development and will be available in a future update.

## Execution Order Summary

```
┌─────────────────────────────────────┐
│  Step 1: Port Forwarding            │
│  (Run in terminal - keep running)   │
│  → 01-prometheus_port_forwarder     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 2: Metrics Collection         │
│  (Run during normal/issue scenarios)│
│  → 02-multinode_metrics_collector   │
│  → Creates timestamped data files   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 3: Report Generation          │
│  (Analyze collected files)          │
│  → 03-metrics_report                │
│  → Work in progress                 │
└─────────────────────────────────────┘
```

## Important Notes

1. **Sequential Execution**: These steps must be executed in order. Do not skip steps or change the sequence.

2. **Port Forwarding Persistence**: Step 1 (port forwarding) must remain active throughout Step 2 (metrics collection). If the port forwarding stops, the metrics collector will not be able to access the endpoints.

3. **Data Collection Timing**: Step 2 should be run during the scenarios you want to analyze - normal operations, performance issues, or under pressure.

4. **Report Generation**: Step 3 is currently under development and will be available in a future update.

## Directory Structure

```
performance/
├── README.md                              # This file
├── 01-prometheus_port_forwarder/          # Port forwarding tool
│   ├── README.md
│   ├── PORT_FORWARD_METRICS.md
│   └── port_forward_all_metrics.sh
├── 02-multinode_metrics_collector/        # Metrics collection tool
│   ├── README.md
│   └── cdw_impala_multinode_monitor.py
└── 03-metrics_report/                     # Report generator (Work in Progress)
    └── (Coming soon)
```

## Getting Help

For detailed information about each tool, refer to the README files in each subdirectory:

- [01-prometheus_port_forwarder/README.md](01-prometheus_port_forwarder/README.md) - Port forwarding setup and configuration
- [02-multinode_metrics_collector/README.md](02-multinode_metrics_collector/README.md) - Metrics collection usage and examples
