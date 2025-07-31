import argparse
import subprocess
import json
import os
import sys
import datetime
import csv
import logging
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # fallback if tqdm is not installed

def setup_logging(debug):
    """
    Set up logging configuration.

    Args:
        debug (bool): If True, set log level to DEBUG, else INFO.
    """
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

def debug_print(debug, msg):
    """
    Print debug messages if debug is enabled.

    Args:
        debug (bool): Whether to print debug messages.
        msg (str): The message to log.
    """
    if debug:
        logging.debug(msg)

def run_cdp_cli(cmd, profile, debug):
    """
    Run a CDP CLI command and return the parsed JSON output.
CHR
    Args:
        cmd (list): List of command arguments for CDP CLI.
        profile (str): CDP CLI profile to use.
        debug (bool): Whether to print debug output.

    Returns:
        dict: Parsed JSON output from the command.

    Raises:
        RuntimeError: If the subprocess fails.
    """
    full_cmd = ["cdp"] + cmd + ["--profile", profile, "--output", "json"]
    debug_print(debug, f"Running command: {' '.join(full_cmd)}")
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, check=True)
        debug_print(debug, f"Command output: {result.stdout}")
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        debug_print(debug, f"Command failed: {e.stderr}")
        logging.error(f"CDP CLI command failed: {e.stderr}")
        raise RuntimeError(f"CDP CLI command failed: {e.stderr}")

def validate_cdp_profile(profile, debug):
    """
    Validate that the given CDP profile can access the control plane.

    Args:
        profile (str): CDP CLI profile to use.
        debug (bool): Whether to print debug output.

    Returns:
        tuple: (True, "") if valid, (False, reason) otherwise.
    """
    try:
        run_cdp_cli(["iam", "list-users"], profile, debug)
        logging.info(f"CDP profile '{profile}' validated successfully.")
        return True, ""
    except Exception as e:
        logging.error(f"CDP profile validation failed: {e}")
        return False, str(e)

def list_datahub_clusters_for_env(environment_name, profile, debug):
    """
    List all DataHub clusters in a given environment.

    Args:
        environment_name (str): Name of the CDP environment.
        profile (str): CDP CLI profile to use.
        debug (bool): Whether to print debug output.

    Returns:
        list: List of cluster dictionaries (with at least clusterName and clusterCrn).
    """
    try:
        resp = run_cdp_cli(
            ["datahub", "list-clusters", "--environment-name", environment_name],
            profile, debug
        )
        clusters = resp.get("clusters", [])
        debug_print(debug, f"Found {len(clusters)} clusters in environment {environment_name}")
        return clusters
    except Exception as e:
        logging.error(f"Failed to list clusters for environment {environment_name}: {e}")
        return []

def get_cluster_details(cluster_id, profile, debug):
    """
    Retrieve detailed information for a DataHub cluster.

    Args:
        cluster_id (str): Cluster name.
        profile (str): CDP CLI profile to use.
        debug (bool): Whether to print debug output.

    Returns:
        dict: Cluster details.

    Raises:
        RuntimeError: If cluster details cannot be retrieved.
    """
    try:
        logging.info(f"Retrieving cluster details for '{cluster_id}'...")
        resp = run_cdp_cli(["datahub", "describe-cluster", "--cluster-name", cluster_id], profile, debug)
        cluster = resp.get("cluster")
        if not cluster:
            raise RuntimeError("No cluster details found in response.")
        logging.info(f"Cluster details retrieved for '{cluster_id}'.")
        return cluster
    except Exception as e:
        logging.error(f"Failed to get cluster details: {e}")
        raise RuntimeError(f"Failed to get cluster details: {e}")

