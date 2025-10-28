#!/usr/bin/env python3
"""Environment and FreeIPA discovery module."""

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


class EnvironmentDiscovery:
    """Discover Environment and FreeIPA details."""
    
    def __init__(self, cdp_client, config):
        """
        Initialize environment discovery.
        
        Args:
            cdp_client: CDPClient instance
            config: DiscoveryConfig instance
        """
        self.client = cdp_client
        self.config = config
        self.exporter = CSVExporter()
    
    def discover(self):
        """
        Discover environment and FreeIPA details.
        
        Returns:
            dict: Discovery results with environment and FreeIPA details
        """
        log("🌍 Starting Environment discovery...")
        
        results = {
            'environment': None,
            'freeipa': None,
            'freeipa_upgrade_options': None,
            'success': False
        }
        
        # Get service output directory
        env_dir = self.config.get_service_dir("environment")
        
        # 1. Describe the environment
        env_json, env_err = self.client.describe_environment(self.config.environment_name)
        
        if env_json:
            env_obj = env_json.get("environment", env_json)
            results['environment'] = env_obj
            
            # Save JSON
            json_path = env_dir / f"ENV_{self.config.environment_name}_{self.config.timestamp}.json"
            save_to_file(env_json, json_path)
            
            # Save flattened CSV
            csv_path = env_dir / f"ENV_{self.config.environment_name}_{self.config.timestamp}.csv"
            self.exporter.save_flattened_json_to_csv(env_obj, csv_path)
            
            results['success'] = True
            
            # 2. Extract FreeIPA details
            freeipa_details = (
                env_obj.get("freeipa") or 
                env_obj.get("freeIpaDetails") or 
                env_obj.get("freeIpa")
            )
            
            if freeipa_details:
                results['freeipa'] = freeipa_details
                self._discover_freeipa(freeipa_details, env_dir)
            else:
                log("⚠️ No FreeIPA details found in environment")
        else:
            log(f"⚠️ Could not describe environment {self.config.environment_name}")
            if self.config.debug:
                log(f"DEBUG: env_err: {env_err}")
        
        # 3. Get FreeIPA upgrade options
        freeipa_upgrade_json, freeipa_upgrade_err = self.client.get_freeipa_upgrade_options(
            self.config.environment_name
        )
        
        if freeipa_upgrade_json:
            results['freeipa_upgrade_options'] = freeipa_upgrade_json
            upgrade_path = env_dir / f"ENV_{self.config.environment_name}_FreeIPAUpgradeOptions_{self.config.timestamp}.json"
            save_to_file(freeipa_upgrade_json, upgrade_path)
        else:
            log(f"⚠️ Could not get FreeIPA upgrade options")
            if self.config.debug:
                log(f"DEBUG: freeipa_upgrade_err: {freeipa_upgrade_err}")
        
        return results
    
    def _discover_freeipa(self, freeipa_details, env_dir):
        """
        Discover FreeIPA instance details.
        
        Args:
            freeipa_details: FreeIPA details from environment
            env_dir: Output directory path
        """
        log("🔐 Discovering FreeIPA instances...")
        
        # Flatten FreeIPA instance groups
        freeipa_ig_rows = self._flatten_freeipa_instance_groups(freeipa_details)
        
        if freeipa_ig_rows:
            csv_path = env_dir / f"ENV_{self.config.environment_name}_FreeIPAInstanceGroups_{self.config.timestamp}.csv"
            self.exporter.save_instance_groups_to_csv(csv_path, freeipa_ig_rows)
        else:
            log(f"⚠️ No FreeIPA instance groups found")
        
        # Discover FreeIPA recipes if present
        recipes = freeipa_details.get("recipes", [])
        if recipes:
            self._discover_freeipa_recipes(recipes, env_dir)
    
    def _flatten_freeipa_instance_groups(self, freeipa_obj):
        """
        Flatten FreeIPA instance groups for CSV export.
        
        Args:
            freeipa_obj: FreeIPA details object
            
        Returns:
            list: Flattened instance group rows
        """
        rows = []
        if not freeipa_obj:
            return rows
        
        instances = freeipa_obj.get("instances", [])
        recipes = ",".join(freeipa_obj.get("recipes", []))
        
        for inst in instances:
            ig_name = inst.get("instanceGroup") or "default"
            az = inst.get("availabilityZone") or ""
            subnet_id = inst.get("subnetId") or ""
            
            base = {
                "environment": self.config.environment_name,
                "freeipaInstanceGroupName": ig_name,
                "availabilityZone": az,
                "subnetId": subnet_id,
                "recipes": recipes,
                "instanceId": inst.get("instanceId"),
                "instanceStatus": inst.get("instanceStatus"),
                "instanceType": inst.get("instanceType"),
                "instanceVmType": inst.get("instanceVmType"),
                "lifeCycle": inst.get("lifeCycle"),
                "privateIP": inst.get("privateIP"),
                "publicIP": inst.get("publicIP"),
                "sshPort": inst.get("sshPort"),
                "discoveryFQDN": inst.get("discoveryFQDN"),
                "freeipaCrn": freeipa_obj.get("crn"),
                "freeipaDomain": freeipa_obj.get("domain"),
                "freeipaHostname": freeipa_obj.get("hostname"),
                "freeipaInstanceCountByGroup": freeipa_obj.get("instanceCountByGroup"),
                "freeipaMultiAz": freeipa_obj.get("multiAz"),
                "freeipaImageId": (freeipa_obj.get("imageDetails") or {}).get("imageId"),
                "freeipaImageCatalogName": (freeipa_obj.get("imageDetails") or {}).get("imageCatalogName"),
                "freeipaImageOs": (freeipa_obj.get("imageDetails") or {}).get("imageOs"),
            }
            
            volumes = inst.get("attachedVolumes", [])
            if volumes:
                for vol in volumes:
                    row = base.copy()
                    row.update({
                        "volumeCount": vol.get("count"),
                        "volumeSize": vol.get("size"),
                        "volumeType": vol.get("volumeType") if "volumeType" in vol else None
                    })
                    rows.append(row)
            else:
                base.update({
                    "volumeCount": None,
                    "volumeSize": None,
                    "volumeType": None
                })
                rows.append(base)
        
        return rows
    
    def _discover_freeipa_recipes(self, recipes, env_dir):
        """
        Discover FreeIPA recipes.
        
        Note: All recipes (FreeIPA, DataLake, DataHub) use the same CDP CLI command:
        'cdp datahub describe-recipe'
        
        Args:
            recipes: List of recipe names
            env_dir: Output directory path
        """
        if not recipes:
            return
        
        log(f"📋 Discovering {len(recipes)} FreeIPA recipe(s)...")
        
        recipe_dir = env_dir / "recipes"
        recipe_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            from ..common.utils import run_command_json, save_recipe_script
        except ImportError:
            from common.utils import run_command_json, save_recipe_script
        
        for recipe_name in recipes:
            # Note: All recipes use 'cdp datahub describe-recipe' regardless of service type
            cmd = f"cdp datahub describe-recipe --profile {self.client.profile} --recipe-name {recipe_name}"
            describe, err = run_command_json(
                cmd,
                task_name=f"Describing FreeIPA recipe {recipe_name}",
                debug=self.config.debug
            )
            
            if describe:
                json_path = recipe_dir / f"freeipa_recipe_{recipe_name}.json"
                save_to_file(describe, json_path)
                
                recipe_content = describe.get("recipe", {}).get("recipeContent")
                if recipe_content:
                    script_path = recipe_dir / f"freeipa_recipe_{recipe_name}.sh"
                    save_recipe_script(recipe_content, script_path)
            else:
                log(f"⚠️ Failed to describe FreeIPA recipe: {recipe_name}")
                if self.config.debug:
                    log(f"DEBUG: Error: {err}")

