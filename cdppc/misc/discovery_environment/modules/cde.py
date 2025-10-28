#!/usr/bin/env python3
"""CDE (Cloudera Data Engineering) discovery module."""

from pathlib import Path

# Handle both direct execution and module import
try:
    from ..common.utils import log, save_to_file
    from ..exporters.csv_exporter import CSVExporter
except ImportError:
    # Direct execution - use absolute imports
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from common.utils import log, save_to_file
    from exporters.csv_exporter import CSVExporter


class CDEDiscovery:
    """Discover CDE service details."""
    
    # Cloud provider availability
    SUPPORTED_CLOUDS = ['aws', 'azure', 'gcp']
    
    def __init__(self, cdp_client, config):
        """
        Initialize CDE discovery.
        
        Args:
            cdp_client: CDPClient instance
            config: DiscoveryConfig instance
        """
        self.client = cdp_client
        self.config = config
        self.exporter = CSVExporter()
    
    def discover(self):
        """
        Discover all CDE services in the environment.
        
        Returns:
            dict: Discovery results with CDE service details
        """
        log("⚙️ Starting CDE (Data Engineering) discovery...")
        
        results = {
            'services': [],
            'success': False
        }
        
        # List CDE services (filter by environment if possible)
        services_json, services_err = self.client.list_cde_services()
        
        if not services_json:
            log("ℹ️ No CDE services found or CDE not available")
            if self.config.debug:
                log(f"DEBUG: services_err: {services_err}")
            return results
        
        all_services = services_json.get("services", [])
        
        # Filter services by environment
        services = [
            s for s in all_services 
            if s.get("environmentName") == self.config.environment_name
        ]
        
        if not services:
            log(f"ℹ️ No CDE services found in environment {self.config.environment_name}")
            return results
        
        log(f"Found {len(services)} CDE service(s):")
        for s in services:
            log(f"  - {s.get('name')} (Cluster ID: {s.get('clusterId')})")
        
        # Discover each service
        for service in services:
            service_info = self._discover_single_service(service)
            if service_info:
                results['services'].append(service_info)
        
        results['success'] = True
        return results
    
    def _discover_single_service(self, service_summary):
        """
        Discover details for a single CDE service.
        
        Args:
            service_summary: Service summary object
            
        Returns:
            dict: Service details or None if failed
        """
        cluster_id = service_summary.get("clusterId")
        service_name = service_summary.get("name")
        
        if not cluster_id or not service_name:
            log(f"⚠️ Skipping CDE service with missing cluster ID or name")
            return None
        
        cde_dir = self.config.get_service_dir("cde") / service_name
        cde_dir.mkdir(parents=True, exist_ok=True)
        
        output_prefix = self.config.get_output_prefix("CDE", service_name)
        
        # Describe the CDE service
        describe, describe_err = self.client.describe_cde_service(cluster_id)
        
        if not describe:
            log(f"⚠️ Could not describe CDE service {service_name}")
            if self.config.debug:
                log(f"DEBUG: describe_err: {describe_err}")
            return None
        
        service_obj = describe.get("service", describe)
        
        # Save JSON
        json_path = cde_dir / f"{output_prefix}_{self.config.timestamp}.json"
        save_to_file(describe, json_path)
        
        # Save flattened CSV
        csv_path = cde_dir / f"{output_prefix}_{self.config.timestamp}.csv"
        self.exporter.save_flattened_json_to_csv(service_obj, csv_path)
        
        # Extract instance groups if available
        self._extract_instance_groups(service_obj, service_name, cde_dir, output_prefix)
        
        # Discover Virtual Clusters for this service
        virtual_clusters = self._discover_virtual_clusters(cluster_id, service_name, cde_dir)
        
        # Get upgrade status and version information (CRITICAL)
        upgrade_status = self._get_service_version_info(cluster_id, service_name, cde_dir, output_prefix)
        
        # Get additional service details
        self._get_service_additional_details(cluster_id, service_name, cde_dir, output_prefix)
        
        return {
            'name': service_name,
            'cluster_id': cluster_id,
            'details': service_obj,
            'virtual_clusters': virtual_clusters,
            'upgrade_status': upgrade_status
        }
    
    def _extract_instance_groups(self, service_obj, service_name, cde_dir, output_prefix):
        """Extract and save CDE instance groups."""
        # CDE may have different structure for instance groups based on cloud provider
        charts_details = service_obj.get("chartsDetails", {})
        
        if not charts_details:
            return
        
        # Try to extract instance information
        instance_info = []
        
        # Check for instance groups in various locations
        for key in ['instanceGroups', 'resources', 'chartValueOverrides']:
            if key in charts_details:
                instance_info.append({
                    'service': service_name,
                    'key': key,
                    'data': charts_details[key]
                })
        
        if instance_info:
            ig_path = cde_dir / f"{output_prefix}_InstanceInfo_{self.config.timestamp}.json"
            save_to_file(instance_info, ig_path)
            
            # Flatten for CSV
            ig_csv_path = cde_dir / f"{output_prefix}_InstanceInfo_{self.config.timestamp}.csv"
            self.exporter.save_flattened_json_to_csv(instance_info, ig_csv_path)
    
    def _discover_virtual_clusters(self, cluster_id, service_name, cde_dir):
        """
        Discover virtual clusters for a CDE service.
        
        Args:
            cluster_id: CDE service cluster ID
            service_name: CDE service name
            cde_dir: Output directory for CDE service
            
        Returns:
            list: List of virtual cluster details
        """
        log(f"🎯 Discovering virtual clusters for CDE service {service_name}...")
        
        # List virtual clusters
        vcs_json, vcs_err = self.client.list_cde_virtual_clusters(cluster_id)
        
        if not vcs_json:
            log(f"⚠️ Could not list virtual clusters for {service_name}")
            if self.config.debug:
                log(f"DEBUG: vcs_err: {vcs_err}")
            return []
        
        vcs = vcs_json.get("vcs", [])
        
        if not vcs:
            log(f"ℹ️ No virtual clusters found in CDE service {service_name}")
            return []
        
        log(f"Found {len(vcs)} virtual cluster(s) in {service_name}")
        
        # Create subdirectory for virtual clusters
        vcs_dir = cde_dir / "virtual_clusters"
        vcs_dir.mkdir(parents=True, exist_ok=True)
        
        # Save VCs list
        vcs_list_path = vcs_dir / f"virtual_clusters_list_{self.config.timestamp}.json"
        save_to_file(vcs_json, vcs_list_path)
        
        # Save VCs list as CSV
        if vcs:
            vcs_csv_path = vcs_dir / f"virtual_clusters_list_{self.config.timestamp}.csv"
            self.exporter.save_instance_groups_to_csv(vcs_csv_path, vcs)
        
        # Discover each virtual cluster in detail
        vc_details = []
        for vc in vcs:
            vc_detail = self._discover_single_virtual_cluster(cluster_id, vc, vcs_dir)
            if vc_detail:
                vc_details.append(vc_detail)
        
        return vc_details
    
    def _discover_single_virtual_cluster(self, cluster_id, vc_summary, vcs_dir):
        """
        Discover details for a single virtual cluster.
        
        Args:
            cluster_id: CDE service cluster ID
            vc_summary: Virtual cluster summary object
            vcs_dir: Output directory for virtual clusters
            
        Returns:
            dict: Virtual cluster details or None if failed
        """
        vc_id = vc_summary.get("vcId")
        vc_name = vc_summary.get("vcName")
        
        if not vc_id:
            log(f"⚠️ Skipping virtual cluster with missing VC ID")
            return None
        
        # Describe the virtual cluster
        vc_describe, vc_err = self.client.describe_cde_virtual_cluster(cluster_id, vc_id)
        
        if not vc_describe:
            log(f"⚠️ Could not describe virtual cluster {vc_name or vc_id}")
            if self.config.debug:
                log(f"DEBUG: vc_err: {vc_err}")
            return None
        
        vc_obj = vc_describe.get("vc", vc_describe)
        
        # Create subdirectory for this VC
        vc_subdir = vcs_dir / (vc_name or vc_id)
        vc_subdir.mkdir(parents=True, exist_ok=True)
        
        # Save VC detailed JSON
        vc_json_path = vc_subdir / f"vc_{vc_name}_{self.config.timestamp}.json"
        save_to_file(vc_describe, vc_json_path)
        
        # Save VC flattened CSV
        vc_csv_path = vc_subdir / f"vc_{vc_name}_{self.config.timestamp}.csv"
        self.exporter.save_flattened_json_to_csv(vc_obj, vc_csv_path)
        
        return {
            'vc_id': vc_id,
            'vc_name': vc_name,
            'details': vc_obj
        }
    
    def _get_service_version_info(self, cluster_id, service_name, cde_dir, output_prefix):
        """
        Get CDE service upgrade status and version information.
        This is CRITICAL for identifying pending upgrades.
        
        Args:
            cluster_id: CDE service cluster ID
            service_name: CDE service name
            cde_dir: Output directory for CDE service
            output_prefix: Output file prefix
            
        Returns:
            dict: Upgrade status information
        """
        log(f"📊 Getting upgrade status and version info for {service_name}...")
        
        # Get upgrade status
        upgrade_json, upgrade_err = self.client.get_cde_upgrade_status(cluster_id)
        
        if upgrade_json:
            upgrade_path = cde_dir / f"{output_prefix}_UpgradeStatus_{self.config.timestamp}.json"
            save_to_file(upgrade_json, upgrade_path)
            
            upgrade_csv_path = cde_dir / f"{output_prefix}_UpgradeStatus_{self.config.timestamp}.csv"
            self.exporter.save_flattened_json_to_csv(upgrade_json, upgrade_csv_path)
            
            # Extract version information for summary
            upgrade_obj = upgrade_json.get("upgradeStatus", upgrade_json)
            current_version = upgrade_obj.get("currentVersion")
            available_versions = upgrade_obj.get("availableVersions", [])
            
            if current_version:
                log(f"  Current CDE version: {current_version}")
            if available_versions:
                log(f"  Available upgrades: {len(available_versions)} version(s)")
            
            return {
                'current_version': current_version,
                'available_versions': available_versions,
                'upgrade_available': len(available_versions) > 0 if available_versions else False,
                'status': upgrade_obj.get("status"),
                'details': upgrade_obj
            }
        else:
            log(f"⚠️ Could not get upgrade status for {service_name}")
            if self.config.debug:
                log(f"DEBUG: upgrade_err: {upgrade_err}")
            return None
    
    def _get_service_additional_details(self, cluster_id, service_name, cde_dir, output_prefix):
        """
        Get additional CDE service details including backups and initialization info.
        
        Args:
            cluster_id: CDE service cluster ID
            service_name: CDE service name
            cde_dir: Output directory for CDE service
            output_prefix: Output file prefix
        """
        # 1. Get Kubeconfig
        try:
            kubeconfig_json, kubeconfig_err = self.client.get_cde_kubeconfig(cluster_id)
            if kubeconfig_json:
                kubeconfig_path = cde_dir / f"{output_prefix}_Kubeconfig_{self.config.timestamp}.json"
                save_to_file(kubeconfig_json, kubeconfig_path)
        except Exception as e:
            if self.config.debug:
                log(f"DEBUG: Could not get Kubeconfig: {e}")
        
        # 2. List backups
        try:
            backups_json, backups_err = self.client.list_cde_backups(cluster_id)
            if backups_json:
                backups = backups_json.get("backups", [])
                if backups:
                    log(f"Found {len(backups)} backup(s) for {service_name}")
                    backups_path = cde_dir / f"{output_prefix}_Backups_{self.config.timestamp}.json"
                    save_to_file(backups_json, backups_path)
                    backups_csv_path = cde_dir / f"{output_prefix}_Backups_{self.config.timestamp}.csv"
                    if backups:
                        self.exporter.save_instance_groups_to_csv(backups_csv_path, backups)
        except Exception as e:
            if self.config.debug:
                log(f"DEBUG: Could not list backups: {e}")
        
        # 3. Get service initialization logs
        try:
            init_logs_json, init_logs_err = self.client.get_cde_service_init_logs(cluster_id)
            if init_logs_json:
                init_logs_path = cde_dir / f"{output_prefix}_InitLogs_{self.config.timestamp}.json"
                save_to_file(init_logs_json, init_logs_path)
        except Exception as e:
            if self.config.debug:
                log(f"DEBUG: Could not get init logs: {e}")

