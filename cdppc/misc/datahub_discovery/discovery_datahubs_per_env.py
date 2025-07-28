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

def log(message):
    """
    Print a log message with a timestamp.
    """
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def usage():
    """
    Print usage instructions and exit the script.
    """
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
    """
    Parse ~/.cdp/credentials and return a list of available profiles.
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

def spinner_thread_func(stop_event, message):
    """
    Display a spinner animation in the terminal while a background task is running.

    Args:
        stop_event (threading.Event): Event to signal the spinner to stop.
        message (str): Message to display alongside the spinner.
    """
    for symbol in itertools.cycle("|/-\\"):
        if stop_event.is_set():
            break
        print(f"\r [{symbol}] {message}", end="", flush=True)
        time.sleep(0.1)
    print("\r", end="")

def run_command(command, task_name=None, debug=False):
    """
    Run a shell command and optionally display a spinner while it runs.

    Args:
        command (str): The shell command to execute.
        task_name (str, optional): If provided, display a spinner with this task name.
        debug (bool): If True, print the command and output for debugging.

    Returns:
        tuple: (stdout output as str or None, stderr output as str or None)
    """
    stop_spinner = threading.Event()
    if task_name:
        spinner = threading.Thread(target=spinner_thread_func, args=(stop_spinner, task_name))
        spinner.start()
    try:
        if debug:
            log(f"DEBUG: Running command: {command}")
        # Use shell=True to allow --profile to be parsed correctly
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
    """
    Run a shell command and parse its output as JSON.

    Args:
        command (str): The shell command to execute.
        task_name (str, optional): If provided, display a spinner with this task name.
        debug (bool): If True, print the command and output for debugging.

    Returns:
        tuple: (parsed JSON object or None, error message or None)
    """
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
    """
    Save data to a file. If data is a string, write as text; otherwise, dump as JSON.

    Args:
        data (str or dict): Data to save.
        filepath (Path): Path to the output file.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, indent=2)
    log(f"✅ Saved: {filepath}")

def save_recipe_script(content, filepath):
    """
    Save a recipe script to a file and format it with shfmt if available.

    Args:
        content (str): Script content.
        filepath (Path): Path to the output file.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        f.write(content)
    if shutil.which("shfmt"):
        subprocess.run(["shfmt", "-w", filepath], check=False)
        log(f"✅ Saved (formatted): {filepath}")
    else:
        log("⚠️ 'shfmt' not found, skipping shell formatting.")

def get_timestamp():
    """
    Get the current timestamp as a string in the format YYYYMMDDHHMMSS.

    Returns:
        str: Timestamp string.
    """
    return datetime.now().strftime("%Y%m%d%H%M%S")

def flatten_instance_groups(cluster_name, environment_name, instance_groups, timestamp):
    """
    Flatten instance group data into a list of dictionaries for CSV export.

    Args:
        cluster_name (str): Name of the cluster.
        environment_name (str): Name of the environment.
        instance_groups (list): List of instance group dictionaries.
        timestamp (str): Timestamp string.

    Returns:
        list: List of dictionaries, each representing an instance (and its volumes).
    """
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
                # If there are attached volumes, create a row for each volume
                for vol in volumes:
                    row = base.copy()
                    row.update({
                        "volumeCount": vol.get("count"),
                        "volumeType": vol.get("volumeType"),
                        "volumeSize": vol.get("size")
                    })
                    rows.append(row)
            else:
                # If no volumes, set volume fields to None
                base.update({
                    "volumeCount": None,
                    "volumeType": None,
                    "volumeSize": None
                })
                rows.append(base)
    return rows

def save_instance_groups_to_csv(csv_path, rows):
    """
    Save a list of instance group rows to a CSV file.

    Args:
        csv_path (Path): Path to the output CSV file.
        rows (list): List of dictionaries to write as rows.
    """
    if not rows:
        log(f"⚠️ No instance group data to write: {csv_path}")
        return
    with open(csv_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    log(f"✅ Saved CSV: {csv_path}")

def describe_unique_recipes(recipe_dir, all_recipes_set, profile, debug=False):
    """
    For each unique recipe name, describe it using the CLI and save its details and script.

    Args:
        recipe_dir (Path): Directory to save recipe files.
        all_recipes_set (set): Set of unique recipe names.
        profile (str): CDP CLI profile to use.
        debug (bool): If True, print debug info.
    """
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

def main():
    """
    Main function to orchestrate the discovery and export of DataHub cluster information
    for a given environment. Handles command-line arguments, output directory, and
    iterates through clusters to collect and save their details.
    """
    # Argument parsing
    environment_name = None
    output_arg = None
    profile = "default"
    debug = False

    args = sys.argv[1:]
    # Show usage if no arguments or --help/-h is present
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

    # Check for CDP CLI configuration
    profiles = get_cdp_profiles()
    if not profiles:
        log("⚠️ No CDP CLI profiles found in ~/.cdp/credentials. Please configure the CDP CLI before running this script.")
        sys.exit(1)
    if profile not in profiles:
        log(f"⚠️ Profile '{profile}' not found in ~/.cdp/credentials. Available profiles: {profiles}")
        sys.exit(1)

    timestamp = get_timestamp()
    base_dir = Path(output_arg or f"/tmp/discovery_datahubs-{timestamp}")
    base_dir.mkdir(parents=True, exist_ok=True)

    log(f"🔍 Starting DataHub discovery for environment: {environment_name} (profile: {profile})")

    all_instance_rows = []
    all_recipes_set = set()

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

            # If template information is available, save it and its content
            if template:
                cluster_template = template.get("clusterTemplate", {})
                status = cluster_template.get("status")
                template_name = cluster_template.get("clusterTemplateName", "").strip()
                content = cluster_template.get("clusterTemplateContent")

                # Always save the full template description
                save_to_file(
                    {"clusterTemplate": cluster_template},
                    cluster_dir / f"{output_prefix}_Template_{timestamp}.json"
                )

                # Save the template content separately for user-managed or default templates
                if status in ("USER_MANAGED", "DEFAULT") and content:
                    # Make filename-safe version of template name
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

        # Check available upgrade images and latest runtime image for the cluster
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

        # Describe the database server for the cluster
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

        # Describe all unique recipes found in the cluster
        if all_recipes_set:
            describe_unique_recipes(recipe_dir, all_recipes_set, profile, debug=debug)
        else:
            log(f"ℹ️ No recipes found in cluster: {name}")

    # Save all instance group data for all clusters to a single CSV
    if all_instance_rows:
        save_instance_groups_to_csv(base_dir / f"ALL_{environment_name}_instance_groups.csv", all_instance_rows)

    # Archive the output directory as a tar.gz file
    archive_path = f"{base_dir}.tar.gz"
    shutil.make_archive(str(base_dir), 'gztar', root_dir=base_dir)
    log(f"📦 Archived output to: {archive_path}")
    log(f"🏁 Done. Output saved in: {base_dir}")

if __name__ == "__main__":
    main()