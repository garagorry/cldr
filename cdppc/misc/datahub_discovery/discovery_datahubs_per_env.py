#!/usr/bin/env python3

import subprocess
import sys
import json
import threading
import itertools
import time
import csv
import shutil
from datetime import datetime
from pathlib import Path
import os
import re
from collections.abc import MutableMapping

def log(message):
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def usage():
    print("Usage: python discovery_datahubs_per_env.py --environment-name <environment-name> [--output-dir <path>] [--profile <cdp-profile>] [--debug]")
    print("       python discovery_datahubs_per_env.py --help")
    print("       python discovery_datahubs_per_env.py -h")
    print("\nArguments:")
    print("  --environment-name <environment-name>  Name of the CDP environment to discover DataHub clusters in. (required)")
    print("  --output-dir <path>        Directory to save output files (default: /tmp/discovery_datahubs-<timestamp>)")
    print("  --profile <cdp-profile>    CDP CLI profile to use (default: 'default')")
    print("  --debug                    Enable debug output")
    print("  --help, -h                 Show this help message and exit")
    sys.exit(1)

def get_cdp_profiles():
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

def spinner_thread_func(stop_event, message):
    for symbol in itertools.cycle("|/-\\"):
        if stop_event.is_set():
            break
        print(f"\r [{symbol}] {message}", end="", flush=True)
        time.sleep(0.1)
    print("\r", end="")

def run_command(command, task_name=None, debug=False):
    stop_spinner = threading.Event()
    if task_name:
        spinner = threading.Thread(target=spinner_thread_func, args=(stop_spinner, task_name))
        spinner.start()
    try:
        if debug:
            log(f"DEBUG: Running command: {command}")
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        if task_name:
            stop_spinner.set()
            spinner.join()
        if debug:
            log(f"DEBUG: Return code: {result.returncode}")
            log(f"DEBUG: STDOUT: {result.stdout.strip()}")
            log(f"DEBUG: STDERR: {result.stderr.strip()}")
        if result.returncode != 0:
            return None, result.stderr.strip()
        return result.stdout.strip(), None
    except Exception as e:
        if task_name:
            stop_spinner.set()
            spinner.join()
        if debug:
            log(f"DEBUG: Exception: {e}")
        return None, str(e)

def run_command_json(command, task_name=None, debug=False):
    output, error = run_command(command, task_name, debug=debug)
    if output:
        try:
            return json.loads(output), None
        except json.JSONDecodeError:
            if debug:
                log(f"DEBUG: Failed to parse JSON. Output was: {output}")
            return None, "Failed to parse JSON response."
    return None, error

def save_to_file(data, filepath):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, indent=2)
    log(f"✅ Saved: {filepath}")

def save_recipe_script(content, filepath):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        f.write(content)
    if shutil.which("shfmt"):
        subprocess.run(["shfmt", "-w", filepath], check=False)
        log(f"✅ Saved (formatted): {filepath}")
    else:
        log("⚠️ 'shfmt' not found, skipping shell formatting.")

def get_timestamp():
    return datetime.now().strftime("%Y%m%d%H%M%S")

def flatten_instance_groups(cluster_name, environment_name, instance_groups, timestamp):
    rows = []
    for ig in instance_groups:
        ig_name = ig.get("name")
        azs = ",".join(ig.get("availabilityZones", []))
        subnets = ",".join(ig.get("subnetIds", []))
        recipes = ",".join(ig.get("recipes", []))
        for inst in ig.get("instances", []):
            base = {
                "environment": environment_name,
                "clusterName": cluster_name,
                "instanceGroupName": ig_name,
                "availabilityZones": azs,
                "subnetIds": subnets,
                "recipes": recipes,
                "nodeGroupRole": inst.get("instanceGroup"),
                "instanceId": inst.get("id"),
                "state": inst.get("state"),
                "instanceType": inst.get("instanceType"),
                "privateIp": inst.get("privateIp"),
                "publicIp": inst.get("publicIp"),
                "fqdn": inst.get("fqdn"),
                "status": inst.get("status"),
                "statusReason": inst.get("statusReason"),
                "sshPort": inst.get("sshPort"),
                "clouderaManagerServer": inst.get("clouderaManagerServer"),
                "availabilityZone": inst.get("availabilityZone"),
                "instanceVmType": inst.get("instanceVmType"),
                "rackId": inst.get("rackId"),
                "subnetId": inst.get("subnetId")
            }
            volumes = inst.get("attachedVolumes", [])
            if volumes:
                for vol in volumes:
                    row = base.copy()
                    row.update({
                        "volumeCount": vol.get("count"),
                        "volumeType": vol.get("volumeType"),
                        "volumeSize": vol.get("size")
                    })
                    rows.append(row)
            else:
                base.update({
                    "volumeCount": None,
                    "volumeType": None,
                    "volumeSize": None
                })
                rows.append(base)
    return rows

