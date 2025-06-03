import json
import os
import argparse
import sys
from datetime import datetime

def load_json_file(filepath):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

def extract_actions_from_statement(statement):
    actions = statement.get("Action", [])
    if isinstance(actions, str):
        return [actions]
    return actions

def check_policy_for_permissions(policy, permissions_to_check):
    found = set()
    statements = policy.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]

    for statement in statements:
        actions = extract_actions_from_statement(statement)
        for action in actions:
            if action in permissions_to_check:
                found.add(action)
    return found

def get_latest_policy_dir(base_path="/tmp"):
    dirs = [d for d in os.listdir(base_path) if d.startswith("AWS_Policies_")]
    if not dirs:
        print(f"No policy directories found in {base_path}")
        return None, []

    dirs.sort(reverse=True)
    latest = os.path.join(base_path, dirs[0])
    others = [os.path.join(base_path, d) for d in dirs[1:]]
    return latest, others

def main():
    parser = argparse.ArgumentParser(
        description="Check AWS permissions in policy JSON files.",
        epilog=(
            "Example of permissions file:\n"
            "  tag:GetResources\n"
            "  tag:UntagResources\n"
            "  tag:GetTagValues\n"
            "  resource-explorer:ListTags\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--policy-dir", required=False, help="Directory containing policy JSON files.")
    parser.add_argument("--permissions-file", required=True, help="Text file listing permissions to check (one per line).")

    if len(sys.argv) == 1:
        parser.print_help()
        print("\nExample usage:")
        print("  python check_permissions.py --permissions-file required_perms.txt\n")
        sys.exit(0)

    args = parser.parse_args()

    try:
        with open(args.permissions_file, "r") as f:
            permissions = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading permissions file: {e}")
        return

    permissions_set = set(permissions)

    policy_dir = args.policy_dir
    if not policy_dir:
        policy_dir, other_dirs = get_latest_policy_dir()
        if not policy_dir:
            return
        print(f"Using latest policy directory: {policy_dir}")
        if other_dirs:
            print("Other available policy directories:")
            for d in other_dirs:
                print(f"  - {d}")
        print()

    if not os.path.exists(policy_dir) or not os.path.isdir(policy_dir):
        print(f"Error: Policy directory '{policy_dir}' does not exist or is not a directory.")
        return

    print("\n=== Permissions Found in Policies ===\n")
    found_any = False
    for filename in os.listdir(policy_dir):
        if filename.endswith(".json"):
            filepath = os.path.join(policy_dir, filename)
            policy_json = load_json_file(filepath)
            if not policy_json:
                continue

            found_perms = check_policy_for_permissions(policy_json, permissions_set)
            if found_perms:
                found_any = True
                print(f"[{filename}]:")
                for perm in sorted(found_perms):
                    print(f"  - {perm}")
                print()

    if not found_any:
        print("No specified permissions were found in any policy.")

if __name__ == "__main__":
    main()
