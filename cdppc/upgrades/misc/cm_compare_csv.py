import csv
import sys
import os
import time
import threading
import xml.etree.ElementTree as ET

def spinner(stop_event):
    spinner_chars = ['|', '/', '-', '\\']
    idx = 0
    while not stop_event.is_set():
        sys.stdout.write(f'\r{spinner_chars[idx]} Identifying Changes...')
        sys.stdout.flush()
        idx = (idx + 1) % len(spinner_chars)
        time.sleep(0.1)
        idx = (idx + 1) % len(spinner_chars)
    sys.stdout.write('\r✓ Done!          \n')

# Parse XML value into (key, value) pairs
def parse_xml_properties(xml_string):
    props = []
    try:
        root = ET.fromstring(f"<root>{xml_string}</root>")  # Wrap multiple <property> in one root
        for prop in root.findall("property"):
            name = prop.findtext("name")
            value = prop.findtext("value")
            if name is not None and value is not None:
                props.append((name.strip(), value.strip()))
    except ET.ParseError:
        pass  # Not a valid XML string, skip
    return props

# Parse semicolon-separated key=value pairs
def parse_kv_pairs(value):
    props = []
    if ';' in value and '=' in value:
        parts = value.split(';')
        for part in parts:
            if '=' in part:
                k, v = part.split('=', 1)
                props.append((k.strip(), v.strip()))
    return props

# Read CSV and normalize values (split XML or structured key-value strings)
def read_csv(file_path):
    data = {}
    with open(file_path, mode='r') as file:
        reader = csv.reader(file)
        header = next(reader)

        # Detect format: either [filename, key, value] or [filename, key, property, value]
        is_flat = len(header) == 3
        for row in reader:
            filename = row[0].strip()
            key = row[1].strip()

            if is_flat:
                value = row[2].strip()
                if value.startswith("<property>"):
                    for subkey, subval in parse_xml_properties(value):
                        composite_key = (filename, key, subkey)
                        data[composite_key] = subval
                elif ";" in value and "=" in value:
                    for subkey, subval in parse_kv_pairs(value):
                        composite_key = (filename, key, subkey)
                        data[composite_key] = subval
                else:
                    composite_key = (filename, key, "")
                    data[composite_key] = value
            else:
                subkey = row[2].strip()
                value = row[3].strip()
                composite_key = (filename, key, subkey)
                data[composite_key] = value
    return data

def compare_files_and_output_csv(old_file, new_file, modified_file, added_file, removed_file):
    old_data = read_csv(old_file)
    new_data = read_csv(new_file)

    modified = []
    added = []
    removed = []

    stop_event = threading.Event()
    spinner_thread = threading.Thread(target=spinner, args=(stop_event,))
    spinner_thread.start()

    for key in set(old_data).intersection(set(new_data)):
        if old_data[key] != new_data[key]:
            modified.append((key[0], key[1], key[2], old_data[key], new_data[key]))

    for key in new_data:
        if key not in old_data:
            added.append((key[0], key[1], key[2], new_data[key]))

    for key in old_data:
        if key not in new_data:
            removed.append((key[0], key[1], key[2], old_data[key]))

    stop_event.set()
    spinner_thread.join()

    with open(modified_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["filename", "key", "property", "old_value", "new_value"])
        writer.writerows(modified)

    with open(added_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["filename", "key", "property", "new_value"])
        writer.writerows(added)

    with open(removed_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["filename", "key", "property", "old_value"])
        writer.writerows(removed)

    print("\n🔄 Identified Changes:")
    print(f"\nModified values ({len(modified)}):")

def main():
    if len(sys.argv) != 6:
        print("❌ Usage: python compare_csv.py <old_file.csv> <new_file.csv> <modified_file.csv> <added_file.csv> <removed_file.csv>")
        sys.exit(1)

    old_file, new_file, modified_file, added_file, removed_file = sys.argv[1:]

    if not os.path.exists(old_file):
        print(f"❌ The file {old_file} does not exist.")
        sys.exit(1)

    if not os.path.exists(new_file):
        print(f"❌ The file {new_file} does not exist.")
        sys.exit(1)

    compare_files_and_output_csv(old_file, new_file, modified_file, added_file, removed_file)

    print(f"\n✅ The identified changes have been written to:")
    print(f"  Modified values: {modified_file}")
    print(f"  Added values: {added_file}")
    print(f"  Removed values: {removed_file}")

if __name__ == "__main__":
    main()