def get_aws_instance_volume_details(instance_id, debug):
    """
    Retrieve detailed volume information for an AWS EC2 instance.

    Args:
        instance_id (str): The EC2 instance ID.
        debug (bool): Whether to print debug output.

    Returns:
        list: List of dictionaries with volume details.
    """
    try:
        # Describe the instance to get root device and block device mappings
        instance_cmd = [
            "aws", "ec2", "describe-instances",
            "--instance-ids", instance_id,
            "--query", "Reservations[].Instances[].[RootDeviceName, BlockDeviceMappings[].{DeviceName:DeviceName, VolumeId:Ebs.VolumeId, DeleteOnTermination:Ebs.DeleteOnTermination, AttachTime:Ebs.AttachTime, Status:Ebs.Status}]",
            "--output", "json"
        ]
        debug_print(debug, f"Running AWS CLI: {' '.join(instance_cmd)}")
        instance_proc = subprocess.run(instance_cmd, capture_output=True, text=True, check=True)
        instance_json = json.loads(instance_proc.stdout)
        if not instance_json or not instance_json[0] or len(instance_json[0]) < 2:
            debug_print(debug, f"Unexpected AWS CLI output for instance details: {instance_proc.stdout}")
            logging.warning(f"Unexpected AWS CLI output for instance {instance_id}")
            return []
        root_device = instance_json[0][0]
        block_device_mappings = instance_json[0][1]
        volume_ids = [bdm.get("VolumeId") for bdm in block_device_mappings if bdm.get("VolumeId")]
        if not volume_ids:
            debug_print(debug, f"No volumes found for instance {instance_id}")
            logging.warning(f"No volumes found for instance {instance_id}")
            return []
        # Describe the volumes to get additional details
        volumes_cmd = [
            "aws", "ec2", "describe-volumes",
            "--volume-ids"
        ] + volume_ids + [
            "--output", "json"
        ]
        debug_print(debug, f"Running AWS CLI: {' '.join(volumes_cmd)}")
        volumes_proc = subprocess.run(volumes_cmd, capture_output=True, text=True, check=True)
        volumes_json = json.loads(volumes_proc.stdout)
        volumes_by_id = {v["VolumeId"]: v for v in volumes_json.get("Volumes", [])}
        result = []
        for bdm in block_device_mappings:
            vol_id = bdm.get("VolumeId")
            if not vol_id or vol_id not in volumes_by_id:
                continue
            vol = volumes_by_id[vol_id]
            result.append({
                "volume_id": vol_id,
                "device_name": bdm.get("DeviceName"),
                "volume_size": vol.get("Size"),
                "volume_state": vol.get("State"),
                "attachment_status": bdm.get("Status"),
                "attachment_time": bdm.get("AttachTime"),
                "encrypted": vol.get("Encrypted"),
                "kms_key_id": vol.get("KmsKeyId") if vol.get("KmsKeyId") else "None",
                "delete_on_termination": bdm.get("DeleteOnTermination"),
                "is_root_disk": "Yes" if bdm.get("DeviceName") == root_device else "No"
            })
        debug_print(debug, f"AWS volume details for {instance_id}: {result}")
        logging.info(f"Retrieved AWS volume details for instance {instance_id}")
        return result
    except subprocess.CalledProcessError as e:
        debug_print(debug, f"Failed to get AWS volume details for {instance_id}: {e.stderr}")
        logging.error(f"Failed to get AWS volume details for {instance_id}: {e.stderr}")
        return []
    except Exception as e:
        debug_print(debug, f"Failed to get AWS volume details for {instance_id}: {e}")
        logging.error(f"Failed to get AWS volume details for {instance_id}: {e}")
        return []

