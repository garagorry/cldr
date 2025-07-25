import json
import re
import subprocess
import sys
from pathlib import Path

# Add tqdm for progress bar
try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

# NOTE: This script requires the Beta CDP CLI (cdpcli-beta) to be installed.
# See "Installing Beta CDP CLI" documentation for installation instructions.

# Regular expression to match valid input JSON filenames
FILENAME_REGEX = re.compile(r'ENVIRONMENT_ENV_.*_DH_.*_\d{14}\.json$')

# Patterns to exclude from processing
EXCLUDE_PATTERNS = [
    'AvailableImages',
    'DB',
    'RunTimeAvailableImages',
    'Template',
    '.csv',
    'recipes'
]

# Base custom tags for the request template (the "dhname" tag is set dynamically per file)
BASE_CUSTOM_TAGS = {
    "tech-team-email": "dummy@example.com",
    "map-migrated": "d-server-00000",
    "SREMetrics": "true",
    "owner-team-email": "dummy@example.com",
    "appliance_exception": "cloudera",
    "ebs_data_classification": "Interna",
    "GoldenImage_Exception": "true",
    "ctrl_dlcore_type": "datalake",
    "dh-vocation": "engineering",
    "ebs_data_retention": "1825",
    "/Tags/sigla": "NG2",
    "/Tags/squad": "Big Data Support Squad",
    "AlertCloud": "custom",
    "ctrl_dlcore": "NG2",
    "LoadBalancerType": "VPCLink"
}

def extract_instance_group_details(group):
    instances = group.get("instances", [])
    first_instance = instances[0] if instances else {}
    default_instance_type = "m6i.4xlarge"
    root_volume_size = 200  # Default root volume size in GB

    attached_volumes_raw = first_instance.get("attachedVolumes", [])
    attached_volumes = []
    if attached_volumes_raw:
        for v in attached_volumes_raw:
            raw_type = v.get("volumeType", "gp3")
            volume_type = "gp3" if raw_type == "gp2" else raw_type
            attached_volumes.append({
                "size": v.get("size", 256),
                "count": v.get("count", 2),
                "type": volume_type
            })
    else:
        attached_volumes = [{
            "size": 256,
            "count": 2,
            "type": "gp3"
        }]

    return {
        "name": group.get("name", "null"),
        "nodeCount": len(instances) if instances else 0,
        "type": (
            "GATEWAY" if first_instance.get("instanceType") in ["GATEWAY", "GATEWAY_PRIMARY"]
            else "CORE"
        ),
        "recoveryMode": "MANUAL",
        "minimumNodeCount": 0,
        "scalabilityOption": "ALLOWED",
        "template": {
            "aws": {
                "encryption": {
                    "type": "DEFAULT",
                    "key": None
                },
                "placementGroup": {
                    "strategy": "PARTITION"
                }
            },
            "instanceType": first_instance.get("instanceVmType", default_instance_type),
            "rootVolume": {
                "size": root_volume_size
            },
            "attachedVolumes": attached_volumes,
            "cloudPlatform": "AWS"
        },
        "recipeNames": group.get("recipes", []),
        "subnetIds": group.get("subnetIds", []),
        "availabilityZones": group.get("availabilityZones", [])
    }

def run_cdp_command(command_args):
    try:
        result = subprocess.run(
            command_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            encoding="utf-8"
        )
        return json.loads(result.stdout)
    except Exception as e:
        print(f"[ERROR] Failed to run command: {' '.join(command_args)}\n{e}")
        return None

def get_bucket_name_from_datalake_crn(datalake_crn):
    if not datalake_crn:
        return None
    for arg in ["--datalake-name", "--datalake-crn"]:
        command = [
            "cdp", "datalake", "describe-datalake", arg, datalake_crn
        ]
        data = run_cdp_command(command)
        if data and "datalake" in data:
            location = data["datalake"].get("cloudStorageBaseLocation")
            if location and location.startswith("s3a://"):
                bucket = location[6:].split("/", 1)[0]
                return bucket
    return None

