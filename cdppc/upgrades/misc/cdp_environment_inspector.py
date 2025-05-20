#!/usr/bin/env python3
import subprocess
import json
import datetime
import os
import argparse
from tqdm import tqdm

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.decode('utf-8')
    except subprocess.CalledProcessError as e:
        stderr_output = e.stderr.decode('utf-8')

        filtered_stderr = "\n".join(
            line for line in stderr_output.splitlines()
            if "You are running a BETA release of the CDP CLI" not in line
        ).strip()

        if (
            "describe-database-server" in command and
            ("Database for Data Hub" in filtered_stderr or "NOT_FOUND" in filtered_stderr)
        ):
            print(f"Info: Skipping DB server description for embedded Postgres in:\n  {command}")
            return None

        print(f"Error executing command: {command}")
        print(f"Error details: {filtered_stderr}")
        return None

def get_timestamp():
    return datetime.datetime.now().strftime("%Y%m%d%H%M%S")

def save_to_file(data, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'a') as file:
        file.write(data)

def main(base_dir, env_names_filter=None):
    print("Fetching environments...")
    environments_output = run_command("cdp environments list-environments")
    if not environments_output:
        return

    environments = json.loads(environments_output).get('environments', [])

    if env_names_filter:
        environments = [env for env in environments if env.get('environmentName') in env_names_filter]

    for env in tqdm(environments, desc="Processing environments"):
        environment_crn = env.get('crn')
        environment_name = env.get('environmentName')
        if not environment_crn or not environment_name:
            continue

        # Environment Details
        env_details = run_command(f"cdp environments describe-environment --environment-name {environment_crn}")
        if env_details:
            save_to_file(env_details, os.path.join(base_dir, f"ENVIRONMENT_ENV_{environment_name}_{get_timestamp()}.json"))

        # FreeIPA Upgrade Options
        freeipa_upgrade_options = run_command(f"cdp environments get-freeipa-upgrade-options --environment {environment_crn}")
        if freeipa_upgrade_options:
            save_to_file(freeipa_upgrade_options, os.path.join(base_dir, f"ENVIRONMENT_ENV_{environment_name}_FreeIPAUpgradeOptions_{get_timestamp()}.json"))

        # Datalake
        print(f"Fetching datalake for environment {environment_name}...")
        datalakes_output = run_command(f"cdp datalake list-datalakes --environment-name {environment_crn}")
        if datalakes_output:
            datalakes = json.loads(datalakes_output).get('datalakes', [])
            for datalake in tqdm(datalakes, desc="Processing datalakes"):
                datalake_crn = datalake.get('crn')
                datalake_name = datalake.get('datalakeName')
                if not datalake_crn or not datalake_name:
                    continue

                datalake_details = run_command(f"cdp datalake describe-datalake --datalake-name {datalake_crn}")
                if datalake_details:
                    save_to_file(datalake_details, os.path.join(base_dir, f"ENVIRONMENT_ENV_{environment_name}_DL_{datalake_name}_{get_timestamp()}.json"))

                db_server_details = run_command(f"cdp datalake describe-database-server --cluster-crn {datalake_crn}")
                if db_server_details:
                    save_to_file(db_server_details, os.path.join(base_dir, f"ENVIRONMENT_ENV_{environment_name}_DL_{datalake_name}_DB_{get_timestamp()}.json"))

                available_images = run_command(f"cdp datalake upgrade-datalake --show-available-images --datalake-name {datalake_crn}")
                if available_images:
                    save_to_file(available_images, os.path.join(base_dir, f"ENVIRONMENT_ENV_{environment_name}_DL_{datalake_name}_AvailableImages_{get_timestamp()}.json"))

                runtime_images = run_command(f"cdp datalake upgrade-datalake --show-latest-available-image-per-runtime --datalake-name {datalake_crn}")
                if runtime_images:
                    save_to_file(runtime_images, os.path.join(base_dir, f"ENVIRONMENT_ENV_{environment_name}_DL_{datalake_name}_RunTimeAvailableImages_{get_timestamp()}.json"))

        # Datahubs
        print(f"Fetching datahubs for environment {environment_name}...")
        datahubs_output = run_command(f"cdp datahub list-clusters --environment-name {environment_crn}")
        if datahubs_output:
            datahubs = json.loads(datahubs_output).get('clusters', [])
            for datahub in tqdm(datahubs, desc="Processing datahubs"):
                datahub_crn = datahub.get('crn')
                datahub_name = datahub.get('clusterName')
                if not datahub_crn or not datahub_name:
                    continue

                datahub_details = run_command(f"cdp datahub describe-cluster --cluster-name {datahub_crn}")
                if datahub_details:
                    save_to_file(datahub_details, os.path.join(base_dir, f"ENVIRONMENT_ENV_{environment_name}_DH_{datahub_name}_{get_timestamp()}.json"))

                available_images = run_command(f"cdp datahub upgrade-cluster --show-available-images --cluster-name {datahub_crn}")
                if available_images:
                    save_to_file(available_images, os.path.join(base_dir, f"ENVIRONMENT_ENV_{environment_name}_DH_{datahub_name}_AvailableImages_{get_timestamp()}.json"))

                runtime_images = run_command(f"cdp datahub upgrade-cluster --show-latest-available-image-per-runtime --cluster-name {datahub_crn}")
                if runtime_images:
                    save_to_file(runtime_images, os.path.join(base_dir, f"ENVIRONMENT_ENV_{environment_name}_DH_{datahub_name}_RunTimeAvailableImages_{get_timestamp()}.json"))

                db_server_details = run_command(f"cdp datahub describe-database-server --cluster-crn {datahub_crn}")
                if db_server_details:
                    save_to_file(db_server_details, os.path.join(base_dir, f"ENVIRONMENT_ENV_{environment_name}_DH_{datahub_name}_DB_{get_timestamp()}.json"))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process CDP environments and save outputs to a specified directory.")
    parser.add_argument("--base-dir", type=str, default="/tmp", help="Base directory to store output files.")
    parser.add_argument("--env-name", action="append", help="Specify an environment name to process (can be used multiple times).")
    args = parser.parse_args()

    os.makedirs(args.base_dir, exist_ok=True)
    main(args.base_dir, env_names_filter=args.env_name)

# python3 cdp_environment_inspector.py --base-dir /tmp/cdp_output_$(date +"%Y%m%d%H%M%S")
# python3 cdp_environment_inspector.py --base-dir /tmp/cdp_output_$(date +"%Y%m%d%H%M%S") --env-name jdga-01-cdp-env --env-name jdga-02-env