def get_instance_volume_details(instance, cloud_platform, profile, debug):
    """
    Retrieve detailed volume information for an instance, depending on cloud platform.

    Args:
        instance (dict): Instance dictionary.
        cloud_platform (str): Cloud platform name (e.g., "aws").
        profile (str): CDP CLI profile to use.
        debug (bool): Whether to print debug output.

    Returns:
        list: List of dictionaries with volume details.
    """
    instance_id = instance.get("id")
    debug_print(debug, f"Getting detailed volumes for instance {instance_id} on {cloud_platform}")
    if not instance_id:
        logging.warning(f"Instance missing 'id': {instance}")
        return []
    if cloud_platform.lower() == "aws":
        return get_aws_instance_volume_details(instance_id, debug)
    else:
        debug_print(debug, f"Unknown cloud platform {cloud_platform}, using attachedVolumes from cluster response")
        logging.warning(f"Unknown cloud platform {cloud_platform}, using attachedVolumes from cluster response")
        attached = instance.get("attachedVolumes", [])
        result = []
        for vol in attached:
            result.append({
                "volume_id": vol.get("volumeId"),
                "device_name": vol.get("deviceName"),
                "volume_size": vol.get("size"),
                "volume_state": "",
                "attachment_status": "",
                "attachment_time": "",
                "encrypted": "",
                "kms_key_id": "",
                "delete_on_termination": "",
                "is_root_disk": ""
            })
        return result

def write_detailed_csv(data, output_folder, cluster_name, debug):
    """
    Write detailed volume information for all instances in a cluster to a CSV file.

    Args:
        data (dict): Mapping of hostgroup to list of instance dicts (with detailed_volumes).
        output_folder (str): Output directory path.
        cluster_name (str): Name of the cluster.
        debug (bool): Whether to print debug output.
    """
    os.makedirs(output_folder, exist_ok=True)
    timestamp = os.path.basename(output_folder).split('-')[-1]
    csv_path = os.path.join(output_folder, f"{cluster_name}_{timestamp}_volumes.csv")
    debug_print(debug, f"Writing detailed CSV output to {csv_path}")
    logging.info(f"Writing detailed CSV output to {csv_path}")
    with open(csv_path, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "hostgroup",
            "instance_id",
            "instance_state",
            "private_ip",
            "public_ip",
            "volume_id",
            "device_name",
            "volume_size_gib",
            "volume_state",
            "attachment_status",
            "attachment_time",
            "encrypted",
            "kms_key_id",
            "delete_on_termination",
            "is_root_disk"
        ])
        for hostgroup, instances in data.items():
            for inst in instances:
                instance_id = inst.get("id")
                instance_state = inst.get("state")
                private_ip = inst.get("privateIp")
                public_ip = inst.get("publicIp")
                for vol in inst.get("detailed_volumes", []):
                    writer.writerow([
                        hostgroup,
                        instance_id,
                        instance_state,
                        private_ip,
                        public_ip,
                        vol.get("volume_id"),
                        vol.get("device_name"),
                        vol.get("volume_size"),
                        vol.get("volume_state"),
                        vol.get("attachment_status"),
                        vol.get("attachment_time"),
                        vol.get("encrypted"),
                        vol.get("kms_key_id"),
                        vol.get("delete_on_termination"),
                        vol.get("is_root_disk")
                    ])
    logging.info(f"CSV file written: {csv_path}")

