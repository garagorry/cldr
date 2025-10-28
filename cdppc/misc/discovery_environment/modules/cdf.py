#!/usr/bin/env python3
"""CDF (Cloudera DataFlow) discovery module."""

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


class CDFDiscovery:
    """Discover CDF (DataFlow) service details."""
    
    # Cloud provider availability
    SUPPORTED_CLOUDS = ['aws', 'azure']
    
    def __init__(self, cdp_client, config):
        """
        Initialize CDF discovery.
        
        Args:
            cdp_client: CDPClient instance
            config: DiscoveryConfig instance
        """
        self.client = cdp_client
        self.config = config
        self.exporter = CSVExporter()
        self.environment_crn = None
    
    def discover(self, environment_crn=None):
        """
        Discover all CDF services.
        
        Args:
            environment_crn: Optional environment CRN for filtering
            
        Returns:
            dict: Discovery results with CDF service details
        """
        log("🌊 Starting CDF (DataFlow) discovery...")
        
        results = {
            'services': [],
            'success': False
        }
        
        services_json, services_err = self.client.list_cdf_services(environment_crn)
        
        if not services_json:
            log("ℹ️ No CDF services found or CDF not available")
            if services_err and "command not found" in str(services_err):
                log("⚠️  CDP CLI not found in PATH - did you activate your virtual environment?")
            elif self.config.debug:
                log(f"DEBUG: services_err: {services_err}")
            return results
        
        all_services = services_json.get("services", [])
        
        services = []
        for s in all_services:
            if s.get("name") == self.config.environment_name:
                services.append(s)
                continue
            env_crn = s.get("environmentCrn", "")
            if env_crn and self.config.environment_name in env_crn:
                services.append(s)
                continue
        
        if self.config.debug and not services:
            log(f"DEBUG: No services matched environment '{self.config.environment_name}'")
            log(f"DEBUG: Available services:")
            for s in all_services:
                log(f"  - Name: {s.get('name')}, EnvCRN: {s.get('environmentCrn', 'N/A')[:80]}...")
        
        if not services:
            log(f"ℹ️ No CDF services found in environment {self.config.environment_name}")
            return results
        
        log(f"Found {len(services)} CDF service(s):")
        for s in services:
            log(f"  - {s.get('name', s.get('crn'))}")
        
        for service in services:
            service_info = self._discover_single_service(service)
            if service_info:
                results['services'].append(service_info)
        
        flow_definitions = self._discover_flow_definitions()
        results['flow_definitions'] = flow_definitions
        
        projects = self._discover_projects()
        results['projects'] = projects
        
        readyflows = self._discover_readyflows()
        results['readyflows'] = readyflows
        
        results['success'] = True
        return results
    
    def _discover_single_service(self, service_summary):
        """
        Discover details for a single CDF service and all its resources.
        
        Args:
            service_summary: Service summary object
            
        Returns:
            dict: Service details or None if failed
        """
        service_crn = service_summary.get("crn")
        service_name = service_summary.get("name", "unknown")
        cluster_id = service_summary.get("clusterId")
        workload_version = service_summary.get("workloadVersion")
        deployment_count = service_summary.get("deploymentCount", 0)
        
        if not service_crn:
            log(f"⚠️ Skipping CDF service with missing CRN")
            return None
        
        cdf_dir = self.config.get_service_dir("cdf") / service_name
        cdf_dir.mkdir(parents=True, exist_ok=True)
        
        output_prefix = self.config.get_output_prefix("CDF", service_name)
        
        log(f"📊 CDF Service: {service_name}")
        if workload_version:
            log(f"  Workload version: {workload_version}")
        if cluster_id:
            log(f"  Cluster ID: {cluster_id}")
        log(f"  Deployment count: {deployment_count}")
        
        describe, describe_err = self.client.describe_cdf_service(service_crn)
        
        if not describe:
            log(f"⚠️ Could not describe CDF service {service_name}")
            if self.config.debug:
                log(f"DEBUG: describe_err: {describe_err}")
            return None
        
        service_obj = describe.get("service", describe)
        
        json_path = cdf_dir / f"{output_prefix}_{self.config.timestamp}.json"
        save_to_file(describe, json_path)
        
        csv_path = cdf_dir / f"{output_prefix}_{self.config.timestamp}.csv"
        self.exporter.save_flattened_json_to_csv(service_obj, csv_path)
        
        deployments = self._discover_deployments(service_crn, service_name, cdf_dir)
        
        return {
            'name': service_name,
            'crn': service_crn,
            'cluster_id': cluster_id,
            'workload_version': workload_version,
            'deployment_count': deployment_count,
            'details': service_obj,
            'deployments': deployments
        }
    
    def _discover_deployments(self, service_crn, service_name, cdf_dir):
        """
        Discover deployments for a CDF service.
        
        Args:
            service_crn: CDF service CRN
            service_name: CDF service name
            cdf_dir: Output directory for CDF service
            
        Returns:
            list: List of deployment details
        """
        log(f"🌊 Discovering deployments for {service_name}...")
        
        deployments_json, deployments_err = self.client.list_cdf_deployments(service_crn)
        
        if not deployments_json:
            log(f"⚠️ Could not list deployments for {service_name}")
            if self.config.debug:
                log(f"DEBUG: deployments_err: {deployments_err}")
            return []
        
        deployments = deployments_json.get("deployments", [])
        
        if not deployments:
            log(f"ℹ️ No deployments found in {service_name}")
            return []
        
        log(f"Found {len(deployments)} deployment(s)")
        
        deployments_dir = cdf_dir / "deployments"
        deployments_dir.mkdir(parents=True, exist_ok=True)
        
        deployments_list_path = deployments_dir / f"deployments_list_{self.config.timestamp}.json"
        save_to_file(deployments_json, deployments_list_path)
        
        if deployments:
            deployments_csv_path = deployments_dir / f"deployments_list_{self.config.timestamp}.csv"
            self.exporter.save_instance_groups_to_csv(deployments_csv_path, deployments)
        
        deployment_details = []
        for deployment in deployments:
            deployment_detail = self._discover_single_deployment(deployment, deployments_dir)
            if deployment_detail:
                deployment_details.append(deployment_detail)
        
        return deployment_details
    
    def _discover_single_deployment(self, deployment_summary, deployments_dir):
        """
        Discover details for a single CDF deployment.
        
        Args:
            deployment_summary: Deployment summary object
            deployments_dir: Output directory for deployments
            
        Returns:
            dict: Deployment details or None if failed
        """
        deployment_crn = deployment_summary.get("crn")
        deployment_name = deployment_summary.get("name", "unknown")
        
        if not deployment_crn:
            log(f"⚠️ Skipping deployment with missing CRN")
            return None
        
        deployment_describe, deployment_err = self.client.describe_cdf_deployment(deployment_crn)
        
        if not deployment_describe:
            log(f"⚠️ Could not describe deployment {deployment_name}")
            if self.config.debug:
                log(f"DEBUG: deployment_err: {deployment_err}")
            return None
        
        deployment_obj = deployment_describe.get("deployment", deployment_describe)
        
        deployment_subdir = deployments_dir / deployment_name
        deployment_subdir.mkdir(parents=True, exist_ok=True)
        
        deployment_json_path = deployment_subdir / f"deployment_{deployment_name}_{self.config.timestamp}.json"
        save_to_file(deployment_describe, deployment_json_path)
        
        deployment_csv_path = deployment_subdir / f"deployment_{deployment_name}_{self.config.timestamp}.csv"
        self.exporter.save_flattened_json_to_csv(deployment_obj, deployment_csv_path)
        
        nifi_version = deployment_obj.get("nifiVersion")
        status = deployment_obj.get("status", {}).get("state")
        if nifi_version:
            log(f"  Deployment {deployment_name} - NiFi version: {nifi_version}")
        if status:
            log(f"  Deployment {deployment_name} - Status: {status}")
        
        return {
            'crn': deployment_crn,
            'name': deployment_name,
            'details': deployment_obj
        }
    
    def _discover_flow_definitions(self):
        """
        Discover flow definitions (user-created flows).
        
        Returns:
            list: List of flow definition details
        """
        log(f"📐 Discovering Flow Definitions...")
        
        flows_json, flows_err = self.client.list_cdf_flow_definitions()
        
        if not flows_json:
            if self.config.debug:
                log(f"DEBUG: Could not list flow definitions: {flows_err}")
            return []
        
        flows = flows_json.get("flowDefinitions", [])
        
        if not flows:
            log(f"ℹ️ No flow definitions found")
            return []
        
        log(f"Found {len(flows)} flow definition(s)")
        
        cdf_main_dir = self.config.get_service_dir("cdf")
        flows_path = cdf_main_dir / f"flow_definitions_{self.config.timestamp}.json"
        save_to_file(flows_json, flows_path)
        
        if flows:
            flows_csv_path = cdf_main_dir / f"flow_definitions_{self.config.timestamp}.csv"
            self.exporter.save_instance_groups_to_csv(flows_csv_path, flows)
        
        return flows
    
    def _discover_projects(self):
        """
        Discover DataFlow projects.
        
        Returns:
            list: List of project details
        """
        log(f"📁 Discovering DataFlow Projects...")
        
        projects_json, projects_err = self.client.list_cdf_projects()
        
        if not projects_json:
            if self.config.debug:
                log(f"DEBUG: Could not list projects: {projects_err}")
            return []
        
        projects = projects_json.get("projects", [])
        
        if not projects:
            log(f"ℹ️ No projects found")
            return []
        
        log(f"Found {len(projects)} project(s)")
        
        cdf_main_dir = self.config.get_service_dir("cdf")
        projects_path = cdf_main_dir / f"projects_{self.config.timestamp}.json"
        save_to_file(projects_json, projects_path)
        
        if projects:
            projects_csv_path = cdf_main_dir / f"projects_{self.config.timestamp}.csv"
            self.exporter.save_instance_groups_to_csv(projects_csv_path, projects)
        
        return projects
    
    def _discover_readyflows(self):
        """
        Discover ReadyFlows (pre-built flows from Cloudera).
        
        Returns:
            list: List of ReadyFlow details
        """
        log(f"🎁 Discovering ReadyFlows (pre-built flows)...")
        
        readyflows_json, readyflows_err = self.client.list_cdf_readyflows()
        
        if not readyflows_json:
            if self.config.debug:
                log(f"DEBUG: Could not list ReadyFlows: {readyflows_err}")
            return []
        
        readyflows = readyflows_json.get("readyflows", [])
        
        if not readyflows:
            log(f"ℹ️ No ReadyFlows found")
            return []
        
        log(f"Found {len(readyflows)} ReadyFlow(s)")
        
        cdf_main_dir = self.config.get_service_dir("cdf")
        readyflows_path = cdf_main_dir / f"readyflows_{self.config.timestamp}.json"
        save_to_file(readyflows_json, readyflows_path)
        
        if readyflows:
            readyflows_csv_path = cdf_main_dir / f"readyflows_{self.config.timestamp}.csv"
            self.exporter.save_instance_groups_to_csv(readyflows_csv_path, readyflows)
        
        return readyflows

