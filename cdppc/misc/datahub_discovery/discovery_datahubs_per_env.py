#!/usr/bin/env python3

import subprocess
import sys
import json
import threading
import itertools
import time
import csv
from datetime import datetime
from pathlib import Path

def log(message):
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def usage():
    print("Usage: python list_and_describe_datahubs.py <environment-name>")
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
    with open(filepath, "w") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, indent=2)
    log(f"✅ Saved: {filepath}")

def get_timestamp():
    return datetime.now().strftime("%Y%m%d%H%M%S")

# === CSV Generation ===
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
                "nodeGroupRole": inst.get("instanceGroup"),  # <-- added field
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

def main():
    if len(sys.argv) != 2:
        usage()

    environment_name = sys.argv[1]
    log(f"🔍 Starting DataHub discovery for environment: {environment_name}")

    base_dir = Path(f"./datahubs_output_{environment_name}_{get_timestamp()}")
    base_dir.mkdir(parents=True, exist_ok=True)

    all_instance_rows = []

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

        timestamp = get_timestamp()

        # Describe Cluster
        describe, describe_err = run_command_json(
            f"cdp datahub describe-cluster --cluster-name {crn}",
            task_name=f"Describing cluster {name}"
        )
        if describe:
            describe_path = base_dir / f"ENVIRONMENT_ENV_{environment_name}_DH_{name}_{timestamp}.json"
            save_to_file(describe, describe_path)

            # InstanceGroups to CSV
            instance_groups = describe.get("cluster", {}).get("instanceGroups", [])
            rows = flatten_instance_groups(name, environment_name, instance_groups, timestamp)
            save_instance_groups_to_csv(base_dir / f"ENVIRONMENT_ENV_{environment_name}_DH_{name}_InstanceGroups_{timestamp}.csv", rows)
            all_instance_rows.extend(rows)

            # Cluster Template
            template_crn = describe.get("cluster", {}).get("clusterTemplateCrn")
            if template_crn:
                template, template_err = run_command_json(
                    f"cdp datahub describe-cluster-template --cluster-template-name {template_crn}",
                    task_name=f"Describing template for {name}"
                )
                if template:
                    cluster_template = template.get("clusterTemplate", {})
                    content_str = cluster_template.get("clusterTemplateContent")

                    try:
                        parsed_content = json.loads(content_str)
                        cluster_template["clusterTemplateContent"] = parsed_content
                    except (TypeError, json.JSONDecodeError):
                        log(f"⚠️ Could not parse clusterTemplateContent for {name}, leaving as-is")

                    template_output_file = base_dir / f"ENVIRONMENT_ENV_{environment_name}_DH_{name}_Template_{timestamp}.json"
                    with open(template_output_file, "w") as f:
                        json.dump({"clusterTemplate": cluster_template}, f, indent=2)
                    log(f"✅ Saved: {template_output_file}")
                else:
                    log(f"⚠️ Skipping template describe for {name} (information not available)")
            else:
                log(f"⚠️ clusterTemplateCrn not found for {name}, skipping template describe.")
        else:
            log(f"⚠️ Skipping full describe for {name} (unable to retrieve cluster details)")
            continue

        # Available Images
        available_images, avail_err = run_command_json(
            f"cdp datahub upgrade-cluster --show-available-images --cluster-name {crn}",
            task_name=f"Checking available upgrade images for {name}"
        )
        if available_images:
            save_to_file(available_images, base_dir / f"ENVIRONMENT_ENV_{environment_name}_DH_{name}_AvailableImages_{timestamp}.json")
        else:
            log(f"⚠️ Skipping available images for {name} (information not available)")

        # Runtime Images
        runtime_images, runtime_err = run_command_json(
            f"cdp datahub upgrade-cluster --show-latest-available-image-per-runtime --cluster-name {crn}",
            task_name=f"Checking latest runtime image for {name}"
        )
        if runtime_images:
            save_to_file(runtime_images, base_dir / f"ENVIRONMENT_ENV_{environment_name}_DH_{name}_RunTimeAvailableImages_{timestamp}.json")
        else:
            log(f"⚠️ Skipping runtime images for {name} (information not available)")

        # DB Server
        db_server, db_err = run_command_json(
            f"cdp datahub describe-database-server --cluster-crn {crn}",
            task_name=f"Describing DB server for {name}"
        )
        if db_server:
            save_to_file(db_server, base_dir / f"ENVIRONMENT_ENV_{environment_name}_DH_{name}_DB_{timestamp}.json")
        else:
            log(f"⚠️ Skipping DB server describe for {name} (information not available)")

    if all_instance_rows:
        aggregate_csv_path = base_dir / f"ALL_ENV_{environment_name}_InstanceGroups_{get_timestamp()}.csv"
        save_instance_groups_to_csv(aggregate_csv_path, all_instance_rows)

    log(f"🏁 Done. Output saved in: {base_dir}")

if __name__ == "__main__":
    main()