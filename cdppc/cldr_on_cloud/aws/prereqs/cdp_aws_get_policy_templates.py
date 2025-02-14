import subprocess
import base64
import json
import os
import argparse

def is_cdp_installed():
    try:
        subprocess.run(["cdp", "--help"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        print("Error: The 'cdp' command is not installed or not found in the system PATH.")
        return False
    except subprocess.CalledProcessError:
        print("Error: The 'cdp' command failed to execute correctly.")
        return False

def save_pretty_json(filename, data):
    try:
        with open(filename, "w") as file:
            json.dump(data, file, indent=4)
        print(f"Policy Template saved: {filename}")
    except Exception as e:
        print(f"Error saving JSON to {filename}: {e}")

def parse_args():
    parser = argparse.ArgumentParser(description="Fetch AWS policy templates using the CDP CLI.")
    parser.add_argument("--profile", type=str, default="default", help="CDP profile to use (default is 'default').")
    return parser.parse_args()

def validate_profile_and_fetch_data(profile):
    command = f"cdp --profile {profile} environments get-credential-prerequisites --cloud-platform AWS"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: Unable to access CDP using profile '{profile}'.")
        return None

    return result.stdout

def main():
    args = parse_args()

    if not is_cdp_installed():
        exit(1)

    output = validate_profile_and_fetch_data(args.profile)

    if not output:
        exit(1)

    try:
        output_json = json.loads(output)
    except json.JSONDecodeError:
        print("Error: Failed to parse JSON from the CDP command output.")
        exit(1)

    aws_data = output_json.get("aws", {})
    aws_accountId = output_json.get("accountId", "unknown_account")

    if aws_accountId == "unknown_account":
        print("Error: AWS account ID not found in the output.")
        exit(1)

    policy_base64 = aws_data.get("policyJson", None)
    if policy_base64:
        decoded_policy = base64.b64decode(policy_base64).decode('utf-8')
        decoded_policy_json = json.loads(decoded_policy)
        crossAccountPolicyName = f"{aws_accountId}_xa.json"
        save_pretty_json(crossAccountPolicyName, decoded_policy_json)

    policies = aws_data.get("policies", [])
    if policies:
        for policy in policies:
            service = policy.get("service", None)
            policy_base64 = policy.get("policyJson", None)

            if service and policy_base64:
                decoded_policy = base64.b64decode(policy_base64).decode('utf-8')
                decoded_policy_json = json.loads(decoded_policy)

                filename = f"{service.replace(' ', '_')}.json"
                save_pretty_json(filename, decoded_policy_json)
                print(f" - {service}: Policy saved to {filename}")
    else:
        print("No individual policies found.")

if __name__ == "__main__":
    main()
