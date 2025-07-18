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


def log(message):
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def usage():
    print("Usage: python list_and_describe_datahubs.py <environment-name> [--output-dir <path>]")
    sys.exit(1)


def spinner_thread_func(stop_event, message):
    for symbol in itertools.cycle("|/-\\"):
        if stop_event.is_set():
            break
        print(f"\r [{symbol}] {message}", end="", flush=True)
        time.sleep(0.1)
    print("\r", end="")


def run_command(command, task_name=None):
    stop_spinner = threading.Event()
    if task_name:
        spinner = threading.Thread(target=spinner_thread_func, args=(stop_spinner, task_name))
        spinner.start()
    try:
        result = subprocess.run(command.split(), capture_output=True, text=True)
        if task_name:
            stop_spinner.set()
            spinner.join()
        if result.returncode != 0:
            return None, result.stderr.strip()
        return result.stdout.strip(), None
    except Exception as e:
        if task_name:
            stop_spinner.set()
            spinner.join()
        return None, str(e)


def run_command_json(command, task_name=None):
    output, error = run_command(command, task_name)
    if output:
        try:
            return json.loads(output), None
        except json.JSONDecodeError:
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


def save_instance_groups_to_csv(csv_path, rows):
    if not rows:
        log(f"⚠️ No instance group data to write: {csv_path}")
        return
    with open(csv_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    log(f"✅ Saved CSV: {csv_path}")


def describe_unique_recipes(recipe_dir, all_recipes_set):
    for recipe_name in sorted(all_recipes_set):
        describe, err = run_command_json(
            f"cdp datahub describe-recipe --recipe-name {recipe_name}",
            task_name=f"Describing recipe {recipe_name}"
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
    if len(sys.argv) < 2:
        usage()

    environment_name = sys.argv[1]
    output_arg = None
    if len(sys.argv) == 4 and sys.argv[2] == "--output-dir":
        output_arg = sys.argv[3]

    timestamp = get_timestamp()
    base_dir = Path(output_arg or f"/tmp/discovery_datahubs-{timestamp}")
    base_dir.mkdir(parents=True, exist_ok=True)

    log(f"🔍 Starting DataHub discovery for environment: {environment_name}")

    all_instance_rows = []
    all_recipes_set = set()

    list_output, list_err = run_command_json(
        f"cdp datahub list-clusters --environment-name {environment_name}",
        task_name="Listing DataHub clusters"
    )
    clusters = list_output.get("clusters", []) if list_output else []

    if not clusters:
        log("No DataHub clusters found.")
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

        describe, describe_err = run_command_json(
            f"cdp datahub describe-cluster --cluster-name {crn}",
            task_name=f"Describing cluster {name}"
        )
        if not describe:
            log(f"⚠️ Skipping describe for {name}")
            continue

        output_prefix = f"ENVIRONMENT_ENV_{environment_name}_DH_{name}"
        save_to_file(describe, cluster_dir / f"{output_prefix}_{timestamp}.json")

        instance_groups = describe.get("cluster", {}).get("instanceGroups", [])
        rows = flatten_instance_groups(name, environment_name, instance_groups, timestamp)
        save_instance_groups_to_csv(cluster_dir / f"{output_prefix}_InstanceGroups_{timestamp}.csv", rows)
        all_instance_rows.extend(rows)

        
        for ig in instance_groups:
            for recipe in ig.get("recipes", []):
                all_recipes_set.add(recipe)

        template_crn = describe.get("cluster", {}).get("clusterTemplateCrn")
        template_name = describe.get("cluster", {}).get("clusterTemplateName")

        if template_crn:
            template, template_err = run_command_json(
                f"cdp datahub describe-cluster-template --cluster-template-name {template_crn}",
                task_name=f"Describing template for {name}"
            )

            #log(f"Template describe output: {template}")
            #if not template and template_err:
            #    log(f"⚠️ CLI stderr:\n{template_err}")


            if template:
                cluster_template = template.get("clusterTemplate", {})
                status = cluster_template.get("status")
                template_name = cluster_template.get("clusterTemplateName", "").strip()
                content = cluster_template.get("clusterTemplateContent")

                # Always save full template describe regardless of status
                save_to_file(
                    {"clusterTemplate": cluster_template},
                    cluster_dir / f"{output_prefix}_Template_{timestamp}.json"
                )

                # If USER_MANAGED, save the content separately using template name
                if status == "USER_MANAGED" and content:
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
        else:
            log(f"⚠️ clusterTemplateCrn not found for {name}, skipping template describe.")


        for suffix, label in [
            ("AvailableImages", "Checking available upgrade images"),
            ("RunTimeAvailableImages", "Checking latest runtime image")
        ]:
            command = (
                f"cdp datahub upgrade-cluster --show-available-images --cluster-name {crn}"
                if suffix == "AvailableImages"
                else f"cdp datahub upgrade-cluster --show-latest-available-image-per-runtime --cluster-name {crn}"
            )
            data, err = run_command_json(command, task_name=f"{label} for {name}")
            if data:
                save_to_file(data, cluster_dir / f"{output_prefix}_{suffix}_{timestamp}.json")
            else:
                log(f"⚠️ Skipping {suffix} for {name}")

        db_server, db_err = run_command_json(
            f"cdp datahub describe-database-server --cluster-crn {crn}",
            task_name=f"Describing DB server for {name}"
        )
        if db_server:
            save_to_file(db_server, cluster_dir / f"{output_prefix}_DB_{timestamp}.json")

        else:
            log(f"⚠️ Skipping DB server describe for {name}")

        if all_recipes_set:
            describe_unique_recipes(recipe_dir, all_recipes_set)
        else:
            log(f"ℹ️ No recipes found in cluster: {name}")

    if all_instance_rows:
        save_instance_groups_to_csv(base_dir / f"ALL_{environment_name}_instance_groups.csv", all_instance_rows)

    archive_path = f"{base_dir}.tar.gz"
    shutil.make_archive(str(base_dir), 'gztar', root_dir=base_dir)
    log(f"📦 Archived output to: {archive_path}")
    log(f"🏁 Done. Output saved in: {base_dir}")


if __name__ == "__main__":
    main()