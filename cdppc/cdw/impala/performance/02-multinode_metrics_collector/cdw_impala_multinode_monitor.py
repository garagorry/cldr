#!/usr/bin/env python3
"""
CDW Impala Multi-Node Monitor
Collects Prometheus metrics from multiple endpoints at regular intervals
"""

import argparse
import subprocess
import sys
import os
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional
from collections import defaultdict
import signal

# Default configuration
DEFAULT_INTERVAL = 5  # seconds
DEFAULT_DURATION = 60  # seconds
DEFAULT_KUBECTL = "kubectl"
DEFAULT_NAMESPACE = "impala-1764611655-qscn"

# Colors for output
class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color

def log(message: str, color: str = Colors.GREEN):
    """Print colored log message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{timestamp}]{Colors.NC} {message}")

def error(message: str):
    """Print error message"""
    log(f"ERROR: {message}", Colors.RED)

def warning(message: str):
    """Print warning message"""
    log(f"WARNING: {message}", Colors.YELLOW)

def info(message: str):
    """Print info message"""
    log(message, Colors.BLUE)

def success(message: str):
    """Print success message"""
    log(message, Colors.GREEN)

def parse_endpoints_file(file_path: str) -> List[Tuple[str, int, str]]:
    """
    Parse the endpoints file created by port_forward_all_metrics.sh
    Format: endpoint_type,index,http://localhost:port/metrics_path
    
    Returns: List of tuples (endpoint_type, index, url)
    """
    endpoints = []
    try:
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split(',')
                if len(parts) < 3:
                    warning(f"Invalid line {line_num} in {file_path}: {line}")
                    continue
                
                endpoint_type = parts[0].strip()
                try:
                    index = int(parts[1].strip())
                except ValueError:
                    warning(f"Invalid index on line {line_num}: {parts[1]}")
                    continue
                
                url = ','.join(parts[2:]).strip()  # In case URL contains commas
                endpoints.append((endpoint_type, index, url))
        
        if not endpoints:
            error(f"No valid endpoints found in {file_path}")
            return []
        
        success(f"Parsed {len(endpoints)} endpoints from {file_path}")
        return endpoints
    
    except FileNotFoundError:
        error(f"Endpoints file not found: {file_path}")
        return []
    except Exception as e:
        error(f"Error reading endpoints file: {e}")
        return []

def fetch_metrics(url: str, timeout: int = 5) -> Optional[str]:
    """
    Fetch metrics from a given URL using curl
    Returns the metrics text or None on failure
    """
    try:
        result = subprocess.run(
            ['curl', '--silent', '--fail', '--max-time', str(timeout), url],
            capture_output=True,
            text=True,
            timeout=timeout + 1
        )
        
        if result.returncode == 0 and result.stdout:
            return result.stdout
        else:
            return None
    
    except subprocess.TimeoutExpired:
        warning(f"Timeout fetching metrics from {url}")
        return None
    except Exception as e:
        warning(f"Error fetching metrics from {url}: {e}")
        return None

def collect_metrics_for_endpoint(
    endpoint_type: str,
    index: int,
    url: str,
    output_dir: Path,
    interval: int,
    duration: int,
    stop_event: threading.Event
) -> int:
    """
    Collect metrics for a single endpoint at regular intervals
    
    Returns: Number of successful collections
    """
    # Create output file: metrics_{endpoint_type}_{index}.txt
    output_file = output_dir / f"metrics_{endpoint_type}_{index}.txt"
    
    start_time = time.time()
    collection_count = 0
    success_count = 0
    
    info(f"Starting collection for {endpoint_type}-{index} -> {output_file.name}")
    
    # Open file in append mode (for aggregation)
    try:
        with open(output_file, 'a') as f:
            # Write header with timestamp when collection starts
            f.write(f"\n{'='*80}\n")
            f.write(f"Collection started: {datetime.now().isoformat()}\n")
            f.write(f"Endpoint: {endpoint_type}-{index}\n")
            f.write(f"URL: {url}\n")
            f.write(f"Interval: {interval}s, Duration: {duration}s\n")
            f.write(f"{'='*80}\n\n")
            
            while not stop_event.is_set():
                elapsed = time.time() - start_time
                
                if elapsed >= duration:
                    break
                
                # Fetch metrics
                metrics = fetch_metrics(url)
                
                if metrics:
                    # Write timestamp and metrics
                    timestamp = datetime.now().isoformat()
                    f.write(f"# Timestamp: {timestamp}\n")
                    f.write(f"# Elapsed: {elapsed:.2f}s\n")
                    f.write(metrics)
                    f.write("\n\n")
                    f.flush()  # Ensure data is written immediately
                    success_count += 1
                else:
                    f.write(f"# Timestamp: {datetime.now().isoformat()}\n")
                    f.write(f"# Elapsed: {elapsed:.2f}s\n")
                    f.write("# ERROR: Failed to fetch metrics\n\n")
                    f.flush()
                
                collection_count += 1
                
                # Wait for next interval (or until stop event)
                if not stop_event.wait(interval):
                    # Event not set, continue
                    pass
                else:
                    # Event was set, break
                    break
            
            # Write footer
            f.write(f"\n{'='*80}\n")
            f.write(f"Collection ended: {datetime.now().isoformat()}\n")
            f.write(f"Total collections: {collection_count}, Successful: {success_count}\n")
            f.write(f"{'='*80}\n\n")
    
    except Exception as e:
        error(f"Error writing to {output_file}: {e}")
        return success_count
    
    info(f"Completed collection for {endpoint_type}-{index}: {success_count}/{collection_count} successful")
    return success_count

def main():
    parser = argparse.ArgumentParser(
        description='Monitor Prometheus metrics from multiple Impala endpoints',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor with default settings (5s interval, 60s duration)
  %(prog)s -f prometheus_endpoints_impala-1764611655-qscn.txt

  # Monitor with custom interval and duration
  %(prog)s -f prometheus_endpoints_impala-1764611655-qscn.txt -i 10 -t 300

  # Specify kubectl and namespace
  %(prog)s -f prometheus_endpoints_impala-1764611655-qscn.txt -b ~/bin/kubectl -n my-namespace
        """
    )
    
    parser.add_argument(
        '-f', '--file',
        required=True,
        help='Path to endpoints file (created by port_forward_all_metrics.sh)'
    )
    
    parser.add_argument(
        '-i', '--interval',
        type=int,
        default=DEFAULT_INTERVAL,
        help=f'Collection interval in seconds (default: {DEFAULT_INTERVAL})'
    )
    
    parser.add_argument(
        '-t', '--duration',
        type=int,
        default=DEFAULT_DURATION,
        help=f'Total collection duration in seconds (default: {DEFAULT_DURATION})'
    )
    
    parser.add_argument(
        '-b', '--kubectl',
        default=DEFAULT_KUBECTL,
        help=f'Path to kubectl binary (default: {DEFAULT_KUBECTL})'
    )
    
    parser.add_argument(
        '-k', '--kubeconfig',
        help='Path to kubeconfig file'
    )
    
    parser.add_argument(
        '-n', '--namespace',
        default=DEFAULT_NAMESPACE,
        help=f'Kubernetes namespace (default: {DEFAULT_NAMESPACE})'
    )
    
    parser.add_argument(
        '-o', '--output-dir',
        default='prometheus_metrics_collected',
        help='Output directory for collected metrics files (default: prometheus_metrics_collected)'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.interval <= 0:
        error("Interval must be greater than 0")
        sys.exit(1)
    
    if args.duration <= 0:
        error("Duration must be greater than 0")
        sys.exit(1)
    
    if args.interval > args.duration:
        warning(f"Interval ({args.interval}s) is greater than duration ({args.duration}s)")
    
    # Parse endpoints file
    endpoints = parse_endpoints_file(args.file)
    if not endpoints:
        error("No endpoints to monitor")
        sys.exit(1)
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    info(f"Output directory: {output_dir.absolute()}")
    
    # Set up signal handler for graceful shutdown
    stop_event = threading.Event()
    
    def signal_handler(signum, frame):
        info("\nReceived interrupt signal, stopping collection...")
        stop_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Display configuration
    info("=" * 80)
    info("CDW Impala Multi-Node Monitor")
    info("=" * 80)
    info(f"Endpoints file: {args.file}")
    info(f"Number of endpoints: {len(endpoints)}")
    info(f"Collection interval: {args.interval} seconds")
    info(f"Total duration: {args.duration} seconds")
    info(f"Expected collections per endpoint: ~{args.duration // args.interval}")
    info(f"Output directory: {output_dir.absolute()}")
    info("=" * 80)
    info("")
    
    # Start collection threads for each endpoint
    threads = []
    results = {}
    
    for endpoint_type, index, url in endpoints:
        thread = threading.Thread(
            target=lambda et=endpoint_type, idx=index, u=url: results.setdefault(
                (et, idx),
                collect_metrics_for_endpoint(et, idx, u, output_dir, args.interval, args.duration, stop_event)
            ),
            daemon=True
        )
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete or duration to elapse
    start_time = time.time()
    
    try:
        # Wait for duration or until interrupted
        while time.time() - start_time < args.duration:
            if stop_event.is_set():
                break
            time.sleep(1)
        
        # Set stop event to signal all threads
        stop_event.set()
        
        # Wait for all threads to finish (with timeout)
        for thread in threads:
            thread.join(timeout=5)
    
    except KeyboardInterrupt:
        info("\nInterrupted by user")
        stop_event.set()
        for thread in threads:
            thread.join(timeout=5)
    
    # Summary
    info("")
    info("=" * 80)
    info("Collection Summary")
    info("=" * 80)
    
    total_success = 0
    total_endpoints = len(endpoints)
    
    for endpoint_type, index, url in endpoints:
        key = (endpoint_type, index)
        success_count = results.get(key, 0)
        total_success += success_count
        output_file = output_dir / f"metrics_{endpoint_type}_{index}.txt"
        
        if success_count > 0:
            success(f"{endpoint_type}-{index}: {success_count} successful collections -> {output_file.name}")
        else:
            warning(f"{endpoint_type}-{index}: No successful collections")
    
    info("=" * 80)
    info(f"Total endpoints monitored: {total_endpoints}")
    info(f"Total successful collections: {total_success}")
    info(f"Metrics files saved to: {output_dir.absolute()}")
    info("=" * 80)
    
    if total_success == 0:
        error("No metrics were collected successfully")
        sys.exit(1)
    
    success("Collection completed successfully!")

if __name__ == '__main__':
    main()