def write_instancegroup_json_and_csv(cluster, output_folder, debug):
    """
    Write instance group information to both JSON and CSV files.

    Args:
        cluster (dict): Cluster dictionary containing instanceGroups.
        output_folder (str): Output directory path.
        debug (bool): Whether to print debug output.
    """
    instance_groups = cluster.get("instanceGroups", [])
    json_path = os.path.join(output_folder, "instance_groups.json")
    csv_path = os.path.join(output_folder, "instance_groups.csv")
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(instance_groups, jf, indent=2)
    logging.info(f"Instance group JSON written: {json_path}")

    # Flatten instance group info for CSV
    rows = []
    attached_volumes_fields = set()
    for group in instance_groups:
        group_name = group.get("name", "")
        group_type = group.get("instanceGroupType", "")
        group_state = group.get("state", "")
        for inst in group.get("instances", []):
            attached_vols = inst.get("attachedVolumes", [])
            # Collect all possible keys for attached volume columns
            for vol in attached_vols:
                for k in vol.keys():
                    attached_volumes_fields.add(k)
            rows.append({
                "hostgroup": group_name,
                "instance_group_type": group_type,
                "group_state": group_state,
                "instance_id": inst.get("id"),
                "instance_state": inst.get("state"),
                "private_ip": inst.get("privateIp"),
                "public_ip": inst.get("publicIp"),
                "instance_type": inst.get("instanceType"),
                "attached_volumes": attached_vols  # keep as list for now
            })

    # Prepare CSV fieldnames: flatten attached_volumes fields
    base_fields = [
        "hostgroup", "instance_group_type", "group_state",
        "instance_id", "instance_state", "private_ip", "public_ip", "instance_type"
    ]
    # Sort for stable order
    attached_volumes_fields = sorted(attached_volumes_fields)
    # Determine the maximum number of attached volumes per instance
    max_attached_vols = 0
    for row in rows:
        if isinstance(row["attached_volumes"], list):
            max_attached_vols = max(max_attached_vols, len(row["attached_volumes"]))

    # Build attached volume column names
    attached_vols_columns = []
    for i in range(max_attached_vols):
        for field in attached_volumes_fields:
            attached_vols_columns.append(f"attached_volume_{i}_{field}")

    # Final fieldnames for CSV
    fieldnames = base_fields + attached_vols_columns

    with open(csv_path, "w", newline='', encoding="utf-8") as cf:
        writer = csv.DictWriter(cf, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out_row = {k: row[k] for k in base_fields}
            attached_vols = row["attached_volumes"]
            # Fill attached volume columns for each instance
            for i in range(max_attached_vols):
                if i < len(attached_vols):
                    vol = attached_vols[i]
                    for field in attached_volumes_fields:
                        out_row[f"attached_volume_{i}_{field}"] = vol.get(field, "")
                else:
                    for field in attached_volumes_fields:
                        out_row[f"attached_volume_{i}_{field}"] = ""
            writer.writerow(out_row)
    logging.info(f"Instance group CSV written: {csv_path}")

def write_describe_cluster_json(cluster, output_folder, debug):
    """
    Write the full describe-cluster response to a JSON file.

    Args:
        cluster (dict): Cluster dictionary.
        output_folder (str): Output directory path.
        debug (bool): Whether to print debug output.
    """
    json_path = os.path.join(output_folder, "describe-cluster.json")
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(cluster, jf, indent=2)
    logging.info(f"describe-cluster JSON written: {json_path}")

def main():
    """
    Main entry point for the DataHub instance group and volume validation script.

    Parses command-line arguments, validates the CDP profile, determines clusters to process,
    retrieves cluster and instance details, and writes output files.
    """
    parser = argparse.ArgumentParser(
        description="Validate DataHub instance groups and volumes. Provide --environment-name to process all clusters in an environment, or --cluster-name for specific clusters."
    )
    parser.add_argument("--profile", required=False, default="default", help="CDP CLI profile to use (default: 'default')")
    parser.add_argument("--environment-name", help="CDP environment name to process all DataHub clusters in the environment")
    parser.add_argument("--cluster-name", action="append", help="DataHub cluster name to process (can be specified multiple times)")
    parser.add_argument("--output-folder", default="/tmp/datahub_validations", help="Output folder (default: /tmp/datahub_validations)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    setup_logging(args.debug)

    if not args.environment_name and not args.cluster_name:
        logging.error("You must provide --environment-name or at least one --cluster-name")
        print("Error: You must provide --environment-name or at least one --cluster-name")
        sys.exit(1)

    # If profile is not provided, use 'default'
    profile = args.profile if args.profile else "default"

    valid, reason = validate_cdp_profile(profile, args.debug)
    if not valid:
        logging.error(f"CDP profile '{profile}' is not able to get information from control plane: {reason}")
        print(f"CDP profile '{profile}' is not able to get information from control plane: {reason}")
        sys.exit(2)

    # Determine clusters to process based on arguments
    clusters_to_process = []
    if args.environment_name:
        clusters = list_datahub_clusters_for_env(args.environment_name, profile, args.debug)
        if not clusters:
            logging.error(f"No DataHub clusters found in environment {args.environment_name}")
            print(f"No DataHub clusters found in environment {args.environment_name}")
            sys.exit(3)
        for c in clusters:
            clusters_to_process.append({
                "name": c.get("clusterName")
            })
    if args.cluster_name:
        for name in args.cluster_name:
            clusters_to_process.append({"name": name})

    # Remove duplicate clusters (by name)
    seen = set()
    unique_clusters = []
    for c in clusters_to_process:
        key = c["name"]
        if key and key not in seen:
            seen.add(key)
            unique_clusters.append(c)
    clusters_to_process = unique_clusters

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_output_folder = f"{args.output_folder}-{timestamp}"
    os.makedirs(base_output_folder, exist_ok=True)

    for c in clusters_to_process:
        cluster_id = c["name"]
        try:
            cluster = get_cluster_details(cluster_id, profile, args.debug)
        except Exception as e:
            logging.error(f"Error retrieving cluster details for {cluster_id}: {e}")
            print(f"Error retrieving cluster details for {cluster_id}: {e}")
            continue

        cluster_name = cluster.get("clusterName") or cluster.get("name") or "unknown_cluster"
        cloud_platform = cluster.get("cloudPlatform", "unknown")
        instance_groups = cluster.get("instanceGroups", [])
        output_data = {}

        total_instances = sum(len(group.get("instances", [])) for group in instance_groups)
        logging.info(f"Cluster: {cluster_name} | Cloud: {cloud_platform} | Instance groups: {len(instance_groups)} | Instances: {total_instances}")

        # Create a subfolder for each cluster
        safe_cluster_name = cluster_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        cluster_output_folder = os.path.join(base_output_folder, safe_cluster_name)
        os.makedirs(cluster_output_folder, exist_ok=True)

        # Write describe-cluster.json
        write_describe_cluster_json(cluster, cluster_output_folder, args.debug)

        # Write instanceGroups JSON and CSV
        write_instancegroup_json_and_csv(cluster, cluster_output_folder, args.debug)

        # Prepare detailed volume info for each instance
        use_progress = tqdm is not None and total_instances > 1
        pbar = tqdm(total=total_instances, desc=f"{cluster_name}: Processing instances", unit="instance") if use_progress else None

        try:
            for group in instance_groups:
                hostgroup = group.get("name", "unknown_hostgroup")
                instances = group.get("instances", [])
                output_data[hostgroup] = []
                for instance in instances:
                    logging.info(f"Processing instance {instance.get('id')} in hostgroup {hostgroup}")
                    detailed_volumes = get_instance_volume_details(instance, cloud_platform, profile, args.debug)
                    instance_copy = dict(instance)
                    instance_copy["detailed_volumes"] = detailed_volumes
                    output_data[hostgroup].append(instance_copy)
                    if pbar:
                        pbar.update(1)
            if pbar:
                pbar.close()
        except Exception as e:
            if pbar:
                pbar.close()
            logging.error(f"Error during instance processing for cluster {cluster_name}: {e}")
            print(f"Error during instance processing for cluster {cluster_name}: {e}")
            continue

        # Write detailed CSV (cloud provider volumes)
        write_detailed_csv(output_data, cluster_output_folder, cluster_name, args.debug)
        logging.info(f"Cluster {cluster_name} export complete. Output written to {os.path.abspath(cluster_output_folder)}/")
        print(f"Cluster {cluster_name} export complete. Output written to {os.path.abspath(cluster_output_folder)}/")

if __name__ == "__main__":
    main()
