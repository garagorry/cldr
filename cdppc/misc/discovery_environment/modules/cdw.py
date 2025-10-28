#!/usr/bin/env python3
"""CDW (Cloudera Data Warehouse) discovery module."""

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


class CDWDiscovery:
    """Discover CDW cluster details."""
    
    # Cloud provider availability
    SUPPORTED_CLOUDS = ['aws', 'azure']
    
    def __init__(self, cdp_client, config):
        """
        Initialize CDW discovery.
        
        Args:
            cdp_client: CDPClient instance
            config: DiscoveryConfig instance
        """
        self.client = cdp_client
        self.config = config
        self.exporter = CSVExporter()
    
    def discover(self):
        """
        Discover all CDW clusters and their resources.
        
        Returns:
            dict: Discovery results with CDW cluster details
        """
        log("🏢 Starting CDW (Data Warehouse) discovery...")
        
        results = {
            'clusters': [],
            'success': False
        }
        
        # List CDW clusters
        clusters_json, clusters_err = self.client.list_cdw_clusters()
        
        if not clusters_json:
            log("ℹ️ No CDW clusters found or CDW not available")
            if self.config.debug:
                log(f"DEBUG: clusters_err: {clusters_err}")
            return results
        
        all_clusters = clusters_json.get("clusters", [])
        
        # Filter clusters by environment CRN (match environment name in CRN)
        clusters = []
        for c in all_clusters:
            env_crn = c.get("environmentCrn", "")
            cluster_name = c.get("name", "")
            # Match by environment name in CRN or cluster name contains env name
            if (env_crn and self.config.environment_name in env_crn) or \
               (cluster_name and self.config.environment_name in cluster_name):
                clusters.append(c)
        
        if not clusters:
            log(f"ℹ️ No CDW clusters found in environment {self.config.environment_name}")
            if self.config.debug:
                log(f"DEBUG: Available clusters: {[c.get('id') + ' (' + c.get('name', 'N/A') + ')' for c in all_clusters]}")
            return results
        
        log(f"Found {len(clusters)} CDW cluster(s):")
        for c in clusters:
            log(f"  - {c.get('name')} (ID: {c.get('id')})")
        
        # Discover each cluster
        for cluster in clusters:
            cluster_info = self._discover_single_cluster(cluster)
            if cluster_info:
                results['clusters'].append(cluster_info)
        
        results['success'] = True
        return results
    
    def _discover_single_cluster(self, cluster_summary):
        """
        Discover details for a single CDW cluster and all its resources.
        
        Args:
            cluster_summary: Cluster summary object
            
        Returns:
            dict: Cluster details or None if failed
        """
        cluster_id = cluster_summary.get("id")
        cluster_name = cluster_summary.get("name", cluster_id)
        
        if not cluster_id:
            log(f"⚠️ Skipping CDW cluster with missing ID")
            return None
        
        cdw_dir = self.config.get_service_dir("cdw") / cluster_name
        cdw_dir.mkdir(parents=True, exist_ok=True)
        
        output_prefix = self.config.get_output_prefix("CDW", cluster_name)
        
        # 1. Describe the CDW cluster
        describe, describe_err = self.client.describe_cdw_cluster(cluster_id)
        
        if not describe:
            log(f"⚠️ Could not describe CDW cluster {cluster_name}")
            if self.config.debug:
                log(f"DEBUG: describe_err: {describe_err}")
            return None
        
        cluster_obj = describe.get("cluster", describe)
        
        # Save JSON
        json_path = cdw_dir / f"{output_prefix}_{self.config.timestamp}.json"
        save_to_file(describe, json_path)
        
        # Save flattened CSV
        csv_path = cdw_dir / f"{output_prefix}_{self.config.timestamp}.csv"
        self.exporter.save_flattened_json_to_csv(cluster_obj, csv_path)
        
        # 2. Discover Database Catalogs (DBCs)
        dbcs = self._discover_database_catalogs(cluster_id, cluster_name, cdw_dir)
        
        # 3. Discover Virtual Warehouses (VWs)
        vws = self._discover_virtual_warehouses(cluster_id, cluster_name, cdw_dir)
        
        # 4. Discover Data Visualizations
        data_vizs = self._discover_data_visualizations(cluster_id, cluster_name, cdw_dir)
        
        # 5. Discover Hue instances
        hues = self._discover_hue_instances(cluster_id, cluster_name, cdw_dir)
        
        return {
            'id': cluster_id,
            'name': cluster_name,
            'details': cluster_obj,
            'dbcs': dbcs,
            'virtual_warehouses': vws,
            'data_visualizations': data_vizs,
            'hues': hues
        }
    
    def _discover_database_catalogs(self, cluster_id, cluster_name, cdw_dir):
        """
        Discover Database Catalogs (DBCs) for a CDW cluster.
        
        Args:
            cluster_id: CDW cluster ID
            cluster_name: CDW cluster name
            cdw_dir: Output directory for CDW cluster
            
        Returns:
            list: List of DBC details
        """
        log(f"📚 Discovering Database Catalogs for {cluster_name}...")
        
        # List DBCs
        dbcs_json, dbcs_err = self.client.list_cdw_dbcs(cluster_id)
        
        if not dbcs_json:
            log(f"⚠️ Could not list DBCs for {cluster_name}")
            if self.config.debug:
                log(f"DEBUG: dbcs_err: {dbcs_err}")
            return []
        
        dbcs = dbcs_json.get("dbcs", [])
        
        if not dbcs:
            log(f"ℹ️ No Database Catalogs found in {cluster_name}")
            return []
        
        log(f"Found {len(dbcs)} Database Catalog(s)")
        
        # Create subdirectory for DBCs
        dbcs_dir = cdw_dir / "database_catalogs"
        dbcs_dir.mkdir(parents=True, exist_ok=True)
        
        # Save DBCs list
        dbcs_list_path = dbcs_dir / f"dbcs_list_{self.config.timestamp}.json"
        save_to_file(dbcs_json, dbcs_list_path)
        
        if dbcs:
            dbcs_csv_path = dbcs_dir / f"dbcs_list_{self.config.timestamp}.csv"
            self.exporter.save_instance_groups_to_csv(dbcs_csv_path, dbcs)
        
        # Discover each DBC in detail
        dbc_details = []
        for dbc in dbcs:
            dbc_detail = self._discover_single_dbc(cluster_id, dbc, dbcs_dir)
            if dbc_detail:
                dbc_details.append(dbc_detail)
        
        return dbc_details
    
    def _discover_single_dbc(self, cluster_id, dbc_summary, dbcs_dir):
        """Discover details for a single Database Catalog."""
        dbc_id = dbc_summary.get("id")
        dbc_name = dbc_summary.get("name", dbc_id)
        
        if not dbc_id:
            return None
        
        # Describe DBC
        dbc_describe, dbc_err = self.client.describe_cdw_dbc(cluster_id, dbc_id)
        
        if not dbc_describe:
            log(f"⚠️ Could not describe DBC {dbc_name}")
            return None
        
        dbc_obj = dbc_describe.get("dbc", dbc_describe)
        
        # Create subdirectory for this DBC
        dbc_subdir = dbcs_dir / dbc_name
        dbc_subdir.mkdir(parents=True, exist_ok=True)
        
        # Save DBC details
        dbc_json_path = dbc_subdir / f"dbc_{dbc_name}_{self.config.timestamp}.json"
        save_to_file(dbc_describe, dbc_json_path)
        
        dbc_csv_path = dbc_subdir / f"dbc_{dbc_name}_{self.config.timestamp}.csv"
        self.exporter.save_flattened_json_to_csv(dbc_obj, dbc_csv_path)
        
        # Get upgrade versions
        upgrade_json, upgrade_err = self.client.get_upgrade_dbc_versions(cluster_id, dbc_id)
        if upgrade_json:
            upgrade_path = dbc_subdir / f"dbc_{dbc_name}_UpgradeVersions_{self.config.timestamp}.json"
            save_to_file(upgrade_json, upgrade_path)
            
            # Log version info
            upgrade_versions = upgrade_json.get("upgradeVersions", {})
            current = upgrade_versions.get("currentVersion")
            latest = upgrade_versions.get("latestVersion")
            if current:
                log(f"  DBC {dbc_name} - Current version: {current}")
            if latest and latest != current:
                log(f"  DBC {dbc_name} - Upgrade available: {latest}")
        
        return {
            'id': dbc_id,
            'name': dbc_name,
            'details': dbc_obj
        }
    
    def _discover_virtual_warehouses(self, cluster_id, cluster_name, cdw_dir):
        """
        Discover Virtual Warehouses (VWs) for a CDW cluster.
        
        Args:
            cluster_id: CDW cluster ID
            cluster_name: CDW cluster name
            cdw_dir: Output directory for CDW cluster
            
        Returns:
            list: List of VW details
        """
        log(f"🏭 Discovering Virtual Warehouses for {cluster_name}...")
        
        # List VWs
        vws_json, vws_err = self.client.list_cdw_vws(cluster_id)
        
        if not vws_json:
            log(f"⚠️ Could not list VWs for {cluster_name}")
            if self.config.debug:
                log(f"DEBUG: vws_err: {vws_err}")
            return []
        
        vws = vws_json.get("vws", [])
        
        if not vws:
            log(f"ℹ️ No Virtual Warehouses found in {cluster_name}")
            return []
        
        log(f"Found {len(vws)} Virtual Warehouse(s)")
        
        # Create subdirectory for VWs
        vws_dir = cdw_dir / "virtual_warehouses"
        vws_dir.mkdir(parents=True, exist_ok=True)
        
        # Save VWs list
        vws_list_path = vws_dir / f"vws_list_{self.config.timestamp}.json"
        save_to_file(vws_json, vws_list_path)
        
        if vws:
            vws_csv_path = vws_dir / f"vws_list_{self.config.timestamp}.csv"
            self.exporter.save_instance_groups_to_csv(vws_csv_path, vws)
        
        # Discover each VW in detail
        vw_details = []
        for vw in vws:
            vw_detail = self._discover_single_vw(cluster_id, vw, vws_dir)
            if vw_detail:
                vw_details.append(vw_detail)
        
        return vw_details
    
    def _discover_single_vw(self, cluster_id, vw_summary, vws_dir):
        """Discover details for a single Virtual Warehouse."""
        vw_id = vw_summary.get("id")
        vw_name = vw_summary.get("name", vw_id)
        
        if not vw_id:
            return None
        
        # Describe VW
        vw_describe, vw_err = self.client.describe_cdw_vw(cluster_id, vw_id)
        
        if not vw_describe:
            log(f"⚠️ Could not describe VW {vw_name}")
            return None
        
        vw_obj = vw_describe.get("vw", vw_describe)
        
        # Create subdirectory for this VW
        vw_subdir = vws_dir / vw_name
        vw_subdir.mkdir(parents=True, exist_ok=True)
        
        # Save VW details
        vw_json_path = vw_subdir / f"vw_{vw_name}_{self.config.timestamp}.json"
        save_to_file(vw_describe, vw_json_path)
        
        vw_csv_path = vw_subdir / f"vw_{vw_name}_{self.config.timestamp}.csv"
        self.exporter.save_flattened_json_to_csv(vw_obj, vw_csv_path)
        
        # Get upgrade versions
        upgrade_json, upgrade_err = self.client.get_upgrade_vw_versions(cluster_id, vw_id)
        if upgrade_json:
            upgrade_path = vw_subdir / f"vw_{vw_name}_UpgradeVersions_{self.config.timestamp}.json"
            save_to_file(upgrade_json, upgrade_path)
            
            # Log version info
            upgrade_versions = upgrade_json.get("upgradeVersions", {})
            current = upgrade_versions.get("currentVersion")
            latest = upgrade_versions.get("latestVersion")
            if current:
                log(f"  VW {vw_name} - Current version: {current}")
            if latest and latest != current:
                log(f"  VW {vw_name} - Upgrade available: {latest}")
        
        return {
            'id': vw_id,
            'name': vw_name,
            'details': vw_obj
        }
    
    def _discover_data_visualizations(self, cluster_id, cluster_name, cdw_dir):
        """Discover Data Visualizations for a CDW cluster."""
        log(f"📊 Discovering Data Visualizations for {cluster_name}...")
        
        dvizs_json, dvizs_err = self.client.list_cdw_data_visualizations(cluster_id)
        
        if not dvizs_json:
            if self.config.debug:
                log(f"DEBUG: Could not list Data Visualizations: {dvizs_err}")
            return []
        
        dvizs = dvizs_json.get("dataVisualizations", [])
        
        if not dvizs:
            log(f"ℹ️ No Data Visualizations found in {cluster_name}")
            return []
        
        log(f"Found {len(dvizs)} Data Visualization(s)")
        
        # Save Data Visualizations
        dviz_path = cdw_dir / f"data_visualizations_{self.config.timestamp}.json"
        save_to_file(dvizs_json, dviz_path)
        
        if dvizs:
            dviz_csv_path = cdw_dir / f"data_visualizations_{self.config.timestamp}.csv"
            self.exporter.save_instance_groups_to_csv(dviz_csv_path, dvizs)
        
        return dvizs
    
    def _discover_hue_instances(self, cluster_id, cluster_name, cdw_dir):
        """Discover Hue instances for a CDW cluster."""
        log(f"🎨 Discovering Hue instances for {cluster_name}...")
        
        hues_json, hues_err = self.client.list_cdw_hues(cluster_id)
        
        if not hues_json:
            if self.config.debug:
                log(f"DEBUG: Could not list Hue instances: {hues_err}")
            return []
        
        hues = hues_json.get("hues", [])
        
        if not hues:
            log(f"ℹ️ No Hue instances found in {cluster_name}")
            return []
        
        log(f"Found {len(hues)} Hue instance(s)")
        
        # Save Hue instances
        hue_path = cdw_dir / f"hue_instances_{self.config.timestamp}.json"
        save_to_file(hues_json, hue_path)
        
        if hues:
            hue_csv_path = cdw_dir / f"hue_instances_{self.config.timestamp}.csv"
            self.exporter.save_instance_groups_to_csv(hue_csv_path, hues)
        
        return hues

