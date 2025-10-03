#!/usr/bin/env python3

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3


def log(message: str) -> None:
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def get_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def run_command(command: str, debug: bool = False) -> Tuple[Optional[str], Optional[str]]:
    if debug:
        log(f"DEBUG: Running command: {command}")
    try:
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        if debug:
            log(f"DEBUG: Return code: {result.returncode}")
            log(f"DEBUG: STDOUT: {result.stdout.strip()}")
            log(f"DEBUG: STDERR: {result.stderr.strip()}")
        if result.returncode != 0:
            return None, result.stderr.strip()
        return result.stdout.strip(), None
    except Exception as e:
        return None, str(e)


def run_command_json(command: str, debug: bool = False) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    output, error = run_command(command, debug=debug)
    if output:
        try:
            return json.loads(output), None
        except json.JSONDecodeError:
            if debug:
                log(f"DEBUG: Failed to parse JSON. Output was: {output}")
            return None, "Failed to parse JSON response."
    return None, error


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    log(f"✅ Saved: {path}")


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        log(f"⚠️ No rows to write for {path.name}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({k for row in rows for k in row.keys()})
    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    log(f"✅ Saved CSV: {path}")


def save_instance_groups_to_csv(csv_path: Path, rows: List[Dict[str, Any]]) -> None:
    write_csv(csv_path, rows)


def get_cdp_profiles() -> List[str]:
    cred_path = os.path.expanduser("~/.cdp/credentials")
    profiles: List[str] = []
    if not os.path.exists(cred_path):
        return profiles
    with open(cred_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                prof = line[1:-1].strip()
                if prof and not prof.startswith("#"):
                    profiles.append(prof)
    return profiles


def get_region_from_data(obj: Dict[str, Any]) -> Optional[str]:
    for key in ["awsConfiguration", "azureConfiguration", "gcpConfiguration"]:
        cfg = obj.get(key)
        if isinstance(cfg, dict) and key == "awsConfiguration":
            region = cfg.get("region")
            if region:
                return region
    # Try infer from instances' AZ
    for ig in obj.get("instanceGroups", []):
        for inst in ig.get("instances", []):
            az = inst.get("availabilityZone")
            if az and "-" in az:
                return az[:-1]
    return None


def flatten_instance_groups(source_name: str, source_type: str, environment: str, instance_groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for ig in instance_groups:
        ig_name = ig.get("name")
        recipes = ",".join(ig.get("recipes", []))
        for inst in ig.get("instances", []):
            base = {
                "environment": environment,
                "sourceType": source_type,
                "sourceName": source_name,
                "hostgroup": ig_name,
                "recipes": recipes,
                "instanceId": inst.get("id") or inst.get("instanceId"),
                "instanceGroupRole": inst.get("instanceGroup"),
                "state": inst.get("state") or inst.get("instanceStatus"),
                "instanceType": inst.get("instanceType") or inst.get("instanceTypeVal"),
                "instanceVmType": inst.get("instanceVmType"),
                "privateIp": inst.get("privateIp") or inst.get("privateIP"),
                "publicIp": inst.get("publicIp") or inst.get("publicIP"),
                "availabilityZone": inst.get("availabilityZone"),
                "subnetId": inst.get("subnetId"),
            }
            volumes = inst.get("attachedVolumes", [])
            if volumes:
                for vol in volumes:
                    row = dict(base)
                    row.update({
                        "attachedVolume_count": vol.get("count"),
                        "attachedVolume_size": vol.get("size"),
                        "attachedVolume_type": vol.get("volumeType") or vol.get("type"),
                    })
                    rows.append(row)
            else:
                rows.append(base)
    return rows


def collect_cdp_resources(environment_name: str, profile: str, debug: bool, base_dir: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Discover DataHub clusters, Datalakes, and FreeIPA instances. Return flattened rows and a bundle of raw objects.
    """
    bundle: Dict[str, Any] = {"environment": None, "datahubs": [], "datalakes": [], "freeipa": None, "datalake_db_servers": {}}
    rows: List[Dict[str, Any]] = []

    env_cmd = f"cdp environments describe-environment --profile {profile} --environment-name {environment_name}"
    env_json, _ = run_command_json(env_cmd, debug=debug)
    if env_json:
        bundle["environment"] = env_json
        save_json(env_json, base_dir / "environment" / f"ENV_{environment_name}.json")
    else:
        log(f"⚠️ Failed to describe environment {environment_name}")

    # FreeIPA
    freeipa_obj = None
    if env_json:
        env_obj = env_json.get("environment", env_json)
        freeipa_obj = env_obj.get("freeipa") or env_obj.get("freeIpaDetails") or env_obj.get("freeIpa")
    bundle["freeipa"] = freeipa_obj
    if freeipa_obj:
        env_dir = base_dir / "environment"
        freeipa_rows = flatten_instance_groups("freeipa", "FREEIPA", environment_name, [{"name": "freeipa", "instances": freeipa_obj.get("instances", [])}])
        rows.extend(freeipa_rows)
        save_json({"freeipa": freeipa_obj}, env_dir / f"FREEIPA_{environment_name}.json")
        # Write FreeIPA instance groups CSV (per environment) and global CSV
        if freeipa_rows:
            save_instance_groups_to_csv(env_dir / f"FREEIPA_{environment_name}_InstanceGroups.csv", freeipa_rows)
            save_instance_groups_to_csv(base_dir / f"ALL_{environment_name}_freeipa_instance_groups.csv", freeipa_rows)
        # FreeIPA upgrade options
        freeipa_upgrade_cmd = f"cdp environments get-freeipa-upgrade-options --profile {profile} --environment {environment_name}"
        freeipa_upgrade_json, _ = run_command_json(freeipa_upgrade_cmd, debug=debug)
        if freeipa_upgrade_json:
            save_json(freeipa_upgrade_json, env_dir / f"FREEIPA_{environment_name}_UpgradeOptions.json")

    # Datalakes
    datalake_list_cmd = f"cdp datalake list-datalakes --profile {profile} --environment-name {environment_name}"
    datalake_list_json, _ = run_command_json(datalake_list_cmd, debug=debug)
    datalakes = datalake_list_json.get("datalakes", []) if datalake_list_json else []
    if datalakes:
        log(f"🛢️ Found {len(datalakes)} datalake(s)")
    all_datalake_instance_rows: List[Dict[str, Any]] = []
    for dl in datalakes:
        dl_name = dl.get("datalakeName")
        dl_crn = dl.get("crn")
        if not dl_name or not dl_crn:
            continue
        describe_dl_cmd = f"cdp datalake describe-datalake --profile {profile} --datalake-name {dl_crn}"
        describe_dl_json, _ = run_command_json(describe_dl_cmd, debug=debug)
        if not describe_dl_json:
            continue
        bundle["datalakes"].append(describe_dl_json)
        dl_dir = base_dir / "datalake" / dl_name
        save_json(describe_dl_json, dl_dir / f"DL_{dl_name}.json")
        dl_obj = describe_dl_json.get("datalake", describe_dl_json.get("datalakeDetails", describe_dl_json))
        igs = dl_obj.get("instanceGroups", [])
        if not igs:
            for cfg_key in ["awsConfiguration", "azureConfiguration", "gcpConfiguration"]:
                cfg = dl_obj.get(cfg_key, {})
                if isinstance(cfg, dict) and cfg.get("instanceGroups"):
                    igs = cfg.get("instanceGroups", [])
                    break
        dl_rows = flatten_instance_groups(dl_name, "DATALAKE", environment_name, igs)
        rows.extend(dl_rows)
        all_datalake_instance_rows.extend(dl_rows)
        if dl_rows:
            save_instance_groups_to_csv(dl_dir / f"DL_{dl_name}_InstanceGroups.csv", dl_rows)

        # Also fetch Datalake Database Server (RDS) details
        describe_db_cmd = f"cdp datalake describe-database-server --profile {profile} --cluster-crn {dl_crn}"
        describe_db_json, _ = run_command_json(describe_db_cmd, debug=debug)
        if describe_db_json:
            save_json(describe_db_json, dl_dir / f"DL_{dl_name}_DB.json")
            bundle["datalake_db_servers"][dl_name] = describe_db_json
        # Datalake available images (upgrade)
        for suffix, flag in [("AvailableImages", "--show-available-images"), ("RunTimeAvailableImages", "--show-latest-available-image-per-runtime")]:
            upgrade_cmd = f"cdp datalake upgrade-datalake --profile {profile} {flag} --datalake-name {dl_crn}"
            upgrade_json, _ = run_command_json(upgrade_cmd, debug=debug)
            if upgrade_json:
                save_json(upgrade_json, dl_dir / f"DL_{dl_name}_{suffix}.json")

    # DataHubs
    list_dh_cmd = f"cdp datahub list-clusters --profile {profile} --environment-name {environment_name}"
    list_dh_json, _ = run_command_json(list_dh_cmd, debug=debug)
    clusters = list_dh_json.get("clusters", []) if list_dh_json else []
    if clusters:
        log(f"🧩 Found {len(clusters)} DataHub cluster(s)")
    # Pre-fetch COD databases for mapping (internalName -> databaseName)
    cod_lookup: Dict[str, str] = {}
    cod_list_json, _ = run_command_json(
        f"cdp opdb list-databases --profile {profile} --environment-name {environment_name}",
        debug=debug,
    )
    if cod_list_json:
        for db in cod_list_json.get("databases", []):
            internal_name = db.get("internalName")
            database_name = db.get("databaseName")
            if internal_name and database_name:
                cod_lookup[internal_name] = database_name

    all_datahub_instance_rows: List[Dict[str, Any]] = []
    for c in clusters:
        name = c.get("clusterName")
        crn = c.get("crn")
        if not name or not crn:
            continue
        describe_cmd = f"cdp datahub describe-cluster --profile {profile} --cluster-name {crn}"
        describe_json, _ = run_command_json(describe_cmd, debug=debug)
        if not describe_json:
            continue
        bundle["datahubs"].append(describe_json)
        dh_dir = base_dir / "datahubs" / name
        save_json(describe_json, dh_dir / f"DH_{name}.json")
        cluster_obj = describe_json.get("cluster", describe_json)
        igs = cluster_obj.get("instanceGroups", [])
        dh_rows = flatten_instance_groups(name, "DATAHUB", environment_name, igs)
        rows.extend(dh_rows)
        all_datahub_instance_rows.extend(dh_rows)
        if dh_rows:
            save_instance_groups_to_csv(dh_dir / f"DH_{name}_InstanceGroups.csv", dh_rows)
        # DataHub available images
        for suffix, flag in [("AvailableImages", "--show-available-images"), ("RunTimeAvailableImages", "--show-latest-available-image-per-runtime")]:
            up_cmd = (
                f"cdp datahub upgrade-cluster --profile {profile} {flag} --cluster-name {crn}"
            )
            up_json, _ = run_command_json(up_cmd, debug=debug)
            if up_json:
                save_json(up_json, dh_dir / f"DH_{name}_{suffix}.json")
        # COD (OpDB) describe based on DataHub cluster name matching internalName
        if name and name in cod_lookup:
            db_name = cod_lookup[name]
            cod_json, _ = run_command_json(
                f"cdp opdb describe-database --profile {profile} --database-name {db_name} --environment-name {environment_name}",
                debug=debug,
            )
            if cod_json:
                save_json(cod_json, dh_dir / f"DH_{name}_COD_{db_name}.json")

    # Global CSVs for instance groups
    if all_datalake_instance_rows:
        save_instance_groups_to_csv(base_dir / f"ALL_{environment_name}_datalake_instance_groups.csv", all_datalake_instance_rows)
    if all_datahub_instance_rows:
        save_instance_groups_to_csv(base_dir / f"ALL_{environment_name}_datahub_instance_groups.csv", all_datahub_instance_rows)

    # Cloudera AI (ML) Workspaces
    ml_list_cmd = f"cdp ml list-workspaces --profile {profile} --environment-name {environment_name}"
    ml_list_json, _ = run_command_json(ml_list_cmd, debug=debug)
    workspaces = ml_list_json.get("workspaces", []) if ml_list_json else []
    if workspaces:
        log(f"🤖 Found {len(workspaces)} ML workspace(s)")
    for ws in workspaces:
        ws_name = ws.get("workspaceName") or ws.get("name")
        if not ws_name:
            continue
        ws_dir = base_dir / "ml" / ws_name
        describe_ws_cmd = f"cdp ml describe-workspace --profile {profile} --environment-name {environment_name} --workspace-name {ws_name}"
        describe_ws_json, _ = run_command_json(describe_ws_cmd, debug=debug)
        if not describe_ws_json:
            continue
        save_json(describe_ws_json, ws_dir / f"ML_{ws_name}.json")
        ws_obj = describe_ws_json.get("workspace", describe_ws_json)
        igs = ws_obj.get("instanceGroups", [])
        rows.extend(flatten_instance_groups(ws_name, "ML", environment_name, igs))

    # Operational Database (OpDB / COD)
    opdb_list_cmd = f"cdp opdb list-databases --profile {profile} --environment-name {environment_name}"
    opdb_list_json, _ = run_command_json(opdb_list_cmd, debug=debug)
    databases = opdb_list_json.get("databases", []) if opdb_list_json else []
    if databases:
        log(f"🗄️  Found {len(databases)} COD database(s)")
    for db in databases:
        db_name = db.get("databaseName") or db.get("name")
        if not db_name:
            continue
        db_dir = base_dir / "opdb" / db_name
        desc_db_cmd = f"cdp opdb describe-database --profile {profile} --database-name {db_name} --environment-name {environment_name}"
        desc_db_json, _ = run_command_json(desc_db_cmd, debug=debug)
        if not desc_db_json:
            continue
        save_json(desc_db_json, db_dir / f"OPDB_{db_name}.json")
        # Try to extract instances from COD details if present (best-effort)
        # Some responses embed nodes with instance IDs; capture them minimally
        instance_ids = []
        for v in deep_find_values(desc_db_json, ["instanceId", "id", "ec2InstanceId", "vmId"]):
            if isinstance(v, str) and v.startswith("i-"):
                instance_ids.append(v)
        if instance_ids:
            synthetic_igs = [{"name": "cod", "instances": [{"id": iid} for iid in sorted(set(instance_ids))]}]
            rows.extend(flatten_instance_groups(db_name, "OPDB", environment_name, synthetic_igs))

    # Data Engineering (CDE)
    de_list_cmd = f"cdp de list-workspaces --profile {profile} --environment-name {environment_name}"
    de_list_json, _ = run_command_json(de_list_cmd, debug=debug)
    de_workspaces = de_list_json.get("workspaces", []) if de_list_json else []
    if de_workspaces:
        log(f"🧱 Found {len(de_workspaces)} DE workspace(s)")
    for ws in de_workspaces:
        ws_crn = ws.get("crn") or ws.get("workspaceCrn")
        ws_name = ws.get("workspaceName") or ws.get("name") or ws_crn
        if not ws_crn:
            continue
        ws_dir = base_dir / "de" / (ws_name or "workspace")
        save_json(ws, ws_dir / f"DE_{ws_name}_list.json")
        # List virtual clusters in workspace (best-effort)
        de_vc_list_cmd = f"cdp de list-virtual-clusters --profile {profile} --workspace-crn {ws_crn}"
        de_vc_list_json, _ = run_command_json(de_vc_list_cmd, debug=debug)
        virtual_clusters = de_vc_list_json.get("virtualClusters", []) if de_vc_list_json else []
        if virtual_clusters:
            save_json(de_vc_list_json, ws_dir / f"DE_{ws_name}_virtual_clusters.json")
        for vc in virtual_clusters:
            vc_crn = vc.get("crn") or vc.get("clusterCrn")
            vc_name = vc.get("clusterName") or vc.get("name") or vc_crn
            if not vc_crn:
                continue
            de_vc_desc_cmd = f"cdp de describe-virtual-cluster --profile {profile} --cluster-crn {vc_crn}"
            de_vc_desc_json, _ = run_command_json(de_vc_desc_cmd, debug=debug)
            if not de_vc_desc_json:
                continue
            vc_dir = ws_dir / (vc_name or "virtual_cluster")
            save_json(de_vc_desc_json, vc_dir / f"DE_{vc_name}.json")
            # If the response exposes instanceGroups, flatten (best-effort)
            igs = (de_vc_desc_json.get("virtualCluster") or {}).get("instanceGroups", [])
            if igs:
                rows.extend(flatten_instance_groups(vc_name or ws_name, "DE", environment_name, igs))

    # Data Warehouse (DW) - best-effort discovery
    # Try common listings to capture topology; store JSON even if we cannot flatten instances
    dw_base_dir = base_dir / "dw"
    # Database catalogs
    dw_list_dbc_cmd = f"cdp dw list-dbc --profile {profile} --environment-name {environment_name}"
    dw_list_dbc_json, _ = run_command_json(dw_list_dbc_cmd, debug=debug)
    if dw_list_dbc_json:
        save_json(dw_list_dbc_json, dw_base_dir / "DW_database_catalogs.json")
    # Virtual warehouses (naming varies; accommodate common variants)
    for cmd, out_name in [
        (f"cdp dw list-vw --profile {profile} --environment-name {environment_name}", "DW_virtual_warehouses.json"),
        (f"cdp dw list-vws --profile {profile} --environment-name {environment_name}", "DW_virtual_warehouses_alt.json"),
    ]:
        dw_list_vw_json, _ = run_command_json(cmd, debug=debug)
        if dw_list_vw_json:
            save_json(dw_list_vw_json, dw_base_dir / out_name)

    # DataFlow (CDF PC) - best-effort discovery
    df_base_dir = base_dir / "dataflow"
    df_envs_cmd = f"cdp df list-environments --profile {profile}"
    df_envs_json, _ = run_command_json(df_envs_cmd, debug=debug)
    if df_envs_json:
        save_json(df_envs_json, df_base_dir / "DF_environments.json")
        # Try to list deployments per environment when possible
        envs = df_envs_json.get("environments", []) if isinstance(df_envs_json, dict) else []
        for env in envs:
            env_crn = env.get("crn") or env.get("environmentCrn")
            if not env_crn:
                continue
            df_deploy_cmd = f"cdp df list-deployments --profile {profile} --environment-crn {env_crn}"
            df_deploy_json, _ = run_command_json(df_deploy_cmd, debug=debug)
            if df_deploy_json:
                save_json(df_deploy_json, df_base_dir / f"DF_deployments_{env_crn.replace(':', '_')}.json")

    return rows, bundle


def enrich_with_rds(rds_identifiers_by_region: Dict[str, List[str]], debug: bool = False) -> List[Dict[str, Any]]:
    """
    Describe RDS instances for the provided identifiers, grouped by region.
    Returns a list of RDS instance rows.
    """
    all_rds_rows: List[Dict[str, Any]] = []

    for region, rds_ids in rds_identifiers_by_region.items():
        ids = [rid for rid in rds_ids if rid]
        if not ids:
            continue
        if debug:
            log(f"DEBUG: Describing {len(ids)} RDS instance(s) in {region}")
        
        try:
            rds = boto3.client("rds", region_name=region)
            
            # Describe RDS instances individually (AWS API doesn't accept list)
            for rds_id in ids:
                try:
                    response = rds.describe_db_instances(DBInstanceIdentifier=rds_id)
                    db_instance = response.get("DBInstances", [])[0] if response.get("DBInstances") else None
                    
                    if db_instance:
                        # Extract Cloudera-Resource-Name tag
                        cloudera_resource_name = None
                        if 'TagList' in db_instance:
                            for tag in db_instance['TagList']:
                                if tag['Key'] == 'Cloudera-Resource-Name':
                                    cloudera_resource_name = tag['Value']
                                    break
                        
                        all_rds_rows.append({
                            "region": region,
                            "dbInstanceIdentifier": db_instance.get("DBInstanceIdentifier"),
                            "dbInstanceClass": db_instance.get("DBInstanceClass"),
                            "engine": db_instance.get("Engine"),
                            "engineVersion": db_instance.get("EngineVersion"),
                            "allocatedStorage": db_instance.get("AllocatedStorage"),
                            "storageType": db_instance.get("StorageType"),
                            "multiAZ": db_instance.get("MultiAZ"),
                            "publiclyAccessible": db_instance.get("PubliclyAccessible"),
                            "dbInstanceStatus": db_instance.get("DBInstanceStatus"),
                            "masterUsername": db_instance.get("MasterUsername"),
                            "dbName": db_instance.get("DBName"),
                            "vpcSecurityGroups": [sg["VpcSecurityGroupId"] for sg in db_instance.get("VpcSecurityGroups", [])],
                            "dbSubnetGroup": db_instance.get("DBSubnetGroup", {}).get("DBSubnetGroupName"),
                            "availabilityZone": db_instance.get("AvailabilityZone"),
                            "backupRetentionPeriod": db_instance.get("BackupRetentionPeriod"),
                            "preferredBackupWindow": db_instance.get("PreferredBackupWindow"),
                            "preferredMaintenanceWindow": db_instance.get("PreferredMaintenanceWindow"),
                            "clouderaResourceName": cloudera_resource_name,
                            "endpoint": db_instance.get("Endpoint", {}).get("Address"),
                            "port": db_instance.get("Endpoint", {}).get("Port"),
                        })
                except Exception as e:
                    if debug:
                        log(f"DEBUG: Failed to describe RDS instance {rds_id}: {e}")
                    continue
        except Exception as e:
            log(f"⚠️ Failed RDS describe in {region}: {e}")

    return all_rds_rows


def enrich_with_ec2(instance_ids_by_region: Dict[str, List[str]], debug: bool = False) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Describe EC2 instances and EBS volumes for the provided instance IDs, grouped by region.
    Returns two lists: ec2_instance_rows and ebs_volume_rows.
    """
    all_instance_rows: List[Dict[str, Any]] = []
    all_volume_rows: List[Dict[str, Any]] = []

    for region, instance_ids in instance_ids_by_region.items():
        ids = [iid for iid in instance_ids if iid]
        if not ids:
            continue
        if debug:
            log(f"DEBUG: Describing {len(ids)} instance(s) in {region}")
        ec2 = boto3.client("ec2", region_name=region)

        # Describe instances
        try:
            paginator = ec2.get_paginator("describe_instances")
            pages = paginator.paginate(InstanceIds=ids)
            instance_map: Dict[str, Dict[str, Any]] = {}
            for page in pages:
                for reservation in page.get("Reservations", []):
                    for inst in reservation.get("Instances", []):
                        instance_map[inst["InstanceId"]] = inst
            for iid, inst in instance_map.items():
                tags = {t.get("Key"): t.get("Value") for t in inst.get("Tags", [])}
                all_instance_rows.append({
                    "region": region,
                    "instanceId": iid,
                    "instanceType": inst.get("InstanceType"),
                    "state": (inst.get("State") or {}).get("Name"),
                    "launchTime": inst.get("LaunchTime").isoformat() if inst.get("LaunchTime") else None,
                    "privateIp": inst.get("PrivateIpAddress"),
                    "publicIp": inst.get("PublicIpAddress"),
                    "availabilityZone": (inst.get("Placement") or {}).get("AvailabilityZone"),
                    "subnetId": inst.get("SubnetId"),
                    "vpcId": inst.get("VpcId"),
                    "arch": inst.get("Architecture"),
                    "iamInstanceProfile": (inst.get("IamInstanceProfile") or {}).get("Arn"),
                    "keyName": inst.get("KeyName"),
                    "clouderaResourceName": tags.get("Cloudera-Resource-Name"),
                    "nameTag": tags.get("Name"),
                })

            # Collect all volume IDs from block device mappings
            volume_ids: List[str] = []
            for inst in instance_map.values():
                for bdm in inst.get("BlockDeviceMappings", []):
                    ebs = bdm.get("Ebs")
                    if ebs and ebs.get("VolumeId"):
                        volume_ids.append(ebs["VolumeId"])

            if volume_ids:
                vol_pages = ec2.get_paginator("describe_volumes").paginate(VolumeIds=volume_ids)
                for vpage in vol_pages:
                    for vol in vpage.get("Volumes", []):
                        attachments = vol.get("Attachments", [])
                        attached_instance = attachments[0].get("InstanceId") if attachments else None
                        all_volume_rows.append({
                            "region": region,
                            "volumeId": vol.get("VolumeId"),
                            "sizeGiB": vol.get("Size"),
                            "volumeType": vol.get("VolumeType"),
                            "iops": vol.get("Iops"),
                            "throughput": vol.get("Throughput"),
                            "encrypted": vol.get("Encrypted"),
                            "kmsKeyId": vol.get("KmsKeyId"),
                            "state": vol.get("State"),
                            "createTime": vol.get("CreateTime").isoformat() if vol.get("CreateTime") else None,
                            "availabilityZone": vol.get("AvailabilityZone"),
                            "attachedInstanceId": attached_instance,
                        })
        except Exception as e:
            log(f"⚠️ Failed EC2/Volumes describe in {region}: {e}")

    return all_instance_rows, all_volume_rows


def get_cost_explorer_client() -> Any:
    # Cost Explorer is in us-east-1 for most accounts
    return boto3.client("ce", region_name="us-east-1")


def ce_date(date: datetime) -> str:
    return date.strftime("%Y-%m-%d")


def fetch_costs_for_ec2_and_ebs(
    ce_client: Any,
    region: str,
    start_date: datetime,
    end_date: datetime,
    cloudera_resource_name: Optional[str],
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Query AWS Cost Explorer for EC2 compute and EBS storage costs for a region.
    Optionally filter by Cloudera-Resource-Name tag if provided.
    """
    start = ce_date(start_date)
    end = ce_date(end_date)

    def build_filter(service: str) -> Dict[str, Any]:
        flt: Dict[str, Any] = {
            "And": [
                {"Dimensions": {"Key": "SERVICE", "Values": [service]}},
                {"Dimensions": {"Key": "REGION", "Values": [region]}},
            ]
        }
        if cloudera_resource_name:
            flt["And"].append({"Tags": {"Key": "Cloudera-Resource-Name", "Values": [cloudera_resource_name]}})
        return flt

    results: Dict[str, Any] = {"ec2_daily": [], "ebs_daily": []}

    for service, key in [
        ("Amazon Elastic Compute Cloud - Compute", "ec2_daily"),
        ("Amazon Elastic Block Store", "ebs_daily"),
    ]:
        try:
            if debug:
                log(f"DEBUG: Querying CE for {service} in {region} [{start}..{end}] tag={cloudera_resource_name or 'NONE'}")
            resp = ce_client.get_cost_and_usage(
                TimePeriod={"Start": start, "End": end},
                Granularity="DAILY",
                Metrics=["UnblendedCost", "BlendedCost", "AmortizedCost", "UsageQuantity"],
                GroupBy=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}],
                Filter=build_filter(service),
            )
            results[key] = resp.get("ResultsByTime", [])
        except Exception as e:
            log(f"⚠️ CE query failed for {service} in {region}: {e}")
            results[key] = []

    return results


def summarize_daily_costs(daily: List[Dict[str, Any]]) -> Tuple[float, List[Dict[str, Any]]]:
    total = 0.0
    rows: List[Dict[str, Any]] = []
    for day in daily:
        date_str = day.get("TimePeriod", {}).get("Start")
        day_total = 0.0
        for grp in day.get("Groups", []):
            amt = float(grp.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", 0) or 0)
            day_total += amt
        total += day_total
        rows.append({"date": date_str, "unblended": round(day_total, 6)})
    return total, rows


def fetch_costs_for_rds(
    ce_client: Any,
    region: str,
    start_date: datetime,
    end_date: datetime,
    cloudera_resource_name: Optional[str],
    debug: bool = False,
) -> Dict[str, Any]:
    start = ce_date(start_date)
    end = ce_date(end_date)

    flt: Dict[str, Any] = {
        "And": [
            {"Dimensions": {"Key": "SERVICE", "Values": ["Amazon Relational Database Service"]}},
            {"Dimensions": {"Key": "REGION", "Values": [region]}},
        ]
    }
    if cloudera_resource_name:
        flt["And"].append({"Tags": {"Key": "Cloudera-Resource-Name", "Values": [cloudera_resource_name]}})

    try:
        if debug:
            log(f"DEBUG: Querying CE for RDS in {region} [{start}..{end}] tag={cloudera_resource_name or 'NONE'}")
        resp = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity="DAILY",
            Metrics=["UnblendedCost", "BlendedCost", "AmortizedCost", "UsageQuantity"],
            GroupBy=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}],
            Filter=flt,
        )
        return {"rds_daily": resp.get("ResultsByTime", [])}
    except Exception as e:
        log(f"⚠️ CE query failed for RDS in {region}: {e}")
        return {"rds_daily": []}


def deep_find_values(obj: Any, keys: List[str]) -> List[Any]:
    found: List[Any] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and v is not None:
                found.append(v)
            found.extend(deep_find_values(v, keys))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(deep_find_values(item, keys))
    return found


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Discover all CDP environment resources (DataHub, Datalake, FreeIPA), "
            "enrich with AWS EC2/EBS metadata, and fetch EC2/EBS costs via Cost Explorer."
        )
    )
    parser.add_argument("--environment-name", required=True, help="CDP environment name")
    parser.add_argument("--profile", default="default", help="CDP CLI profile (default: default)")
    parser.add_argument("--output-dir", help="Output directory (default: /tmp/cldr_discovery-<ts>)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--cost-days",
        type=int,
        default=30,
        help="Number of days back for Cost Explorer window (default: 30)",
    )
    args = parser.parse_args()

    profiles = get_cdp_profiles()
    if not profiles:
        log("⚠️ No CDP CLI profiles found in ~/.cdp/credentials")
        sys.exit(1)
    if args.profile not in profiles:
        log(f"⚠️ Profile '{args.profile}' not found. Available: {profiles}")
        sys.exit(1)

    timestamp = get_timestamp()
    base_dir = Path(args.output_dir.rstrip("/")) if args.output_dir else Path(f"/tmp/cldr_discovery-{timestamp}")
    if args.output_dir and not base_dir.name.endswith(timestamp):
        base_dir = Path(f"{base_dir}-{timestamp}")
    base_dir.mkdir(parents=True, exist_ok=True)

    log(f"🔍 Starting discovery for environment: {args.environment_name} (profile: {args.profile})")

    # Discover CDP resources
    rows, bundle = collect_cdp_resources(args.environment_name, args.profile, args.debug, base_dir)
    write_csv(base_dir / "flattened" / "cdp_instances_flat.csv", rows)
    save_json({"summary": {"counts": len(rows)}}, base_dir / "flattened" / "_summary.json")

    # Build region to instanceIds map
    ids_by_region: Dict[str, List[str]] = defaultdict(list)
    # Try to infer region per row
    for r in rows:
        iid = r.get("instanceId")
        if not iid:
            continue
        region = None
        # Try from AZ first
        az = r.get("availabilityZone")
        if az and "-" in az:
            region = az[:-1]
        # If missing, try from described objects
        if not region:
            # Use environment's region if AWS
            env_obj = (bundle.get("environment") or {}).get("environment", {})
            region = get_region_from_data(env_obj) or region
        if not region:
            # fallback: leave ungrouped
            continue
        ids_by_region[region].append(iid)

    # Extract RDS identifiers from database server descriptions
    rds_ids_by_region: Dict[str, List[str]] = defaultdict(list)
    
    # Define possible RDS identifier field names
    possible_fields = [
        "rdsInstanceId", "dbInstanceIdentifier", "databaseServerId", "serverId",
        "instanceId", "id", "dbInstanceId", "rdsId", "databaseId"
    ]
    
    # From datalake database servers
    for dl_name, db_json in (bundle.get("datalake_db_servers") or {}).items():
        # Extract RDS identifier from host field (pattern: dbsvr-{uuid}.{random}.{region}.rds.amazonaws.com)
        rds_id = None
        host = db_json.get("host", "")
        
        if host and "dbsvr-" in host:
            # Extract the dbsvr-{uuid} part
            rds_id = host.split(".")[0]  # Gets "dbsvr-bc83135d-2614-40d4-923f-478bdab830f5"
        else:
            # Fallback to comprehensive field search if host pattern not found
            search_paths = [
                db_json,
                db_json.get("databaseServer", {}),
                db_json.get("databaseServerDetails", {}),
                db_json.get("server", {}),
                db_json.get("rds", {}),
            ]
            
            for search_obj in search_paths:
                if not isinstance(search_obj, dict):
                    continue
                for field in possible_fields:
                    if field in search_obj and search_obj[field]:
                        rds_id = str(search_obj[field])
                        break
                if rds_id:
                    break
            
            # If still not found, use deep search
            if not rds_id:
                found_values = deep_find_values(db_json, possible_fields)
                for val in found_values:
                    if isinstance(val, str) and (val.startswith("dbsvr-") or val.startswith("db-") or "rds" in val.lower()):
                        rds_id = val
                        break
        
        if rds_id:
            # Try to determine region from host or datalake
            region = None
            if host and "." in host:
                # Extract region from hostname (e.g., us-east-1.rds.amazonaws.com)
                parts = host.split(".")
                for part in parts:
                    if part.startswith("us-") or part.startswith("eu-") or part.startswith("ap-") or part.startswith("ca-") or part.startswith("sa-"):
                        region = part
                        break
            
            if not region:
                for dl_json in (bundle.get("datalakes") or []):
                    if (dl_json.get("datalake", {}).get("datalakeName") or 
                        dl_json.get("datalakeDetails", {}).get("datalakeName")) == dl_name:
                        region = get_region_from_data(dl_json.get("datalake", dl_json.get("datalakeDetails", dl_json)))
                        break
            if not region:
                # Fallback to environment region
                env_obj = (bundle.get("environment") or {}).get("environment", {})
                region = get_region_from_data(env_obj)
            
            if region:
                rds_ids_by_region[region].append(rds_id)
                log(f"Found RDS for datalake {dl_name}: {rds_id} in {region}")
    
    # From DataHub COD database servers - need to describe database server for COD clusters
    for dh_json in (bundle.get("datahubs") or []):
        cluster_obj = dh_json.get("cluster", dh_json)
        cluster_name = cluster_obj.get("clusterName")
        cluster_crn = cluster_obj.get("crn")
        if cluster_name and cluster_name.startswith("cod-") and cluster_crn:
            # Describe the database server for this COD cluster
            describe_db_cmd = f"cdp datahub describe-database-server --profile {args.profile} --cluster-crn {cluster_crn}"
            describe_db_json, _ = run_command_json(describe_db_cmd, debug=args.debug)
            if describe_db_json:
                # Extract RDS identifier from host field (pattern: dbsvr-{uuid}.{random}.{region}.rds.amazonaws.com)
                host = describe_db_json.get("host", "")
                if host and "dbsvr-" in host:
                    # Extract the dbsvr-{uuid} part
                    rds_id = host.split(".")[0]  # Gets "dbsvr-bc83135d-2614-40d4-923f-478bdab830f5"
                    
                    # Determine region from host or cluster
                    region = None
                    if "." in host:
                        # Extract region from hostname (e.g., us-east-1.rds.amazonaws.com)
                        parts = host.split(".")
                        for part in parts:
                            if part.startswith("us-") or part.startswith("eu-") or part.startswith("ap-") or part.startswith("ca-") or part.startswith("sa-"):
                                region = part
                                break
                    
                    if not region:
                        region = get_region_from_data(cluster_obj)
                    
                    if region and rds_id:
                        rds_ids_by_region[region].append(rds_id)
                        log(f"Found RDS for COD cluster {cluster_name}: {rds_id} in {region}")
                        
                        # Save the database server description
                        dh_dir = base_dir / "datahubs" / cluster_name
                        save_json(describe_db_json, dh_dir / f"DH_{cluster_name}_DB.json")

    # Enrich with EC2 + EBS
    ec2_rows, ebs_rows = enrich_with_ec2(ids_by_region, debug=args.debug)
    write_csv(base_dir / "aws" / "ec2_instances.csv", ec2_rows)
    write_csv(base_dir / "aws" / "ebs_volumes.csv", ebs_rows)
    
    # Enrich with RDS
    rds_rows = enrich_with_rds(rds_ids_by_region, debug=args.debug)
    write_csv(base_dir / "aws" / "rds_instances.csv", rds_rows)

    # Cost Explorer per region and (if possible) per Cloudera-Resource-Name tag
    ce = get_cost_explorer_client()
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=max(args.cost_days, 1))
    end_dt = datetime(end_date.year, end_date.month, end_date.day)
    start_dt = datetime(start_date.year, start_date.month, start_date.day)

    # Determine unique regions and tags from EC2 and RDS rows
    crn_tags_by_region: Dict[str, List[Optional[str]]] = defaultdict(list)
    for row in ec2_rows:
        crn_tag = row.get("clouderaResourceName")
        region = row.get("region")
        if region:
            # Deduplicate later
            crn_tags_by_region[region].append(crn_tag)
    
    # Also collect tags from RDS rows
    for row in rds_rows:
        crn_tag = row.get("clouderaResourceName")
        region = row.get("region")
        if region:
            crn_tags_by_region[region].append(crn_tag)

    # Also include RDS identifiers and regions if present from datalake DB servers and any discovered JSON
    rds_regions: Dict[str, List[Optional[str]]] = defaultdict(list)
    # Try infer region(s) from datalake describe content
    for dl_json in (bundle.get("datalakes") or []):
        dl_obj = dl_json.get("datalake", dl_json.get("datalakeDetails", dl_json))
        reg = get_region_from_data(dl_obj)
        if reg:
            rds_regions[reg].append(None)
    # Prefer explicit DB server describe output
    for dl_name, db_json in (bundle.get("datalake_db_servers") or {}).items():
        # best-effort: look for region, arn, or endpoint fields
        values = deep_find_values(db_json, ["region", "awsRegion", "endpoint", "rdsInstanceId", "dbInstanceIdentifier"])
        reg = None
        for v in values:
            if isinstance(v, str) and v.startswith("us-"):
                reg = v
                break
        if not reg:
            # fallback: use datalake region discovered above
            for dl_json in (bundle.get("datalakes") or []):
                if (dl_json.get("datalake", {}).get("datalakeName") or dl_json.get("datalakeDetails", {}).get("datalakeName")) == dl_name:
                    reg = get_region_from_data(dl_json.get("datalake", dl_json.get("datalakeDetails", dl_json)))
                    break
        if reg:
            rds_regions[reg].append(None)

    # Execute CE queries and write results
    cost_summary_rows: List[Dict[str, Any]] = []
    for region, tags in crn_tags_by_region.items():
        unique_tags = list({t for t in tags if t}) or [None]
        for tag in unique_tags:
            ce_results = fetch_costs_for_ec2_and_ebs(ce, region, start_dt, end_dt, tag, debug=args.debug)
            ec2_total, ec2_daily_rows = summarize_daily_costs(ce_results.get("ec2_daily", []))
            ebs_total, ebs_daily_rows = summarize_daily_costs(ce_results.get("ebs_daily", []))

            tag_suffix = tag or "UNSCOPED"
            write_csv(base_dir / "costs" / region / f"ec2_daily_{tag_suffix}.csv", ec2_daily_rows)
            write_csv(base_dir / "costs" / region / f"ebs_daily_{tag_suffix}.csv", ebs_daily_rows)

            cost_summary_rows.append({
                "region": region,
                "tag_ClouderaResourceName": tag or "",
                "ec2_unblended_total": round(ec2_total, 6),
                "ebs_unblended_total": round(ebs_total, 6),
                "rds_unblended_total": 0.0,  # Will be updated below
                "window_start": ce_date(start_dt),
                "window_end": ce_date(end_dt),
            })

    # RDS cost queries per region (integrate with existing cost summary)
    for region, tags in crn_tags_by_region.items():
        unique_tags = list({t for t in tags if t}) or [None]
        for tag in unique_tags:
            rds_results = fetch_costs_for_rds(ce, region, start_dt, end_dt, tag, debug=args.debug)
            rds_total, rds_daily_rows = summarize_daily_costs(rds_results.get("rds_daily", []))
            tag_suffix = tag or "UNSCOPED"
            write_csv(base_dir / "costs" / region / f"rds_daily_{tag_suffix}.csv", rds_daily_rows)
            
            # Update existing cost summary row with RDS costs
            for summary_row in cost_summary_rows:
                if (summary_row["region"] == region and 
                    summary_row["tag_ClouderaResourceName"] == (tag or "")):
                    summary_row["rds_unblended_total"] = round(rds_total, 6)
                    break
            else:
                # If no existing row found, create new one
                cost_summary_rows.append({
                    "region": region,
                    "tag_ClouderaResourceName": tag or "",
                    "ec2_unblended_total": 0.0,
                    "ebs_unblended_total": 0.0,
                    "rds_unblended_total": round(rds_total, 6),
                    "window_start": ce_date(start_dt),
                    "window_end": ce_date(end_dt),
                })

    write_csv(base_dir / "costs" / "summary.csv", cost_summary_rows)

    # Archive output
    archive_path = f"{base_dir}.tar.gz"
    shutil.make_archive(str(base_dir), "gztar", root_dir=base_dir)
    log(f"📦 Archived output to: {archive_path}")
    log(f"🏁 Done. Output saved in: {base_dir}")


if __name__ == "__main__":
    main()


