#!/usr/bin/env python3
"""
Main entry point for CDP Environment Discovery.

This script discovers and gathers details about all resources attached to a
Cloudera Data Platform (CDP) environment, including:
- Environment and FreeIPA (with recipes)
- DataLake (with recipes and runtime info)
- DataHub clusters (with recipes and runtime info)
- Kubernetes-based Data Services (CDE, CAI, CDW, CDF)
- VM-based Services (COD - Operational Database as specialized DataHub)

Supports AWS, Azure, and GCP cloud providers.
"""

import sys
import argparse
from pathlib import Path

# Handle both direct execution and module import
try:
    from .common import CDPClient, DiscoveryConfig, log, create_archive
    from .modules import (
        EnvironmentDiscovery,
        DatalakeDiscovery,
        DatahubDiscovery,
        CDEDiscovery,
        CAIDiscovery,
        CDWDiscovery,
        CDFDiscovery,
        CODDiscovery
    )
except ImportError:
    # Direct execution - add parent directory to path
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from common import CDPClient, DiscoveryConfig, log, create_archive
    from modules import (
        EnvironmentDiscovery,
        DatalakeDiscovery,
        DatahubDiscovery,
        CDEDiscovery,
        CAIDiscovery,
        CDWDiscovery,
        CDFDiscovery,
        CODDiscovery
    )


