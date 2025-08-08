#!/usr/bin/env python3
"""
AWS IAM Policy Downloader

Downloads all attached managed and inline IAM policies for a specified AWS role.
Saves policies as JSON files in an output directory with optional .tgz bundling.

Usage:
    python aws_get_xa_attached_policies.py --role-name <role_name> [--output <output_dir>]

Requirements:
    - boto3
    - AWS credentials configured (via environment, ~/.aws/credentials, or instance profile)
"""

import argparse
import boto3
import logging
import os
import sys
import json
import tarfile
from datetime import datetime
from pathlib import Path
from botocore.exceptions import ClientError

def setup_logging(log_file_path):
    """
    Configure logging to both file and console output.
    
    Args:
        log_file_path (Path): Path to the log file
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

    # File handler
    fh = logging.FileHandler(log_file_path)
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

def get_output_dir(role_name, output_arg):
    """
    Determine and create output directory with timestamp suffix.
    
    Args:
        role_name (str): Name of the IAM role
        output_arg (str): Optional output directory argument
        
    Returns:
        tuple: (output_dir Path, timestamp string)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if output_arg:
        # If output_arg is a path, append role_name and timestamp for uniqueness
        base = Path(output_arg)
        # If the user provided a directory, append role_name and timestamp
        output_dir = base.parent / f"{base.name}_{role_name}_{timestamp}" if base.suffix == "" else base.with_name(f"{base.stem}_{role_name}_{timestamp}")
    else:
        output_dir = Path(f"/tmp/{role_name}_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir, timestamp

def download_attached_managed_policies(iam, role_name, output_dir):
    """
    Download all attached managed policies for the given role.
    
    Args:
        iam: boto3 IAM client
        role_name (str): Name of the IAM role
        output_dir (Path): Directory to save policy JSON files
    """
    logging.info(f"=== Downloading attached managed policies for role: {role_name} ===")
    try:
        response = iam.list_attached_role_policies(RoleName=role_name)
        attached_policies = response.get('AttachedPolicies', [])
        logging.info(f"Found {len(attached_policies)} attached managed policies.")
    except ClientError as e:
        logging.error(f"Error listing attached policies: {e}")
        return

    for policy in attached_policies:
        policy_name = policy['PolicyName']
        policy_arn = policy['PolicyArn']
        logging.info(f"Downloading managed policy: {policy_name} (ARN: {policy_arn})")
        try:
            policy_info = iam.get_policy(PolicyArn=policy_arn)
            version_id = policy_info['Policy']['DefaultVersionId']
            logging.info(f"Default version for {policy_name} is {version_id}")
        except ClientError as e:
            logging.error(f"Error getting policy {policy_name}: {e}")
            continue

        if not version_id.startswith('v') or not version_id[1:].isdigit():
            logging.error(f"Invalid VersionId '{version_id}' for policy {policy_name}")
            continue

        try:
            version = iam.get_policy_version(PolicyArn=policy_arn, VersionId=version_id)
            document = version['PolicyVersion']['Document']
            out_path = output_dir / f"{policy_name}.json"
            with open(out_path, "w") as f:
                json.dump(document, f, indent=2)
            logging.info(f"Policy {policy_name} saved as {out_path}")
        except ClientError as e:
            logging.error(f"Error downloading policy version for {policy_name}: {e}")

def download_inline_policies(iam, role_name, output_dir):
    """
    Download all inline policies for the given role.
    
    Args:
        iam: boto3 IAM client
        role_name (str): Name of the IAM role
        output_dir (Path): Directory to save policy JSON files
    """
    logging.info(f"=== Downloading inline policies for role: {role_name} ===")
    try:
        response = iam.list_role_policies(RoleName=role_name)
        inline_policy_names = response.get('PolicyNames', [])
        logging.info(f"Found {len(inline_policy_names)} inline policies.")
    except ClientError as e:
        logging.error(f"Error listing inline policies: {e}")
        return

    for inline_name in inline_policy_names:
        logging.info(f"Downloading inline policy: {inline_name}")
        try:
            policy = iam.get_role_policy(RoleName=role_name, PolicyName=inline_name)
            document = policy['PolicyDocument']
            out_path = output_dir / f"{role_name}_{inline_name}_inline.json"
            with open(out_path, "w") as f:
                json.dump(document, f, indent=2)
            logging.info(f"Inline policy {inline_name} saved as {out_path}")
        except ClientError as e:
            logging.error(f"Error downloading inline policy {inline_name}: {e}")

def create_tgz_bundle(output_dir, bundle_name):
    """
    Create a .tgz archive of the output directory.
    
    Args:
        output_dir (Path): Directory to archive
        bundle_name (str): Name of the bundle file
        
    Returns:
        Path: Path to the created bundle file
    """
    bundle_path = output_dir.parent / bundle_name
    with tarfile.open(bundle_path, "w:gz") as tar:
        tar.add(output_dir, arcname=output_dir.name)
    logging.info(f"Created bundle: {bundle_path}")
    return bundle_path

def main():
    """Main function to orchestrate the policy download process."""
    parser = argparse.ArgumentParser(
        description="Download all attached managed and inline IAM policies for a given AWS role."
    )
    parser.add_argument("--role-name", required=True, help="Name of the IAM role")
    parser.add_argument("--output", help="Output directory for policy JSON files")
    args = parser.parse_args()

    output_dir, timestamp = get_output_dir(args.role_name, args.output)
    log_file_path = output_dir / "execution.log"
    setup_logging(log_file_path)

    logging.info(f"Starting policy download for role: {args.role_name}")
    logging.info(f"Output directory: {output_dir}")

    iam = boto3.client('iam')

    download_attached_managed_policies(iam, args.role_name, output_dir)
    download_inline_policies(iam, args.role_name, output_dir)

    # Always create a .tgz bundle with timestamp in the name, regardless of --output
    bundle_base = f"{args.role_name}_{timestamp}"
    bundle_name = f"{bundle_base}.tgz"
    create_tgz_bundle(output_dir, bundle_name)
    logging.info(f"Bundle created: {bundle_name}")

    logging.info("All done.")

if __name__ == "__main__":
    main()