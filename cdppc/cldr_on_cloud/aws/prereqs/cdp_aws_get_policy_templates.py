from datetime import datetime
import subprocess
import base64
import json
import os
import argparse
import time

def is_cdp_installed():
    print("🔍 Checking if 'cdp' CLI is installed...")
    try:
        subprocess.run(["cdp", "--help"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("✅ 'cdp' is installed.")
        return True
    except FileNotFoundError:
        print("❌ Error: The 'cdp' command is not installed or not found in the system PATH.")
        return False
    except subprocess.CalledProcessError:
        print("❌ Error: The 'cdp' command failed to execute correctly.")
        return False

def save_pretty_json(directory, filename, data):
    os.makedirs(directory, exist_ok=True)
    filepath = os.path.join(directory, filename)
    try:
        with open(filepath, "w") as file:
            json.dump(data, file, indent=4)
        print(f"📄 Policy saved: {filepath}")
    except Exception as e:
        print(f"❌ Error saving JSON to {filepath}: {e}")

def parse_args():
    parser = argparse.ArgumentParser(description="Fetch AWS policy templates using the CDP CLI.")
    parser.add_argument("--profile", type=str, default="default", help="CDP profile to use (default is 'default').")
    return parser.parse_args()

def validate_profile_and_fetch_data(profile):
    print(f"🔐 Fetching AWS credential prerequisites using profile: '{profile}'...")
    command = f"cdp --profile {profile} environments get-credential-prerequisites --cloud-platform AWS"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Error: Unable to access CDP using profile '{profile}'.")
        return None

    print("✅ CDP data fetched.")
    return result.stdout

def main():
    args = parse_args()

    if not is_cdp_installed():
        exit(1)

    output = validate_profile_and_fetch_data(args.profile)
    if not output:
        exit(1)

    print("🧩 Parsing JSON output...")
    try:
        output_json = json.loads(output)
    except json.JSONDecodeError:
        print("❌ Error: Failed to parse JSON from the CDP command output.")
        exit(1)

    aws_data = output_json.get("aws", {})
    aws_accountId = output_json.get("accountId", "unknown_account")

    if aws_accountId == "unknown_account":
        print("❌ Error: AWS account ID not found in the output.")
        exit(1)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    output_dir = f"/tmp/AWS_Policies_{timestamp}"
    print(f"📁 Creating output directory: {output_dir}")
    os.makedirs(output_dir, exist_ok=True)

    print("📥 Processing cross-account policy...")
    policy_base64 = aws_data.get("policyJson", None)
    if policy_base64:
        decoded_policy = base64.b64decode(policy_base64).decode('utf-8')
        decoded_policy_json = json.loads(decoded_policy)
        crossAccountPolicyName = f"{aws_accountId}_xa.json"
        save_pretty_json(output_dir, crossAccountPolicyName, decoded_policy_json)

    policies = aws_data.get("policies", [])
    if policies:
        print("📦 Processing individual service policies...")
        for i, policy in enumerate(policies, start=1):
            service = policy.get("service", None)
            policy_base64 = policy.get("policyJson", None)

            if service and policy_base64:
                # Skip DynamoDB policies
                if service.lower() == "dynamodb":
                    print(f"  [{i}/{len(policies)}] ⏭️ Skipping DynamoDB policy")
                    continue
                
                print(f"  [{i}/{len(policies)}] 🔓 Decoding policy for service: {service}")
                decoded_policy = base64.b64decode(policy_base64).decode('utf-8')
                decoded_policy_json = json.loads(decoded_policy)

                filename = f"{service.replace(' ', '_')}.json"
                save_pretty_json(output_dir, filename, decoded_policy_json)
    else:
        print("ℹ️ No individual policies found.")

    print(f"\n✅ All policies saved in: {output_dir}")

if __name__ == "__main__":
    main()