def convert_describe_to_distrox_request(cluster_data, bucket_name=None):
    cluster = cluster_data["cluster"]
    cluster_name = cluster.get("clusterName")

    instance_groups = [
        extract_instance_group_details(g)
        for g in cluster.get("instanceGroups", [])
    ]

    tags = BASE_CUSTOM_TAGS.copy()
    tags["dhname"] = cluster_name

    if not bucket_name:
        datalake_crn = cluster.get("datalakeCrn")
        bucket_name = get_bucket_name_from_datalake_crn(datalake_crn)
        if not bucket_name:
            bucket_name = "customer-bucket-name"

    template = {
        "environmentName": cluster["environmentName"],
        "name": cluster["clusterName"],
        "instanceGroups": instance_groups,
        "image": {
            "id": cluster["imageDetails"]["id"],
            "catalog": cluster["imageDetails"].get("catalogName", "cdp-default")
        },
        "network": {
            "subnetId": instance_groups[0].get("subnetIds", [None])[0],
            "networkId": None
        },
        "cluster": {
            "databases": [],
            "cloudStorage": {
                "locations": [
                    {
                        "type": "YARN_LOG",
                        "value": f"s3a://{bucket_name}/datalake/oplogs/yarn-app-logs"
                    },
                    {
                        "type": "ZEPPELIN_NOTEBOOK",
                        "value": f"s3a://{bucket_name}/datalake/{cluster_name}/zeppelin/notebook"
                    }
                ]
            },
            "exposedServices": ["ALL"],
            "blueprintName": cluster.get("workloadType", "<unknown>"),
            "validateBlueprint": False
        },
        "externalDatabase": {
            "availabilityType": "HA"
        },
        "tags": {
            "application": None,
            "userDefined": tags,
            "defaults": None
        },
        "inputs": {
            "ynlogd.dirs": "/hadoopfs/fs1/nodemanager/log,/hadoopfs/fs2/nodemanager/log",
            "ynld.dirs": "/hadoopfs/fs1/nodemanager,/hadoopfs/fs2/nodemanager",
            "dfs.dirs": "/hadoopfs/fs3/datanode,/hadoopfs/fs4/datanode",
            "query_data_hive_path": f"s3a://{bucket_name}/warehouse/tablespace/external/{cluster_name}/hive/sys.db/query_data",
            "query_data_tez_path": f"s3a://{bucket_name}/warehouse/tablespace/external/{cluster_name}/hive/sys.db"
        },
        "gatewayPort": None,
        "enableLoadBalancer": True,
        "variant": "CDP",
        "javaVersion": 8,
        "enableMultiAz": cluster.get("multiAz", False),
        "architecture": "x86_64",
        "disableDbSslEnforcement": False,
        "security": cluster.get("security", {})
    }

    return template

def should_include_file(file_path: Path) -> bool:
    name = file_path.name
    if not FILENAME_REGEX.match(name):
        return False
    return not any(exclude in name for exclude in EXCLUDE_PATTERNS)

def find_input_files(start_dir="."):
    return [p for p in Path(start_dir).rglob("*.json") if should_include_file(p)]

def process_json_files(bucket_name_arg=None, input_dir=".", output_dir=None):
    """
    Processes all valid input JSON files in the specified directory tree,
    converts them to DistroX request templates, and writes the output
    to the output_dir directory.

    Args:
        bucket_name_arg (str or None): If provided, use this bucket name for all templates.
        input_dir (str or Path): Directory to search for input JSON files. Defaults to current directory.
        output_dir (str or Path or None): Directory to write output templates. If None, uses input_dir/distrox_templates.
    """
    input_files = find_input_files(input_dir)
    if output_dir is None:
        output_dir = Path(input_dir) / "distrox_templates"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    if not input_files:
        print("[INFO] No input files found to process.")
        return

    use_progress = tqdm is not None
    iterator = input_files
    created_templates = []

    if use_progress:
        iterator = tqdm(input_files, desc="Creating request templates", unit="template", dynamic_ncols=True)

    for json_file in iterator:
        output_file = output_dir / f"{json_file.stem}_distrox_template.json"
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
                request_template = convert_describe_to_distrox_request(data, bucket_name=bucket_name_arg)
                with open(output_file, "w") as out:
                    json.dump(request_template, out, indent=2)
            created_templates.append(str(output_file))
            if use_progress:
                # Show the file being created in the progress bar
                iterator.set_postfix_str(f"{output_file}", refresh=False)
            else:
                print(f"[OK] Created template: {output_file}")
        except Exception as e:
            if use_progress:
                tqdm.write(f"[ERROR] Failed to process {json_file}: {e}")
            else:
                print(f"[ERROR] Failed to process {json_file}: {e}")

    if use_progress:
        tqdm.write("")  # blank line after progress bar
        for t in created_templates:
            tqdm.write(f"[OK] Created template: {t}")
        tqdm.write("[INFO] All files processed.")
    else:
        if created_templates:
            for t in created_templates:
                print(f"[OK] Created template: {t}")

def print_usage():
    print("Usage: python dh_generate_distrox_request.py [--bucket BUCKET_NAME] [--input-dir INPUT_DIRECTORY] [--output OUTPUT_DIRECTORY]")
    print("  If --bucket is not provided, the script will attempt to auto-detect the bucket name from the datalake.")
    print("  If --input-dir is not provided, the current directory is used.")
    print("  If --output is not provided, output will be written to <input-dir>/distrox_templates.")

if __name__ == "__main__":
    # Parse optional --bucket, --input-dir, and --output arguments
    bucket_name_arg = None
    input_dir_arg = "."
    output_dir_arg = None
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print_usage()
        sys.exit(0)
    if "--bucket" in args:
        idx = args.index("--bucket")
        if idx + 1 < len(args):
            bucket_name_arg = args[idx + 1]
        else:
            print("Error: --bucket argument provided but no bucket name specified.")
            print_usage()
            sys.exit(1)
    if "--input-dir" in args:
        idx = args.index("--input-dir")
        if idx + 1 < len(args):
            input_dir_arg = args[idx + 1]
        else:
            print("Error: --input-dir argument provided but no directory specified.")
            print_usage()
            sys.exit(1)
    if "--output" in args:
        idx = args.index("--output")
        if idx + 1 < len(args):
            output_dir_arg = args[idx + 1]
        else:
            print("Error: --output argument provided but no directory specified.")
            print_usage()
            sys.exit(1)
    process_json_files(bucket_name_arg=bucket_name_arg, input_dir=input_dir_arg, output_dir=output_dir_arg)
