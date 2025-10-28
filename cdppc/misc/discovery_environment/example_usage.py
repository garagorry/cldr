#!/usr/bin/env python3
"""
Example usage of CDP Environment Discovery Tool

This script demonstrates various ways to use the discovery tool.
"""

from discovery_environment import EnvironmentDiscoveryOrchestrator
from discovery_environment.common import DiscoveryConfig, log


def example_full_discovery():
    """Example: Full discovery of all services in an environment."""
    print("\n" + "="*60)
    print("Example 1: Full Environment Discovery")
    print("="*60)
    
    config = DiscoveryConfig(
        environment_name="my-environment",
        profile="default",
        debug=False
    )
    
    orchestrator = EnvironmentDiscoveryOrchestrator(config)
    results = orchestrator.discover_all()
    orchestrator.print_summary()


def example_selective_discovery():
    """Example: Discover only specific services."""
    print("\n" + "="*60)
    print("Example 2: Selective Service Discovery")
    print("="*60)
    
    config = DiscoveryConfig(
        environment_name="my-environment",
        profile="default",
        debug=False,
        include_services=['environment', 'datalake', 'datahub']
    )
    
    orchestrator = EnvironmentDiscoveryOrchestrator(config)
    results = orchestrator.discover_all()
    orchestrator.print_summary()


def example_exclude_services():
    """Example: Discover all except specific services."""
    print("\n" + "="*60)
    print("Example 3: Exclude Specific Services")
    print("="*60)
    
    config = DiscoveryConfig(
        environment_name="my-environment",
        profile="default",
        debug=False
    )
    
    orchestrator = EnvironmentDiscoveryOrchestrator(config)
    results = orchestrator.discover_all()
    orchestrator.print_summary()


def example_with_custom_output():
    """Example: Use custom output directory."""
    print("\n" + "="*60)
    print("Example 4: Custom Output Directory")
    print("="*60)
    
    config = DiscoveryConfig(
        environment_name="my-environment",
        output_dir="/tmp/my-custom-discovery",
        profile="default",
        debug=False
    )
    
    orchestrator = EnvironmentDiscoveryOrchestrator(config)
    results = orchestrator.discover_all()
    orchestrator.print_summary()


def example_debug_mode():
    """Example: Run with debug output."""
    print("\n" + "="*60)
    print("Example 5: Debug Mode")
    print("="*60)
    
    config = DiscoveryConfig(
        environment_name="my-environment",
        profile="default",
        debug=True  # Enable debug output
    )
    
    orchestrator = EnvironmentDiscoveryOrchestrator(config)
    results = orchestrator.discover_all()
    orchestrator.print_summary()


def example_programmatic_access():
    """Example: Access discovery results programmatically."""
    print("\n" + "="*60)
    print("Example 6: Programmatic Access to Results")
    print("="*60)
    
    config = DiscoveryConfig(
        environment_name="my-environment",
        profile="default",
        debug=False
    )
    
    orchestrator = EnvironmentDiscoveryOrchestrator(config)
    results = orchestrator.discover_all()
    
    # Access specific results
    if results.get('datalake', {}).get('success'):
        datalakes = results['datalake'].get('datalakes', [])
        print(f"\nFound {len(datalakes)} datalake(s)")
        for dl in datalakes:
            print(f"  - {dl.get('name')}")
    
    if results.get('datahub', {}).get('success'):
        datahubs = results['datahub'].get('datahubs', [])
        print(f"\nFound {len(datahubs)} datahub(s)")
        for dh in datahubs:
            print(f"  - {dh.get('name')}")
    
    # Generate summary
    summary = orchestrator.generate_summary()
    print(f"\nTotal resources discovered: {summary['total_resources']}")


if __name__ == "__main__":
    # Note: Update 'my-environment' with your actual environment name
    
    log("CDP Environment Discovery - Example Usage")
    log("=" * 60)
    log("\nThese examples demonstrate different ways to use the discovery tool.")
    log("Uncomment the example you want to run and update the environment name.\n")
    
    # Uncomment one of the following to run:
    
    # example_full_discovery()
    # example_selective_discovery()
    # example_exclude_services()
    # example_with_custom_output()
    # example_debug_mode()
    # example_programmatic_access()
    
    log("\n✅ Example script completed")
    log("Update the environment_name and uncomment an example to run.")

