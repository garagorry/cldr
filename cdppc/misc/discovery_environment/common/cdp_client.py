#!/usr/bin/env python3
"""CDP CLI client wrapper for service discovery."""

import os
from pathlib import Path
from .utils import run_command_json, log


class CDPClient:
    """Wrapper for CDP CLI commands."""
    
    def __init__(self, profile="default", debug=False):
        """
        Initialize CDP client.
        
        Args:
            profile: CDP CLI profile name
            debug: Enable debug output
        """
        self.profile = profile
        self.debug = debug
        self._validate_credentials()
    
    def _validate_credentials(self):
        """Validate that CDP credentials are configured."""
        cred_path = os.path.expanduser("~/.cdp/credentials")
        if not os.path.exists(cred_path):
            raise FileNotFoundError(
                "CDP credentials not found at ~/.cdp/credentials. "
                "Please configure the CDP CLI first."
            )
        
        profiles = self.get_profiles()
        if self.profile not in profiles:
            raise ValueError(
                f"Profile '{self.profile}' not found in ~/.cdp/credentials. "
                f"Available profiles: {profiles}"
            )
    
    @staticmethod
    def get_profiles():
        """
        Get list of available CDP profiles.
        
        Returns:
            list: List of profile names
        """
        cred_path = os.path.expanduser("~/.cdp/credentials")
        profiles = []
        
        if not os.path.exists(cred_path):
            return profiles
        
        with open(cred_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("[") and line.endswith("]"):
                    prof = line[1:-1].strip()
                    if prof and not prof.startswith("#"):
                        profiles.append(prof)
        
        return profiles
    
    def _build_command(self, service, operation, **kwargs):
        """
        Build CDP CLI command.
        
        Args:
            service: CDP service name (e.g., 'environments', 'datahub')
            operation: Operation name (e.g., 'describe-environment')
            **kwargs: Additional command arguments
            
        Returns:
            str: Complete command string
        """
        cmd_parts = [f"cdp {service} {operation}"]
        cmd_parts.append(f"--profile {self.profile}")
        
        for key, value in kwargs.items():
            # Skip None values - don't add them to the command
            if value is None:
                continue
            
            flag = key.replace("_", "-")
            if isinstance(value, bool):
                if value:
                    cmd_parts.append(f"--{flag}")
            else:
                cmd_parts.append(f"--{flag} {value}")
        
        return " ".join(cmd_parts)
    
    def execute(self, service, operation, task_name=None, **kwargs):
        """
        Execute a CDP CLI command.
        
        Args:
            service: CDP service name
            operation: Operation name
            task_name: Optional task description for spinner
            **kwargs: Additional command arguments
            
        Returns:
            tuple: (result_json, error)
        """
        command = self._build_command(service, operation, **kwargs)
        return run_command_json(command, task_name=task_name, debug=self.debug)
    
    # Environment operations
    def describe_environment(self, environment_name):
        """Describe a CDP environment."""
        return self.execute(
            "environments",
            "describe-environment",
            task_name=f"Describing environment {environment_name}",
            environment_name=environment_name
        )
    
    def get_freeipa_upgrade_options(self, environment_name):
        """Get FreeIPA upgrade options for an environment."""
        return self.execute(
            "environments",
            "get-freeipa-upgrade-options",
            task_name=f"Getting FreeIPA upgrade options for {environment_name}",
            environment=environment_name
        )
    
    # DataLake operations
    def list_datalakes(self, environment_name):
        """List datalakes in an environment."""
        return self.execute(
            "datalake",
            "list-datalakes",
            task_name=f"Listing datalakes for {environment_name}",
            environment_name=environment_name
        )
    
    def describe_datalake(self, datalake_crn):
        """Describe a datalake."""
        return self.execute(
            "datalake",
            "describe-datalake",
            task_name=f"Describing datalake",
            datalake_name=datalake_crn
        )
    
    def describe_datalake_database_server(self, cluster_crn):
        """Describe database server for a datalake."""
        return self.execute(
            "datalake",
            "describe-database-server",
            task_name=f"Describing datalake database server",
            cluster_crn=cluster_crn
        )
    
    # DataHub operations
    def list_datahub_clusters(self, environment_name):
        """List DataHub clusters in an environment."""
        return self.execute(
            "datahub",
            "list-clusters",
            task_name=f"Listing DataHub clusters for {environment_name}",
            environment_name=environment_name
        )
    
    def describe_datahub_cluster(self, cluster_crn):
        """Describe a DataHub cluster."""
        return self.execute(
            "datahub",
            "describe-cluster",
            task_name=f"Describing DataHub cluster",
            cluster_name=cluster_crn
        )
    
    def describe_datahub_database_server(self, cluster_crn):
        """Describe database server for a DataHub cluster."""
        return self.execute(
            "datahub",
            "describe-database-server",
            task_name=f"Describing DataHub database server",
            cluster_crn=cluster_crn
        )
    
    # CDE operations
    def list_cde_services(self, environment_name=None):
        """List CDE services."""
        kwargs = {}
        if environment_name:
            kwargs['environment_name'] = environment_name
        return self.execute(
            "de",
            "list-services",
            task_name="Listing CDE services",
            **kwargs
        )
    
    def describe_cde_service(self, cluster_id):
        """Describe a CDE service."""
        return self.execute(
            "de",
            "describe-service",
            task_name=f"Describing CDE service {cluster_id}",
            cluster_id=cluster_id
        )
    
    def list_cde_virtual_clusters(self, cluster_id):
        """List virtual clusters for a CDE service."""
        return self.execute(
            "de",
            "list-vcs",
            task_name=f"Listing CDE virtual clusters for {cluster_id}",
            cluster_id=cluster_id
        )
    
    def describe_cde_virtual_cluster(self, cluster_id, vc_id):
        """Describe a CDE virtual cluster."""
        return self.execute(
            "de",
            "describe-vc",
            task_name=f"Describing CDE virtual cluster {vc_id}",
            cluster_id=cluster_id,
            vc_id=vc_id
        )
    
    def get_cde_upgrade_status(self, cluster_id):
        """Get CDE service upgrade status and version information."""
        return self.execute(
            "de",
            "get-upgrade-status",
            task_name=f"Getting upgrade status for {cluster_id}",
            cluster_id=cluster_id
        )
    
    def get_cde_kubeconfig(self, cluster_id):
        """Get Kubeconfig for the CDE service."""
        return self.execute(
            "de",
            "get-kubeconfig",
            task_name=f"Getting Kubeconfig for {cluster_id}",
            cluster_id=cluster_id
        )
    
    def get_cde_service_init_logs(self, cluster_id):
        """Retrieve CDE service initialization logs."""
        return self.execute(
            "de",
            "get-service-init-logs",
            task_name=f"Getting init logs for {cluster_id}",
            cluster_id=cluster_id
        )
    
    def list_cde_backups(self, cluster_id):
        """List CDE service backups."""
        return self.execute(
            "de",
            "list-backups",
            task_name=f"Listing backups for {cluster_id}",
            cluster_id=cluster_id
        )
    
    # CAI/ML operations
    def list_ml_workspaces(self, environment_name=None):
        """List ML workspaces."""
        kwargs = {}
        if environment_name:
            kwargs['environment_name'] = environment_name
        return self.execute(
            "ml",
            "list-workspaces",
            task_name="Listing ML workspaces",
            **kwargs
        )
    
    def describe_ml_workspace(self, environment_name, workspace_name):
        """Describe an ML workspace."""
        return self.execute(
            "ml",
            "describe-workspace",
            task_name=f"Describing ML workspace {workspace_name}",
            environment_name=environment_name,
            workspace_name=workspace_name
        )
    
    def get_latest_workspace_version(self, workspace_crn):
        """Get latest workspace version for upgrade information."""
        return self.execute(
            "ml",
            "get-latest-workspace-version",
            task_name=f"Getting latest workspace version",
            workspace_crn=workspace_crn
        )
    
    def list_workspace_backups(self, workspace_name, environment_name):
        """List backups for an ML workspace."""
        return self.execute(
            "ml",
            "list-workspace-backups",
            task_name=f"Listing workspace backups for {workspace_name}",
            workspace_name=workspace_name,
            environment_name=environment_name
        )
    
    def list_workspace_access(self, workspace_name, environment_name):
        """List access grants for an ML workspace."""
        return self.execute(
            "ml",
            "list-workspace-access",
            task_name=f"Listing workspace access for {workspace_name}",
            workspace_name=workspace_name,
            environment_name=environment_name
        )
    
    def list_ml_serving_apps(self):
        """List ML Serving Apps (Inference Service instances)."""
        return self.execute(
            "ml",
            "list-ml-serving-apps",
            task_name="Listing ML Serving Apps"
        )
    
    def describe_ml_serving_app(self, workspace_crn):
        """Describe an ML Serving App."""
        return self.execute(
            "ml",
            "describe-ml-serving-app",
            task_name=f"Describing ML Serving App",
            workspace_crn=workspace_crn
        )
    
    def list_model_registries(self):
        """List Model Registries."""
        return self.execute(
            "ml",
            "list-model-registries",
            task_name="Listing Model Registries"
        )
    
    def describe_model_registry(self, environment_name, registry_name):
        """Describe a Model Registry."""
        return self.execute(
            "ml",
            "describe-model-registry",
            task_name=f"Describing Model Registry {registry_name}",
            environment_name=environment_name,
            registry_name=registry_name
        )
    
    def get_latest_model_registry_version(self, model_registry_crn):
        """Get latest model registry version."""
        return self.execute(
            "ml",
            "get-latest-model-registry-version",
            task_name=f"Getting latest model registry version",
            model_registry_crn=model_registry_crn
        )
    
    # CDW operations
    def list_cdw_clusters(self):
        """List CDW clusters."""
        return self.execute(
            "dw",
            "list-clusters",
            task_name="Listing CDW clusters"
        )
    
    def describe_cdw_cluster(self, cluster_id):
        """Describe a CDW cluster."""
        return self.execute(
            "dw",
            "describe-cluster",
            task_name=f"Describing CDW cluster {cluster_id}",
            cluster_id=cluster_id
        )
    
    def list_cdw_dbcs(self, cluster_id):
        """List Database Catalogs in a CDW cluster."""
        return self.execute(
            "dw",
            "list-dbcs",
            task_name=f"Listing DBCs for cluster {cluster_id}",
            cluster_id=cluster_id
        )
    
    def describe_cdw_dbc(self, cluster_id, dbc_id):
        """Describe a Database Catalog."""
        return self.execute(
            "dw",
            "describe-dbc",
            task_name=f"Describing DBC {dbc_id}",
            cluster_id=cluster_id,
            dbc_id=dbc_id
        )
    
    def list_cdw_vws(self, cluster_id):
        """List Virtual Warehouses in a CDW cluster."""
        return self.execute(
            "dw",
            "list-vws",
            task_name=f"Listing VWs for cluster {cluster_id}",
            cluster_id=cluster_id
        )
    
    def describe_cdw_vw(self, cluster_id, vw_id):
        """Describe a Virtual Warehouse."""
        return self.execute(
            "dw",
            "describe-vw",
            task_name=f"Describing VW {vw_id}",
            cluster_id=cluster_id,
            vw_id=vw_id
        )
    
    def get_upgrade_dbc_versions(self, cluster_id, dbc_id):
        """Get upgrade versions for a Database Catalog."""
        return self.execute(
            "dw",
            "get-upgrade-dbc-versions",
            task_name=f"Getting upgrade versions for DBC {dbc_id}",
            cluster_id=cluster_id,
            dbc_id=dbc_id
        )
    
    def get_upgrade_vw_versions(self, cluster_id, vw_id):
        """Get upgrade versions for a Virtual Warehouse."""
        return self.execute(
            "dw",
            "get-upgrade-vw-versions",
            task_name=f"Getting upgrade versions for VW {vw_id}",
            cluster_id=cluster_id,
            vw_id=vw_id
        )
    
    def list_cdw_data_visualizations(self, cluster_id):
        """List Data Visualizations in a CDW cluster."""
        return self.execute(
            "dw",
            "list-data-visualizations",
            task_name=f"Listing Data Visualizations for cluster {cluster_id}",
            cluster_id=cluster_id
        )
    
    def describe_cdw_data_visualization(self, cluster_id, data_visualization_id):
        """Describe a Data Visualization."""
        return self.execute(
            "dw",
            "describe-data-visualization",
            task_name=f"Describing Data Visualization {data_visualization_id}",
            cluster_id=cluster_id,
            data_visualization_id=data_visualization_id
        )
    
    def list_cdw_hues(self, cluster_id):
        """List Hue instances in a CDW cluster."""
        return self.execute(
            "dw",
            "list-hues",
            task_name=f"Listing Hue instances for cluster {cluster_id}",
            cluster_id=cluster_id
        )
    
    # CDF operations
    def list_cdf_services(self, environment_crn=None):
        """List CDF (DataFlow) services."""
        kwargs = {}
        if environment_crn:
            kwargs['environment_crn'] = environment_crn
        return self.execute(
            "df",
            "list-services",
            task_name="Listing CDF services",
            **kwargs
        )
    
    def describe_cdf_service(self, service_crn):
        """Describe a CDF service."""
        return self.execute(
            "df",
            "describe-service",
            task_name=f"Describing CDF service",
            service_crn=service_crn
        )
    
    def list_cdf_deployments(self, service_crn):
        """List DataFlow deployments."""
        return self.execute(
            "df",
            "list-deployments",
            task_name=f"Listing CDF deployments",
            service_crn=service_crn
        )
    
    def describe_cdf_deployment(self, deployment_crn):
        """Describe a DataFlow deployment."""
        return self.execute(
            "df",
            "describe-deployment",
            task_name=f"Describing CDF deployment",
            deployment_crn=deployment_crn
        )
    
    def list_cdf_flow_definitions(self):
        """List flow definitions."""
        return self.execute(
            "df",
            "list-flow-definitions",
            task_name="Listing CDF flow definitions"
        )
    
    def describe_cdf_flow(self, flow_crn):
        """Describe a flow definition."""
        return self.execute(
            "df",
            "describe-flow",
            task_name=f"Describing CDF flow",
            flow_crn=flow_crn
        )
    
    def list_cdf_projects(self):
        """List DataFlow projects."""
        return self.execute(
            "df",
            "list-projects",
            task_name="Listing CDF projects"
        )
    
    def describe_cdf_project(self, project_crn):
        """Describe a DataFlow project."""
        return self.execute(
            "df",
            "describe-project",
            task_name=f"Describing CDF project",
            project_crn=project_crn
        )
    
    def list_cdf_readyflows(self):
        """List ReadyFlows (pre-built flows)."""
        return self.execute(
            "df",
            "list-readyflows",
            task_name="Listing CDF ReadyFlows"
        )
    
    def describe_cdf_readyflow(self, readyflow_crn):
        """Describe a ReadyFlow."""
        return self.execute(
            "df",
            "describe-readyflow",
            task_name=f"Describing ReadyFlow",
            readyflow_crn=readyflow_crn
        )
    
    # COD operations
    def list_cod_databases(self, environment_name):
        """List Operational Databases."""
        return self.execute(
            "opdb",
            "list-databases",
            task_name=f"Listing COD databases for {environment_name}",
            environment_name=environment_name
        )
    
    def describe_cod_database(self, database_name, environment_name):
        """Describe an Operational Database."""
        return self.execute(
            "opdb",
            "describe-database",
            task_name=f"Describing COD database {database_name}",
            database_name=database_name,
            environment_name=environment_name
        )

