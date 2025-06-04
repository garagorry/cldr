import subprocess
import json
import argparse
import shutil
import sys
import logging
from tqdm import tqdm

# ---- Logging Configuration ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# ---- CDP CLI Validation ----
def check_cdp_installed():
    if not shutil.which("cdp"):
        logging.error("'cdp' CLI is not installed or not in your PATH.")
        sys.exit(1)
    logging.info("✅ CDP CLI is available.")

# ---- Helper Functions ----

def run_cli(cmd):
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, check=True)
        return result.stdout.decode("utf-8")
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {cmd}")
        logging.error(e.stderr.decode("utf-8"))
        sys.exit(1)

def get_credential_crn(credential_name):
    logging.info(f"🔍 Fetching CRN for credential: {credential_name}")
    output = run_cli(f"cdp environments list-credentials --credential-name {credential_name}")
    data = json.loads(output)
    return data["credentials"][0]["crn"]

def get_shared_resource_user_role_crn():
    logging.info("🔍 Looking up SharedResourceUser role CRN...")
    output = run_cli("cdp iam list-resource-roles")
    roles = json.loads(output)["resourceRoles"]
    for role in roles:
        if role["crn"].endswith("SharedResourceUser"):
            return role["crn"]
    return None

def list_all_users():
    logging.info("📋 Listing all users...")
    output = run_cli("cdp iam list-users")
    return {user["workloadUsername"]: user["crn"] for user in json.loads(output)["users"]}

def list_all_groups():
    logging.info("📋 Listing all groups...")
    output = run_cli("cdp iam list-groups")
    return {group["groupName"]: group["groupName"] for group in json.loads(output)["groups"]}

def list_all_machine_users():
    logging.info("📋 Listing all machine users...")
    output = run_cli("cdp iam list-machine-users")
    return {user["machineUsername"]: user["crn"] for user in json.loads(output)["machineUsers"]}

def assign_shared_resource_user(assignee_id, role_crn, resource_crn, assignee_type):
    logging.info(f"🔐 Assigning SharedResourceUser role to {assignee_type}: {assignee_id}")
    if assignee_type == "user":
        assign_cmd = f"cdp iam assign-user-resource-role --user {assignee_id} --resource-role-crn {role_crn} --resource-crn {resource_crn}"
    elif assignee_type == "group":
        assign_cmd = f"cdp iam assign-group-resource-role --group-name {assignee_id} --resource-role-crn {role_crn} --resource-crn {resource_crn}"
    elif assignee_type == "machine-user":
        assign_cmd = f"cdp iam assign-machine-user-resource-role --machine-user {assignee_id} --resource-role-crn {role_crn} --resource-crn {resource_crn}"
    else:
        logging.error("Invalid assignee type")
        sys.exit(1)

    run_cli(assign_cmd)
    logging.info("✅ Role assignment successful.")

# ---- Main Function ----

def main():
    parser = argparse.ArgumentParser(description="Assign SharedResourceUser role to a CDP user, group, or machine-user.")
    parser.add_argument("--credential-name", required=True, help="Name of the CDP credential")
    parser.add_argument("--assignee-type", required=True, choices=["user", "group", "machine-user"], help="Type of assignee")
    parser.add_argument("--assignee-name", required=True, help="Username, group name, or machine user name")

    args = parser.parse_args()

    steps = [
        "Validate CDP CLI installation",
        "Get Credential CRN",
        "Get SharedResourceUser Role CRN",
        "Fetch Assignee CRN",
        "Assign Role"
    ]

    with tqdm(total=len(steps), desc="Progress", bar_format="{l_bar}{bar} [step {n_fmt}/{total_fmt}]") as pbar:
        check_cdp_installed()
        pbar.update(1)

        credential_crn = get_credential_crn(args.credential_name)
        logging.info(f"🔑 Credential CRN: {credential_crn}")
        pbar.update(1)

        role_crn = get_shared_resource_user_role_crn()
        if not role_crn:
            logging.error("❌ SharedResourceUser role not found.")
            sys.exit(1)
        logging.info(f"🧾 Role CRN: {role_crn}")
        pbar.update(1)

        assignee_id = None
        if args.assignee_type == "user":
            users = list_all_users()
            assignee_id = users.get(args.assignee_name)
        elif args.assignee_type == "group":
            groups = list_all_groups()
            assignee_id = groups.get(args.assignee_name)
        elif args.assignee_type == "machine-user":
            mus = list_all_machine_users()
            assignee_id = mus.get(args.assignee_name)

        if not assignee_id:
            logging.error(f"❌ {args.assignee_type} '{args.assignee_name}' not found.")
            sys.exit(1)
        logging.info(f"👤 Assignee CRN: {assignee_id}")
        pbar.update(1)

        assign_shared_resource_user(assignee_id, role_crn, credential_crn, args.assignee_type)
        pbar.update(1)

if __name__ == "__main__":
    main()