def flatten_datalake_instance_groups(datalake_name, environment_name, datalake_obj, timestamp):
    """
    Flatten the instanceGroups for a datalake, similar to flatten_instance_groups for DataHub.
    This function supports AWS, Azure, and GCP datalakes.
    """
    rows = []
    # Top-level instanceGroups (for newer API responses)
    instance_groups = datalake_obj.get("instanceGroups", [])
    if instance_groups:
        for ig in instance_groups:
            ig_name = ig.get("name")
            azs = ",".join(ig.get("availabilityZones", []))
            recipes = ",".join(ig.get("recipes", []))
            for inst in ig.get("instances", []):
                base = {
                    "environment": environment_name,
                    "datalakeName": datalake_name,
                    "instanceGroupName": ig_name,
                    "availabilityZones": azs,
                    "recipes": recipes,
                    "nodeGroupRole": inst.get("instanceGroup"),
                    "instanceId": inst.get("id"),
                    "state": inst.get("state"),
                    "discoveryFQDN": inst.get("discoveryFQDN"),
                    "instanceStatus": inst.get("instanceStatus"),
                    "statusReason": inst.get("statusReason"),
                    "privateIp": inst.get("privateIp"),
                    "publicIp": inst.get("publicIp"),
                    "sshPort": inst.get("sshPort"),
                    "clouderaManagerServer": inst.get("clouderaManagerServer"),
                    "instanceTypeVal": inst.get("instanceTypeVal"),
                    "availabilityZone": inst.get("availabilityZone"),
                    "instanceVmType": inst.get("instanceVmType"),
                    "rackId": inst.get("rackId"),
                    "subnetId": inst.get("subnetId")
                }
                volumes = inst.get("attachedVolumes", [])
                if volumes:
                    for vol in volumes:
                        row = base.copy()
                        row.update({
                            "volumeCount": vol.get("count"),
                            "volumeType": vol.get("volumeType"),
                            "volumeSize": vol.get("size")
                        })
                        rows.append(row)
                else:
                    base.update({
                        "volumeCount": None,
                        "volumeType": None,
                        "volumeSize": None
                    })
                    rows.append(base)
    else:
        # Try to find instanceGroups under cloud provider configuration
        for config_key in ["awsConfiguration", "azureConfiguration", "gcpConfiguration"]:
            config = datalake_obj.get(config_key, {})
            if isinstance(config, dict):
                instance_groups = config.get("instanceGroups", [])
                for ig in instance_groups:
                    ig_name = ig.get("name")
                    azs = ",".join(ig.get("availabilityZones", []))
                    recipes = ",".join(ig.get("recipes", []))
                    for inst in ig.get("instances", []):
                        base = {
                            "environment": environment_name,
                            "datalakeName": datalake_name,
                            "instanceGroupName": ig_name,
                            "availabilityZones": azs,
                            "recipes": recipes,
                            "nodeGroupRole": inst.get("instanceGroup"),
                            "instanceId": inst.get("id"),
                            "state": inst.get("state"),
                            "discoveryFQDN": inst.get("discoveryFQDN"),
                            "instanceStatus": inst.get("instanceStatus"),
                            "statusReason": inst.get("statusReason"),
                            "privateIp": inst.get("privateIp"),
                            "publicIp": inst.get("publicIp"),
                            "sshPort": inst.get("sshPort"),
                            "clouderaManagerServer": inst.get("clouderaManagerServer"),
                            "instanceTypeVal": inst.get("instanceTypeVal"),
                            "availabilityZone": inst.get("availabilityZone"),
                            "instanceVmType": inst.get("instanceVmType"),
                            "rackId": inst.get("rackId"),
                            "subnetId": inst.get("subnetId")
                        }
                        volumes = inst.get("attachedVolumes", [])
                        if volumes:
                            for vol in volumes:
                                row = base.copy()
                                row.update({
                                    "volumeCount": vol.get("count"),
                                    "volumeType": vol.get("volumeType"),
                                    "volumeSize": vol.get("size")
                                })
                                rows.append(row)
                        else:
                            base.update({
                                "volumeCount": None,
                                "volumeType": None,
                                "volumeSize": None
                            })
                            rows.append(base)
    return rows

