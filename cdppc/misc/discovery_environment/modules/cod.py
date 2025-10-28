#!/usr/bin/env python3
"""COD (Operational Database) discovery module.

Note: COD is NOT a Kubernetes-based data service. It is a specialized
DataHub cluster that uses virtual machines, optimized for operational
database workloads (HBase/Phoenix).
"""

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


class CODDiscovery:
    """Discover COD (Operational Database) details.
    
    COD databases are specialized DataHub clusters running on VMs,
    not Kubernetes-based services like CDE, CAI, CDW, or CDF.
    """
    
    # Cloud provider availability
    SUPPORTED_CLOUDS = ['aws', 'azure']
    
    def __init__(self, cdp_client, config):
        """
        Initialize COD discovery.
        
        Args:
            cdp_client: CDPClient instance
            config: DiscoveryConfig instance
        """
        self.client = cdp_client
        self.config = config
        self.exporter = CSVExporter()
    
    def discover(self):
        """
        Discover all COD databases in the environment.
        
        Returns:
            dict: Discovery results with COD database details
        """
        log("💾 Starting COD (Operational Database) discovery...")
        
        results = {
            'databases': [],
            'success': False
        }
        
        # List COD databases
        databases_json, databases_err = self.client.list_cod_databases(
            self.config.environment_name
        )
        
        if not databases_json:
            log("ℹ️ No COD databases found or COD not available")
            if self.config.debug:
                log(f"DEBUG: databases_err: {databases_err}")
            return results
        
        databases = databases_json.get("databases", [])
        
        if not databases:
            log(f"ℹ️ No COD databases found in environment {self.config.environment_name}")
            return results
        
        log(f"Found {len(databases)} COD database(s):")
        for db in databases:
            log(f"  - {db.get('databaseName')} (Internal: {db.get('internalName')})")
        
        # Collect unique recipes from all databases
        all_recipes_set = set()
        
        # Discover each database
        for database in databases:
            database_info = self._discover_single_database(database, all_recipes_set)
            if database_info:
                results['databases'].append(database_info)
        
        # Note: Recipes are now discovered per database in _discover_single_database
        # all_recipes_set is populated for tracking purposes
        
        results['success'] = True
        return results
    
    def _discover_single_database(self, database_summary, recipes_set):
        """
        Discover details for a single COD database.
        
        Args:
            database_summary: Database summary object
            recipes_set: Set to collect unique recipe names
            
        Returns:
            dict: Database details or None if failed
        """
        database_name = database_summary.get("databaseName")
        internal_name = database_summary.get("internalName")
        
        if not database_name:
            log(f"⚠️ Skipping COD database with missing name")
            return None
        
        cod_dir = self.config.get_service_dir("cod") / database_name
        cod_dir.mkdir(parents=True, exist_ok=True)
        
        output_prefix = self.config.get_output_prefix("COD", database_name)
        
        # Describe the COD database
        describe, describe_err = self.client.describe_cod_database(
            database_name,
            self.config.environment_name
        )
        
        if not describe:
            log(f"⚠️ Could not describe COD database {database_name}")
            if self.config.debug:
                log(f"DEBUG: describe_err: {describe_err}")
            return None
        
        database_obj = describe.get("databaseDetails", describe)
        
        # Save JSON
        json_path = cod_dir / f"{output_prefix}_{self.config.timestamp}.json"
        save_to_file(describe, json_path)
        
        # Save flattened CSV
        csv_path = cod_dir / f"{output_prefix}_{self.config.timestamp}.csv"
        self.exporter.save_flattened_json_to_csv(database_obj, csv_path)
        
        # Collect and describe recipes for THIS COD database
        database_recipes_set = set()
        self._collect_cod_recipes(database_obj, database_recipes_set)
        
        if database_recipes_set:
            recipe_dir = cod_dir / "recipes"
            self._describe_recipes_for_database(recipe_dir, database_recipes_set)
        
        # Also add to global set for tracking
        recipes_set.update(database_recipes_set)
        
        return {
            'database_name': database_name,
            'internal_name': internal_name,
            'details': database_obj
        }
    
    def _collect_cod_recipes(self, database_obj, recipes_set):
        """
        Collect recipe names from COD database object.
        
        Since COD is a specialized DataHub, it may have recipes attached.
        
        Args:
            database_obj: COD database details object
            recipes_set: Set to collect unique recipe names
        """
        # Check for recipes in various possible locations
        # Top-level recipes
        for recipe in database_obj.get("recipes", []):
            recipes_set.add(recipe)
        
        # Instance groups (if present)
        instance_groups = database_obj.get("instanceGroups", [])
        for ig in instance_groups:
            for recipe in ig.get("recipes", []):
                recipes_set.add(recipe)
        
        # Check under infrastructure details (varies by cloud provider)
        for config_key in ["infrastructure", "nodeGroups", "computeResources"]:
            config = database_obj.get(config_key, {})
            if isinstance(config, dict):
                for recipe in config.get("recipes", []):
                    recipes_set.add(recipe)
                # Check instance groups within config
                for ig in config.get("instanceGroups", []):
                    for recipe in ig.get("recipes", []):
                        recipes_set.add(recipe)
    
    def _describe_recipes_for_database(self, recipe_dir, recipes_set):
        """
        Describe all unique recipes for a specific COD database.
        
        Note: All recipes (FreeIPA, DataLake, DataHub, COD) use the same CDP CLI command:
        'cdp datahub describe-recipe'
        
        Args:
            recipe_dir: Directory to save recipes for this database
            recipes_set: Set of unique recipe names for this database
        """
        if not recipes_set:
            return
        
        recipe_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            from ..common.utils import run_command_json, save_recipe_script
        except ImportError:
            from common.utils import run_command_json, save_recipe_script
        
        for recipe_name in sorted(recipes_set):
            # Note: All recipes use 'cdp datahub describe-recipe' regardless of service type
            cmd = f"cdp datahub describe-recipe --profile {self.client.profile} --recipe-name {recipe_name}"
            describe, err = run_command_json(
                cmd,
                task_name=f"Describing COD recipe {recipe_name}",
                debug=self.config.debug
            )
            
            if describe:
                json_path = recipe_dir / f"recipe_{recipe_name}.json"
                save_to_file(describe, json_path)
                
                recipe_content = describe.get("recipe", {}).get("recipeContent")
                if recipe_content:
                    script_path = recipe_dir / f"recipe_{recipe_name}.sh"
                    save_recipe_script(recipe_content, script_path)
            else:
                log(f"⚠️ Failed to describe COD recipe: {recipe_name}")
                if self.config.debug:
                    log(f"DEBUG: Error: {err}")

