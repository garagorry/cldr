#!/usr/bin/env python3

import argparse
import os
import gzip
import re
from datetime import datetime
from tqdm import tqdm

LOG_DATETIME_RE = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}):\d{2}:\d{2},\d+')

def validate_file(file_path):
    if not os.path.exists(file_path):
        raise argparse.ArgumentTypeError(f"File {file_path} does not exist.")
    if not os.access(file_path, os.R_OK):
        raise argparse.ArgumentTypeError(f"File {file_path} is not readable.")
    return file_path

def parse_logs(file_path, output_dir):
    hour_logs = {}
    error_files = set()
    warning_files = set()
    total_size = os.path.getsize(file_path)

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f, tqdm(total=total_size, unit='B', unit_scale=True, desc='Processing log') as pbar:
        current_hour = None

        for line in f:
            pbar.update(len(line.encode('utf-8')))
            match = LOG_DATETIME_RE.match(line)
            if match:
                current_hour = match.group(1)

            if current_hour:
                hour_logs.setdefault(current_hour, []).append(line)
                log_filename = f"{current_hour.replace(' ', '_')}.log.gz"

                if '[ERROR' in line:
                    error_files.add(log_filename)
                elif '[WARNING' in line:
                    warning_files.add(log_filename)

    # Write gzipped logs per hour
    for hour, lines in hour_logs.items():
        filename = f"{hour.replace(' ', '_')}.log.gz"
        out_path = os.path.join(output_dir, filename)
        with gzip.open(out_path, 'wt', encoding='utf-8') as gz_file:
            gz_file.writelines(lines)

    # Write summary logs
    error_summary_path = os.path.join(output_dir, "error_files.log")
    with open(error_summary_path, 'w', encoding='utf-8') as ef:
        for filename in sorted(error_files):
            ef.write(f"{filename}\n")

    warning_summary_path = os.path.join(output_dir, "warning_files.log")
    with open(warning_summary_path, 'w', encoding='utf-8') as wf:
        for filename in sorted(warning_files):
            wf.write(f"{filename}\n")

    print(f"\n✅ Output logs created at: {output_dir}")
    print(f"📄 Error file summary: {error_summary_path}")
    print(f"📄 Warning file summary: {warning_summary_path}")

def main():
    parser = argparse.ArgumentParser(description="Salt Master Log Hourly Parser")
    parser.add_argument('--file', type=validate_file, required=True, help="Path to the Salt log file")
    parser.add_argument('--output-dir', type=str, default=None, help="Base directory to store output logs")

    args = parser.parse_args()
    input_file = args.file

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

    if args.output_dir:
        base_output_dir = args.output_dir
    else:
        base_output_dir = "/var/tmp/salt"

    output_dir = os.path.join(base_output_dir, f"logs_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)

    parse_logs(input_file, output_dir)

if __name__ == "__main__":
    main()