def flatten_freeipa_instance_groups(environment_name, freeipa_obj, timestamp):
    """
    Flatten the FreeIPA instance groups, similar to DataHub and Datalake logic.
    Returns a list of rows, each representing an instance in a group, with attached volume info.
    """
    rows = []
    if not freeipa_obj:
        return rows

    # FreeIPA does not have explicit instanceGroups, but we can treat all instances as a single group or by instanceGroup field.
    instances = freeipa_obj.get("instances", [])
    recipes = ",".join(freeipa_obj.get("recipes", []))
    # Group by instanceGroup field if present, else treat as one group
    for inst in instances:
        ig_name = inst.get("instanceGroup") or "default"
        az = inst.get("availabilityZone") or ""
        # FreeIPA does not have subnetIds at top level, but subnetId per instance
        subnet_id = inst.get("subnetId") or ""
        # Recipes are at top level for FreeIPA
        base = {
            "environment": environment_name,
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

def save_instance_groups_to_csv(csv_path, rows):
    if not rows:
        log(f"⚠️ No instance group data to write: {csv_path}")
        return
    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    log(f"✅ Saved CSV: {csv_path}")

def describe_unique_recipes(recipe_dir, all_recipes_set, profile, debug=False):
    for recipe_name in sorted(all_recipes_set):
        describe, err = run_command_json(
            f"cdp datahub describe-recipe --profile {profile} --recipe-name {recipe_name}",
            task_name=f"Describing recipe {recipe_name}",
            debug=debug
        )
        if describe:
            json_path = recipe_dir / f"recipe_{recipe_name}.json"
            script_path = recipe_dir / f"recipe_{recipe_name}.sh"
            save_to_file(describe, json_path)
            recipe_content = describe.get("recipe", {}).get("recipeContent")
            if recipe_content:
                save_recipe_script(recipe_content, script_path)
        else:
            log(f"⚠️ Failed to describe recipe: {recipe_name}")

def describe_unique_datalake_recipes(recipe_dir, all_recipes_set, profile, debug=False):
    """
    For each unique datalake recipe name, describe it using the CLI and save its details and script.
    """
    for recipe_name in sorted(all_recipes_set):
        describe, err = run_command_json(
            f"cdp datalake describe-recipe --profile {profile} --recipe-name {recipe_name}",
            task_name=f"Describing datalake recipe {recipe_name}",
            debug=debug
        )
        if describe:
            json_path = recipe_dir / f"recipe_{recipe_name}.json"
            script_path = recipe_dir / f"recipe_{recipe_name}.sh"
            save_to_file(describe, json_path)
            recipe_content = describe.get("recipe", {}).get("recipeContent")
            if recipe_content:
                save_recipe_script(recipe_content, script_path)
        else:
            log(f"⚠️ Failed to describe datalake recipe: {recipe_name}")

def flatten_json(y, parent_key='', sep='.'):
    items = []
    if isinstance(y, list):
        for i, v in enumerate(y):
            new_key = f"{parent_key}[{i}]" if parent_key else str(i)
            items.extend(flatten_json(v, new_key, sep=sep).items())
    elif isinstance(y, MutableMapping):
        for k, v in y.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            items.extend(flatten_json(v, new_key, sep=sep).items())
    else:
        items.append((parent_key, y))
    return dict(items)

def save_flattened_json_to_csv(json_obj, csv_path):
    if isinstance(json_obj, list):
        flat_rows = [flatten_json(item) for item in json_obj]
    else:
        flat_rows = [flatten_json(json_obj)]
    fieldnames = set()
    for row in flat_rows:
        fieldnames.update(row.keys())
    fieldnames = sorted(fieldnames)
    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in flat_rows:
            writer.writerow(row)
    log(f"✅ Saved CSV: {csv_path}")

def flatten_freeipa_instances(freeipa_details):
    # Deprecated: replaced by flatten_freeipa_instance_groups for instance group logic
    rows = []
    if not freeipa_details:
        return rows
    instances = freeipa_details.get("instances", [])
    for inst in instances:
        row = flatten_json(inst)
        for k in freeipa_details:
            if k != "instances":
                row[f"freeipaDetails.{k}"] = freeipa_details[k]
        rows.append(row)
    return rows

def flatten_datalake_instances(datalake_details):
    rows = []
    if not datalake_details:
        return rows
    config = None
    for key in ["awsConfiguration", "azureConfiguration", "gcpConfiguration"]:
        if key in datalake_details:
            config = datalake_details[key]
            break
    if not config:
        return rows
    instances = config.get("instances", [])
    for inst in instances:
        row = flatten_json(inst)
        for k in datalake_details:
            if k not in ["awsConfiguration", "azureConfiguration", "gcpConfiguration"]:
                row[f"datalakeDetails.{k}"] = datalake_details[k]
        row["cloudProvider"] = key.replace("Configuration", "")
        rows.append(row)
    return rows

def get_cod_database_details(database_name, environment_name, profile, debug=False):
    """
    Run 'cdp opdb describe-database' for the given COD database name and environment.
    Returns the JSON object (or None, error).
    """
    cmd = f"cdp opdb describe-database --profile {profile} --database-name {database_name} --environment-name {environment_name}"
    return run_command_json(cmd, task_name=f"Describing COD database {database_name}", debug=debug)

def get_cod_database_name_for_cluster(cluster_internal_name, environment_name, profile, debug=False):
    """
    List all opdb databases in the environment, and find the one whose 'internalName' matches the DataHub clusterName.
    Returns the 'databaseName' if found, else None.
    """
    # The correct approach is to list all COD databases in the environment,
    # then find the one whose "internalName" matches the DataHub clusterName,
    # and then get its "databaseName".
    cmd = f"cdp opdb list-databases --profile {profile} --environment-name {environment_name}"
    opdb_list_json, opdb_list_err = run_command_json(cmd, task_name=f"Listing COD databases for {environment_name}", debug=debug)
    if not opdb_list_json:
        if debug:
            log(f"DEBUG: Could not list COD databases: {opdb_list_err}")
        return None
    databases = opdb_list_json.get("databases", [])
    for db in databases:
        # The correct field to match is "internalName"
        internal_name = db.get("internalName")
        # The correct field to use for describe is "databaseName"
        database_name = db.get("databaseName")
        if internal_name == cluster_internal_name:
            return database_name
    return None

def main():
    environment_name = None
    output_arg = None
    profile = "default"
    debug = False

    args = sys.argv[1:]
    if not args or "--help" in args or "-h" in args:
        usage()

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--output-dir":
            if i + 1 < len(args):
                output_arg = args[i + 1]
                i += 2
            else:
                usage()
        elif arg == "--profile":
            if i + 1 < len(args):
                profile = args[i + 1]
                i += 2
            else:
                usage()
        elif arg == "--debug":
            debug = True
            i += 1
        elif arg == "--environment-name":
            if i + 1 < len(args):
                environment_name = args[i + 1]
                i += 2
            else:
                usage()
        else:
            i += 1

    if not environment_name:
        usage()

    profiles = get_cdp_profiles()
    if not profiles:
        log("⚠️ No CDP CLI profiles found in ~/.cdp/credentials. Please configure the CDP CLI before running this script.")
        sys.exit(1)
    if profile not in profiles:
        log(f"⚠️ Profile '{profile}' not found in ~/.cdp/credentials. Available profiles: {profiles}")
        sys.exit(1)

    timestamp = get_timestamp()

    # --- Begin output_dir logic rewrite ---
    if output_arg:
        # If the user provided --output-dir, append the timestamp to the folder name
        # If the path ends with a slash, remove it for consistency
        output_arg = output_arg.rstrip("/")
        # If the output_arg already ends with the timestamp, don't double-append
        if not output_arg.endswith(timestamp):
            base_dir = Path(f"{output_arg}-{timestamp}")
        else:
            base_dir = Path(output_arg)
    else:
        base_dir = Path(f"/tmp/discovery_datahubs-{timestamp}")
    # --- End output_dir logic rewrite ---

    base_dir.mkdir(parents=True, exist_ok=True)

    log(f"🔍 Starting DataHub discovery for environment: {environment_name} (profile: {profile})")

    # --- ENVIRONMENT SECTION ---
    environment_dir = base_dir / "environment"
    environment_dir.mkdir(parents=True, exist_ok=True)

    # 1. Describe the environment and save JSON
    env_json_path = environment_dir / f"ENVIRONMENT_ENV_{environment_name}_{timestamp}.json"
    env_cmd = f"cdp environments describe-environment --profile {profile} --environment-name {environment_name}"
    env_json, env_err = run_command_json(env_cmd, task_name=f"Describing environment {environment_name}", debug=debug)
    if env_json:
        save_to_file(env_json, env_json_path)
        env_obj = env_json.get("environment", env_json)
        env_csv_path = environment_dir / f"ENVIRONMENT_ENV_{environment_name}_{timestamp}.csv"
        save_flattened_json_to_csv(env_obj, env_csv_path)
    else:
        log(f"⚠️ Could not describe environment {environment_name}")
        if debug:
            log(f"DEBUG: env_err: {env_err}")

    # 2. Get FreeIPA upgrade options and save JSON
    freeipa_upgrade_json_path = environment_dir / f"ENVIRONMENT_ENV_{environment_name}_FreeIPAUpgradeOptions_{timestamp}.json"
    freeipa_upgrade_cmd = f"cdp environments get-freeipa-upgrade-options --profile {profile} --environment {environment_name}"
    freeipa_upgrade_json, freeipa_upgrade_err = run_command_json(freeipa_upgrade_cmd, task_name=f"Getting FreeIPA upgrade options for {environment_name}", debug=debug)
    if freeipa_upgrade_json:
        save_to_file(freeipa_upgrade_json, freeipa_upgrade_json_path)
    else:
        log(f"⚠️ Could not get FreeIPA upgrade options for {environment_name}")
        if debug:
            log(f"DEBUG: freeipa_upgrade_err: {freeipa_upgrade_err}")

    # 3. Flatten FreeIPA details and instances to CSV (ENHANCED LOGIC)
    freeipa_details = None
    if env_json:
        env_obj = env_json.get("environment", env_json)
        freeipa_details = env_obj.get("freeipa") or env_obj.get("freeIpaDetails") or env_obj.get("freeIpa")
    if freeipa_details:
        # Enhanced: flatten instance groups for FreeIPA, similar to DataHub/Datalake
        freeipa_ig_rows = flatten_freeipa_instance_groups(environment_name, freeipa_details, timestamp)
        if freeipa_ig_rows:
            freeipa_ig_csv_path = environment_dir / f"ENVIRONMENT_ENV_{environment_name}_FreeIPAInstanceGroups_{timestamp}.csv"
            save_instance_groups_to_csv(freeipa_ig_csv_path, freeipa_ig_rows)
        else:
            log(f"⚠️ No FreeIPA instance groups found for {environment_name}")
    else:
        log(f"⚠️ No FreeIPA details found for {environment_name}")

    # --- DATALAKE SECTION ---
    datalake_dir = base_dir / "datalake"
    datalake_dir.mkdir(parents=True, exist_ok=True)

    datalake_recipes_set = set()

    datalake_list_cmd = f"cdp datalake list-datalakes --profile {profile} --environment-name {environment_name}"
    datalake_list_json, datalake_list_err = run_command_json(datalake_list_cmd, task_name=f"Listing Datalakes for {environment_name}", debug=debug)
    datalakes = datalake_list_json.get("datalakes", []) if datalake_list_json else []

    all_datalake_instance_rows = []

    if datalakes:
        log(f"🛢️ Found {len(datalakes)} datalake(s):")
        for dl in datalakes:
            log(f"  - {dl.get('datalakeName')}")

        for datalake in datalakes:
            datalake_crn = datalake.get("crn")
            datalake_name = datalake.get("datalakeName")
            if not datalake_crn or not datalake_name:
                continue

            dl_subdir = datalake_dir / datalake_name
            dl_subdir.mkdir(parents=True, exist_ok=True)
            output_prefix = f"ENVIRONMENT_ENV_{environment_name}_DL_{datalake_name}"

            # 1. Describe the datalake
            describe_dl_cmd = f"cdp datalake describe-datalake --profile {profile} --datalake-name {datalake_crn}"
            describe_dl_json, describe_dl_err = run_command_json(describe_dl_cmd, task_name=f"Describing datalake {datalake_name}", debug=debug)
            if describe_dl_json:
                describe_dl_path = dl_subdir / f"{output_prefix}_{timestamp}.json"
                save_to_file(describe_dl_json, describe_dl_path)
                describe_dl_csv_path = dl_subdir / f"{output_prefix}_{timestamp}.csv"
                dl_obj = describe_dl_json.get("datalake", describe_dl_json.get("datalakeDetails", describe_dl_json))
                save_flattened_json_to_csv(dl_obj, describe_dl_csv_path)

                # --- DATALAKE INSTANCE GROUPS LOGIC ---
                dl_instance_groups_rows = flatten_datalake_instance_groups(datalake_name, environment_name, dl_obj, timestamp)
                if dl_instance_groups_rows:
                    dl_ig_csv_path = dl_subdir / f"{output_prefix}_InstanceGroups_{timestamp}.csv"
                    save_instance_groups_to_csv(dl_ig_csv_path, dl_instance_groups_rows)
                    all_datalake_instance_rows.extend(dl_instance_groups_rows)
                else:
                    log(f"⚠️ No datalake instance groups found for {datalake_name}")

                # --- DATALAKE RECIPES LOGIC ---

                # 1. Top-level "recipes" key
                recipes_top = dl_obj.get("recipes", [])
                for recipe in recipes_top:
                    datalake_recipes_set.add(recipe)

                # 2. Recipes under configuration
                for config_key in ["awsConfiguration", "azureConfiguration", "gcpConfiguration"]:
                    config = dl_obj.get(config_key, {})
                    if isinstance(config, dict):
                        # recipes at config level
                        for recipe in config.get("recipes", []):
                            datalake_recipes_set.add(recipe)
                        # recipes under instanceGroups (if present)
                        for ig in config.get("instanceGroups", []):
                            for recipe in ig.get("recipes", []):
                                datalake_recipes_set.add(recipe)

                # 3. Recipes under instanceGroups at top level (if present)
                for ig in dl_obj.get("instanceGroups", []):
                    for recipe in ig.get("recipes", []):
                        datalake_recipes_set.add(recipe)

            else:
                log(f"⚠️ Could not describe datalake {datalake_name}")
                if debug:
                    log(f"DEBUG: describe_dl_err: {describe_dl_err}")

            # 2. Describe the database server for the datalake
            describe_db_cmd = f"cdp datalake describe-database-server --profile {profile} --cluster-crn {datalake_crn}"
            describe_db_json, describe_db_err = run_command_json(describe_db_cmd, task_name=f"Describing DB server for datalake {datalake_name}", debug=debug)
            if describe_db_json:
                describe_db_path = dl_subdir / f"{output_prefix}_DB_{timestamp}.json"
                save_to_file(describe_db_json, describe_db_path)
                describe_db_csv_path = dl_subdir / f"{output_prefix}_DB_{timestamp}.csv"
                save_flattened_json_to_csv(describe_db_json, describe_db_csv_path)
            else:
                log(f"⚠️ Could not describe DB server for datalake {datalake_name}")
                if debug:
                    log(f"DEBUG: describe_db_err: {describe_db_err}")

            # 3. Show available upgrade images
            for suffix, label, upgrade_flag in [
                ("AvailableImages", "Checking available upgrade images", "--show-available-images"),
                ("RunTimeAvailableImages", "Checking latest runtime image", "--show-latest-available-image-per-runtime")
            ]:
                upgrade_cmd = f"cdp datalake upgrade-datalake --profile {profile} {upgrade_flag} --datalake-name {datalake_crn}"
                upgrade_json, upgrade_err = run_command_json(upgrade_cmd, task_name=f"{label} for datalake {datalake_name}", debug=debug)
                if upgrade_json:
                    upgrade_path = dl_subdir / f"{output_prefix}_{suffix}_{timestamp}.json"
                    save_to_file(upgrade_json, upgrade_path)
                    upgrade_csv_path = dl_subdir / f"{output_prefix}_{suffix}_{timestamp}.csv"
                    save_flattened_json_to_csv(upgrade_json, upgrade_csv_path)
                else:
                    log(f"⚠️ Skipping {suffix} for datalake {datalake_name}")
                    if debug:
                        log(f"DEBUG: {suffix} err: {upgrade_err}")
    else:
        log("No Datalakes found in this environment.")
        if debug:
            log(f"DEBUG: datalake_list_json: {datalake_list_json}")
            log(f"DEBUG: datalake_list_err: {datalake_list_err}")

    all_instance_rows = []
    all_recipes_set = set()

    # --- DATALAKE RECIPES: describe and save ---
    if datalake_recipes_set:
        for datalake in datalakes:
            datalake_name = datalake.get("datalakeName")
            if not datalake_name:
                continue
            dl_subdir = datalake_dir / datalake_name
            recipe_dir = dl_subdir / "recipes"
            describe_unique_datalake_recipes(recipe_dir, datalake_recipes_set, profile, debug=debug)
    else:
        log("ℹ️ No recipes found in datalake(s).")

    # Save all datalake instance groups to a global CSV
    if all_datalake_instance_rows:
        save_instance_groups_to_csv(base_dir / f"ALL_{environment_name}_datalake_instance_groups.csv", all_datalake_instance_rows)

    # List all DataHub clusters in the environment
    list_output, list_err = run_command_json(
        f"cdp datahub list-clusters --profile {profile} --environment-name {environment_name}",
        task_name="Listing DataHub clusters",
        debug=debug
    )
    clusters = list_output.get("clusters", []) if list_output else []

    if not clusters:
        log("No DataHub clusters found.")
        if debug:
            log(f"DEBUG: list_output: {list_output}")
            log(f"DEBUG: list_err: {list_err}")
            log(f"DEBUG: Profile used: {profile}")
            log(f"DEBUG: Available profiles: {profiles}")
            log(f"DEBUG: Environment name: {environment_name}")
        sys.exit(0)

    log(f"🧩 Found {len(clusters)} cluster(s):")
    for c in clusters:
        log(f"  - {c.get('clusterName')}")

    # Pre-fetch all COD databases for the environment for efficient lookup
    cod_db_lookup = {}
    cod_db_list_json, cod_db_list_err = run_command_json(
        f"cdp opdb list-databases --profile {profile} --environment-name {environment_name}",
        task_name=f"Listing COD databases for {environment_name}",
        debug=debug
    )
    if cod_db_list_json:
        for db in cod_db_list_json.get("databases", []):
            internal_name = db.get("internalName")
            database_name = db.get("databaseName")
            if internal_name and database_name:
                cod_db_lookup[internal_name] = database_name

    for cluster in clusters:
        name = cluster.get("clusterName")
        crn = cluster.get("crn")
        if not name or not crn:
            continue

        cluster_dir = base_dir / name
        recipe_dir = cluster_dir / "recipes"

        # Describe the cluster and save its details
        describe, describe_err = run_command_json(
            f"cdp datahub describe-cluster --profile {profile} --cluster-name {crn}",
            task_name=f"Describing cluster {name}",
            debug=debug
        )
        if not describe:
            log(f"⚠️ Skipping describe for {name}")
            if debug:
                log(f"DEBUG: describe_err: {describe_err}")
            continue

        output_prefix = f"ENVIRONMENT_ENV_{environment_name}_DH_{name}"
        save_to_file(describe, cluster_dir / f"{output_prefix}_{timestamp}.json")

        # Special handling for COD (Operational Database) clusters
        # Instead of using the DataHub clusterName as the COD database name, we must:
        # 1. List all COD databases in the environment (already done above)
        # 2. Find the one whose "internalName" matches the DataHub clusterName
        # 3. Use its "databaseName" to describe the COD database
        if name and name.startswith("cod-"):
            cod_database_name = cod_db_lookup.get(name)
            if cod_database_name:
                cod_json, cod_err = get_cod_database_details(cod_database_name, environment_name, profile, debug=debug)
                if cod_json:
                    cod_json_path = cluster_dir / f"{output_prefix}_COD_{timestamp}.json"
                    save_to_file(cod_json, cod_json_path)
                else:
                    log(f"⚠️ Could not describe COD database {cod_database_name} (matched for cluster {name})")
                    if debug:
                        log(f"DEBUG: COD describe error: {cod_err}")
            else:
                log(f"⚠️ Could not find COD databaseName for cluster internalName '{name}' in environment '{environment_name}'")
        # End COD logic

        # Flatten and save instance group information
        instance_groups = describe.get("cluster", {}).get("instanceGroups", [])
        rows = flatten_instance_groups(name, environment_name, instance_groups, timestamp)
        save_instance_groups_to_csv(cluster_dir / f"{output_prefix}_InstanceGroups_{timestamp}.csv", rows)
        all_instance_rows.extend(rows)

        # Collect all unique recipes from instance groups
        for ig in instance_groups:
            for recipe in ig.get("recipes", []):
                all_recipes_set.add(recipe)

        # Describe the cluster template if available
        template_crn = describe.get("cluster", {}).get("clusterTemplateCrn")
        template_name = describe.get("cluster", {}).get("clusterTemplateName")

        if template_crn:
            template, template_err = run_command_json(
                f"cdp datahub describe-cluster-template --profile {profile} --cluster-template-name {template_crn}",
                task_name=f"Describing template for {name}",
                debug=debug
            )

            if template:
                cluster_template = template.get("clusterTemplate", {})
                status = cluster_template.get("status")
                template_name = cluster_template.get("clusterTemplateName", "").strip()
                content = cluster_template.get("clusterTemplateContent")

                save_to_file(
                    {"clusterTemplate": cluster_template},
                    cluster_dir / f"{output_prefix}_Template_{timestamp}.json"
                )

                if status in ("USER_MANAGED", "DEFAULT") and content:
                    safe_template_name = template_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
                    content_path = cluster_dir / f"{safe_template_name}_content.json"
                    try:
                        parsed_content = json.loads(content)
                        with open(content_path, "w", encoding="utf-8") as f:
                            json.dump(parsed_content, f, indent=4)
                        log(f"✅ Pretty-printed template content saved to {content_path}")
                    except json.JSONDecodeError:
                        log(f"⚠️ Failed to parse JSON content from template {template_name}, saving raw.")
                        with open(content_path, "w", encoding="utf-8") as f:
                            f.write(content)
                elif status == "SERVICE_MANAGED":
                    log(f"ℹ️ Skipping content extraction for {name} (status: default template SERVICE_MANAGED)")
                else:
                    log(f"⚠️ Template content missing for {template_name} ({name})")
            else:
                log(f"⚠️ Skipping template describe for {name}")
                if debug:
                    log(f"DEBUG: template_err: {template_err}")
        else:
            log(f"⚠️ clusterTemplateCrn not found for {name}, skipping template describe.")

        for suffix, label in [
            ("AvailableImages", "Checking available upgrade images"),
            ("RunTimeAvailableImages", "Checking latest runtime image")
        ]:
            command = (
                f"cdp datahub upgrade-cluster --profile {profile} --show-available-images --cluster-name {crn}"
                if suffix == "AvailableImages"
                else f"cdp datahub upgrade-cluster --profile {profile} --show-latest-available-image-per-runtime --cluster-name {crn}"
            )
            data, err = run_command_json(command, task_name=f"{label} for {name}", debug=debug)
            if data:
                save_to_file(data, cluster_dir / f"{output_prefix}_{suffix}_{timestamp}.json")
            else:
                log(f"⚠️ Skipping {suffix} for {name}")
                if debug:
                    log(f"DEBUG: {suffix} err: {err}")

        db_server, db_err = run_command_json(
            f"cdp datahub describe-database-server --profile {profile} --cluster-crn {crn}",
            task_name=f"Describing DB server for {name}",
            debug=debug
        )
        if db_server:
            save_to_file(db_server, cluster_dir / f"{output_prefix}_DB_{timestamp}.json")
        else:
            log(f"⚠️ Skipping DB server describe for {name}")
            if debug:
                log(f"DEBUG: db_err: {db_err}")

        if all_recipes_set:
            describe_unique_recipes(recipe_dir, all_recipes_set, profile, debug=debug)
        else:
            log(f"ℹ️ No recipes found in cluster: {name}")

    if all_instance_rows:
        save_instance_groups_to_csv(base_dir / f"ALL_{environment_name}_datahub_instance_groups.csv", all_instance_rows)

    archive_path = f"{base_dir}.tar.gz"
    shutil.make_archive(str(base_dir), 'gztar', root_dir=base_dir)
    log(f"📦 Archived output to: {archive_path}")
    log(f"🏁 Done. Output saved in: {base_dir}")

if __name__ == "__main__":
    main()