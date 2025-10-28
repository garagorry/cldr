#!/usr/bin/env python3
"""Common utility functions for CDP discovery."""

import subprocess
import threading
import itertools
import time
from datetime import datetime
from pathlib import Path
import json
import shutil


def log(message):
    """Log a message with timestamp."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def spinner_thread_func(stop_event, message):
    """Display a spinner animation while a task is running."""
    for symbol in itertools.cycle("|/-\\"):
        if stop_event.is_set():
            break
        print(f"\r [{symbol}] {message}", end="", flush=True)
        time.sleep(0.1)
    print("\r", end="")


def run_command(command, task_name=None, debug=False):
    """
    Run a shell command and return stdout and stderr.
    
    Args:
        command: Command string to execute
        task_name: Optional task name for spinner display
        debug: Enable debug output
        
    Returns:
        tuple: (stdout, stderr) or (None, error_message)
    """
    stop_spinner = threading.Event()
    if task_name:
        spinner = threading.Thread(target=spinner_thread_func, args=(stop_spinner, task_name))
        spinner.start()
    
    try:
        if debug:
            log(f"DEBUG: Running command: {command}")
        
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        
        if task_name:
            stop_spinner.set()
            spinner.join()
        
        if debug:
            log(f"DEBUG: Return code: {result.returncode}")
            log(f"DEBUG: STDOUT: {result.stdout.strip()}")
            log(f"DEBUG: STDERR: {result.stderr.strip()}")
        
        if result.returncode != 0:
            return None, result.stderr.strip()
        
        return result.stdout.strip(), None
        
    except Exception as e:
        if task_name:
            stop_spinner.set()
            spinner.join()
        if debug:
            log(f"DEBUG: Exception: {e}")
        return None, str(e)


def run_command_json(command, task_name=None, debug=False):
    """
    Run a command and parse JSON output.
    
    Args:
        command: Command string to execute
        task_name: Optional task name for spinner display
        debug: Enable debug output
        
    Returns:
        tuple: (parsed_json, error) or (None, error_message)
    """
    output, error = run_command(command, task_name, debug=debug)
    if output:
        try:
            return json.loads(output), None
        except json.JSONDecodeError:
            if debug:
                log(f"DEBUG: Failed to parse JSON. Output was: {output}")
            return None, "Failed to parse JSON response."
    return None, error


def save_to_file(data, filepath):
    """
    Save data to a file (JSON or text).
    
    Args:
        data: Data to save (dict/list for JSON, str for text)
        filepath: Path object or string for output file
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, "w") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, indent=2)
    
    log(f"✅ Saved: {filepath}")


def save_recipe_script(content, filepath):
    """
    Save a recipe script and optionally format it with shfmt.
    
    Args:
        content: Script content as string
        filepath: Path object or string for output file
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, "w") as f:
        f.write(content)
    
    if shutil.which("shfmt"):
        subprocess.run(["shfmt", "-w", str(filepath)], check=False)
        log(f"✅ Saved (formatted): {filepath}")
    else:
        log(f"✅ Saved: {filepath}")


def get_timestamp():
    """Get current timestamp in format YYYYMMDDHHMMSS."""
    return datetime.now().strftime("%Y%m%d%H%M%S")


def flatten_json(data, parent_key='', sep='.'):
    """
    Flatten nested JSON structure.
    
    Args:
        data: JSON data to flatten
        parent_key: Parent key prefix
        sep: Separator for nested keys
        
    Returns:
        dict: Flattened dictionary
    """
    items = []
    
    if isinstance(data, list):
        for i, v in enumerate(data):
            new_key = f"{parent_key}[{i}]" if parent_key else str(i)
            items.extend(flatten_json(v, new_key, sep=sep).items())
    elif isinstance(data, dict):
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            items.extend(flatten_json(v, new_key, sep=sep).items())
    else:
        items.append((parent_key, data))
    
    return dict(items)


def create_archive(directory_path):
    """
    Create a tar.gz archive of a directory.
    
    Args:
        directory_path: Path to directory to archive
        
    Returns:
        str: Path to created archive
    """
    directory_path = Path(directory_path)
    archive_path = f"{directory_path}.tar.gz"
    shutil.make_archive(str(directory_path), 'gztar', root_dir=directory_path)
    log(f"📦 Archived output to: {archive_path}")
    return archive_path

