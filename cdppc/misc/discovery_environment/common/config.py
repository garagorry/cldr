#!/usr/bin/env python3
"""Configuration management for CDP discovery."""

from pathlib import Path
from datetime import datetime


class DiscoveryConfig:
    """Configuration for CDP environment discovery."""
    
    def __init__(
        self,
        environment_name,
        output_dir=None,
        profile="default",
        debug=False,
        include_services=None,
        exclude_services=None
    ):
        """
        Initialize discovery configuration.
        
        Args:
            environment_name: Name of the CDP environment
            output_dir: Output directory path
            profile: CDP CLI profile name
            debug: Enable debug output
            include_services: List of specific services to include (None = all)
            exclude_services: List of services to exclude
        """
        self.environment_name = environment_name
        self.profile = profile
        self.debug = debug
        self.timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Set output directory
        if output_dir:
            output_dir = output_dir.rstrip("/")
            if not output_dir.endswith(self.timestamp):
                self.output_dir = Path(f"{output_dir}-{self.timestamp}")
            else:
                self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(f"/tmp/discovery_env_{environment_name}-{self.timestamp}")
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Define all available services
        self.all_services = {
            'environment',
            'freeipa',
            'datalake',
            'datahub',
            'cde',
            'cai',
            'cdw',
            'cdf',
            'cod'
        }
        
        # Determine which services to discover
        if include_services:
            self.services_to_discover = set(include_services) & self.all_services
        else:
            self.services_to_discover = self.all_services.copy()
        
        if exclude_services:
            self.services_to_discover -= set(exclude_services)
    
    def get_service_dir(self, service_name):
        """
        Get output directory for a specific service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Path: Directory path for the service
        """
        service_dir = self.output_dir / service_name
        service_dir.mkdir(parents=True, exist_ok=True)
        return service_dir
    
    def should_discover(self, service_name):
        """
        Check if a service should be discovered.
        
        Args:
            service_name: Name of the service
            
        Returns:
            bool: True if service should be discovered
        """
        return service_name in self.services_to_discover
    
    def get_output_prefix(self, service_type, resource_name=None):
        """
        Generate output file prefix.
        
        Args:
            service_type: Type of service (e.g., 'DH', 'DL', 'CDE')
            resource_name: Optional resource name
            
        Returns:
            str: File prefix
        """
        prefix = f"ENV_{self.environment_name}_{service_type}"
        if resource_name:
            prefix += f"_{resource_name}"
        return prefix