class EnvironmentDiscoveryOrchestrator:
    """Orchestrates the discovery of all CDP environment resources."""
    
    def __init__(self, config):
        """
        Initialize the discovery orchestrator.
        
        Args:
            config: DiscoveryConfig instance
        """
        self.config = config
        self.client = CDPClient(profile=config.profile, debug=config.debug)
        
        # Initialize all discovery modules
        self.modules = {
            'environment': EnvironmentDiscovery(self.client, self.config),
            'datalake': DatalakeDiscovery(self.client, self.config),
            'datahub': DatahubDiscovery(self.client, self.config),
            'cde': CDEDiscovery(self.client, self.config),
            'cai': CAIDiscovery(self.client, self.config),
            'cdw': CDWDiscovery(self.client, self.config),
            'cdf': CDFDiscovery(self.client, self.config),
            'cod': CODDiscovery(self.client, self.config)
        }
        
        self.results = {}
    
    def discover_all(self):
        """
        Discover all resources in the environment.
        
        Returns:
            dict: Discovery results for all services
        """
        log(f"🚀 Starting full environment discovery for: {self.config.environment_name}")
        log(f"📂 Output directory: {self.config.output_dir}")
        log(f"🔧 CDP Profile: {self.config.profile}")
        log("")
        
        # Discover each service type
        for service_name, module in self.modules.items():
            if not self.config.should_discover(service_name):
                log(f"⏭️ Skipping {service_name} (excluded from discovery)")
                continue
            
            try:
                if service_name == 'environment':
                    # Environment discovery includes FreeIPA
                    result = module.discover()
                elif service_name == 'datahub':
                    # DataHub can optionally filter to specific cluster
                    result = module.discover()
                else:
                    result = module.discover()
                
                self.results[service_name] = result
                
            except Exception as e:
                log(f"❌ Error discovering {service_name}: {e}")
                if self.config.debug:
                    import traceback
                    log(f"DEBUG: {traceback.format_exc()}")
                self.results[service_name] = {
                    'success': False,
                    'error': str(e)
                }
        
        return self.results
    
    def generate_summary(self):
        """
        Generate a summary of discovery results.
        
        Returns:
            dict: Summary of what was discovered
        """
        summary = {
            'environment': self.config.environment_name,
            'output_dir': str(self.config.output_dir),
            'services_discovered': {},
            'total_resources': 0
        }
        
        for service_name, result in self.results.items():
            if not result.get('success'):
                summary['services_discovered'][service_name] = {
                    'status': 'failed',
                    'count': 0
                }
                continue
            
            # Count resources for each service type
            count = 0
            if service_name == 'environment':
                count = 1 if result.get('environment') else 0
            elif service_name in ['datalake', 'datahub']:
                key = 'datalakes' if service_name == 'datalake' else 'datahubs'
                count = len(result.get(key, []))
            elif service_name == 'cde':
                count = len(result.get('services', []))
            elif service_name == 'cai':
                count = len(result.get('workspaces', []))
            elif service_name == 'cdw':
                count = len(result.get('clusters', []))
            elif service_name == 'cdf':
                count = len(result.get('services', []))
            elif service_name == 'cod':
                count = len(result.get('databases', []))
            
            summary['services_discovered'][service_name] = {
                'status': 'success',
                'count': count
            }
            summary['total_resources'] += count
        
        return summary
    
    def print_summary(self):
        """Print a summary of discovery results."""
        summary = self.generate_summary()
        
        log("\n" + "="*60)
        log("📊 DISCOVERY SUMMARY")
        log("="*60)
        log(f"Environment: {summary['environment']}")
        log(f"Output Directory: {summary['output_dir']}")
        log(f"Total Resources: {summary['total_resources']}")
        log("")
        log("Services:")
        
        for service, info in summary['services_discovered'].items():
            status_icon = "✅" if info['status'] == 'success' else "❌"
            log(f"  {status_icon} {service.upper()}: {info['count']} resource(s)")
        
        log("="*60)


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Discover all resources in a CDP environment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Discover all resources in an environment
  python main.py --environment-name my-env

  # Use a specific CDP profile
  python main.py --environment-name my-env --profile prod

  # Specify output directory
  python main.py --environment-name my-env --output-dir /tmp/my-discovery

  # Discover only specific services
  python main.py --environment-name my-env --include-services datalake datahub

  # Exclude specific services
  python main.py --environment-name my-env --exclude-services cod

  # Enable debug output
  python main.py --environment-name my-env --debug
        """
    )
    
    parser.add_argument(
        '--environment-name',
        required=True,
        help='Name of the CDP environment to discover'
    )
    
    parser.add_argument(
        '--output-dir',
        help='Directory to save output files (default: /tmp/discovery_env_<name>-<timestamp>)'
    )
    
    parser.add_argument(
        '--profile',
        default='default',
        help='CDP CLI profile to use (default: default)'
    )
    
    parser.add_argument(
        '--include-services',
        nargs='+',
        choices=['environment', 'freeipa', 'datalake', 'datahub', 'cde', 'cai', 'cdw', 'cdf', 'cod'],
        help='Specific services to include in discovery'
    )
    
    parser.add_argument(
        '--exclude-services',
        nargs='+',
        choices=['environment', 'freeipa', 'datalake', 'datahub', 'cde', 'cai', 'cdw', 'cdf', 'cod'],
        help='Services to exclude from discovery'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug output'
    )
    
    parser.add_argument(
        '--no-archive',
        action='store_true',
        help='Do not create tar.gz archive of results'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    try:
        args = parse_arguments()
        
        # Create configuration
        config = DiscoveryConfig(
            environment_name=args.environment_name,
            output_dir=args.output_dir,
            profile=args.profile,
            debug=args.debug,
            include_services=args.include_services,
            exclude_services=args.exclude_services
        )
        
        # Create orchestrator and run discovery
        orchestrator = EnvironmentDiscoveryOrchestrator(config)
        orchestrator.discover_all()
        
        # Print summary
        orchestrator.print_summary()
        
        # Create archive if requested
        if not args.no_archive:
            create_archive(config.output_dir)
        
        log(f"\n🏁 Discovery complete! Output saved in: {config.output_dir}")
        
        return 0
        
    except KeyboardInterrupt:
        log("\n⚠️ Discovery interrupted by user")
        return 130
    except Exception as e:
        log(f"\n❌ Error: {e}")
        if args.debug if 'args' in locals() else False:
            import traceback
            log(f"DEBUG: {traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

