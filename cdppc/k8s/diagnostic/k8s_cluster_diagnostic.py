import subprocess
import logging
import os
import json
import argparse
import tarfile
from datetime import datetime
from pathlib import Path

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler("k8s_diagnostic.log"),
        logging.StreamHandler()
    ]
)

def run_cmd(command, output_file=None, env=None):
    try:
        logging.info(f"Running: {' '.join(command)}")
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        if output_file:
            with open(output_file, "w") as f:
                f.write(result.stdout)
            logging.info(f"Saved to: {output_file}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {' '.join(command)}")
        logging.error(e.stderr)
        return ""

def get_cluster_name(env):
    raw_config = run_cmd(["kubectl", "config", "view", "--minify", "-o", "json"], env=env)
    try:
        config = json.loads(raw_config)
        return config["clusters"][0]["name"]
    except (json.JSONDecodeError, KeyError, IndexError):
        logging.error("Failed to parse cluster name from kubeconfig.")
        return "unknown-cluster"

def create_tarball(output_dir):
    tarball_path = output_dir.with_suffix(".tar.gz")
    logging.info(f"Creating archive: {tarball_path}")
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(output_dir, arcname=output_dir.name)
    logging.info("Archive created.")

def main():
    parser = argparse.ArgumentParser(description="Collect Kubernetes cluster diagnostics.")
    parser.add_argument("--kubeconfig", required=True, help="Path to kubeconfig file")
    parser.add_argument("--output-dir", type=str, help="Base path for output folder (timestamp will be added)")

    args = parser.parse_args()
    env = os.environ.copy()
    env["KUBECONFIG"] = args.kubeconfig
    logging.info(f"Using kubeconfig: {args.kubeconfig}")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    cluster_name = get_cluster_name(env)

    base_output = args.output_dir.rstrip("/") if args.output_dir else f"/var/tmp/{cluster_name}"
    output_dir = Path(f"{base_output}-{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)
    logging.info(f"Saving output to: {output_dir}")

    run_cmd(["kubectl", "config", "view", "--minify", "-o", "json"], output_dir / f"{cluster_name}_config.json", env=env)

    commands = {
        "all_pods": ["kubectl", "get", "pods", "--all-namespaces", "-o", "wide"],
        "all_nodes": ["kubectl", "get", "nodes", "-o", "wide"],
        "namespaces": ["kubectl", "get", "namespaces"],
        "services": ["kubectl", "get", "services", "--all-namespaces"],
        "deployments": ["kubectl", "get", "deployments", "--all-namespaces"],
        "daemonsets": ["kubectl", "get", "daemonsets", "--all-namespaces"],
        "replicasets": ["kubectl", "get", "replicasets", "--all-namespaces"],
        "configmaps": ["kubectl", "get", "configmaps", "--all-namespaces"],
        "pv": ["kubectl", "get", "pv"],
        "all_pvc": ["kubectl", "get", "pvc", "--all-namespaces"],
        "clusterInfo": ["kubectl", "cluster-info", "dump"],
        "events": ["kubectl", "get", "events", "--all-namespaces", "--sort-by=.metadata.creationTimestamp"]
    }

    for label, cmd in commands.items():
        run_cmd(cmd, output_dir / f"{cluster_name}_{label}.txt", env=env)

    configmaps_output = run_cmd(["kubectl", "get", "configmaps", "--all-namespaces"], env=env)
    lines = configmaps_output.strip().split("\n")[1:]
    for line in lines:
        parts = line.split()
        if len(parts) >= 2:
            namespace, configmap = parts[0], parts[1]
            run_cmd(["kubectl", "describe", "configmap", configmap, "-n", namespace],
                    output_dir / f"{cluster_name}_{namespace}_{configmap}_describeConfigMap.txt", env=env)

    create_tarball(output_dir)

if __name__ == "__main__":
    main()

