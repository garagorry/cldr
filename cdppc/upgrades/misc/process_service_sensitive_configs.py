import os
import json
import xml.etree.ElementTree as ET
import re
import csv
import argparse

# Define sensitive property keywords
SENSITIVE_KEYWORDS = ["password", "secret", "token", "key", "credential", "passphrase"]

# Helper: Check if a property is sensitive
def is_sensitive_property(property_name):
    for keyword in SENSITIVE_KEYWORDS:
        if keyword in property_name.lower():
            return True
    return False

# Helper: Sanitize sensitive values
def sanitize_value(value):
    return re.sub(r'{{CM_AUTO_TLS}}', '****', value).replace('\n', '').replace('"', '""')

# Helper: Process XML configurations (for nested properties)
def process_xml_configuration(xml_string):
    try:
        root = ET.fromstring(xml_string)
        for property_elem in root.findall('.//property'):
            name = property_elem.find('name').text
            value = property_elem.find('value').text
            sanitized_value = sanitize_value(value)
            if is_sensitive_property(name):
                sanitized_value = '****'
            yield name, sanitized_value
    except ET.ParseError:
        # If it's not a valid XML, we return an empty generator
        return []

# Function to process service and role config files
def process_config_files(input_dir, output_csv_file):
    header = ["type", "service_or_role", "property", "value"]

    with open(output_csv_file, mode='w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(header)

        # Process ServiceConfigs directory
        service_config_dir = os.path.join(input_dir, "ServiceConfigs")
        for service_file in os.listdir(service_config_dir):
            if service_file.endswith('.json'):
                service_name = service_file.split('_')[1]  # Assuming the format of file name
                with open(os.path.join(service_config_dir, service_file), 'r') as f:
                    try:
                        service_data = json.load(f)
                        for item in service_data.get('items', []):
                            key = item.get('name')
                            val = item.get('value', '')
                            sanitized_value = sanitize_value(val)

                            if is_sensitive_property(key):
                                sanitized_value = '****'

                            # Write service data to CSV
                            csv_writer.writerow(["service", service_name, key, f'"{sanitized_value}"'])

                            # Check if the value is XML (for nested properties)
                            if sanitized_value.startswith('<property'):
                                for sub_key, sub_val in process_xml_configuration(sanitized_value):
                                    csv_writer.writerow(["service", service_name, sub_key, f'"{sub_val}"'])
                    except json.JSONDecodeError:
                        print(f"Error processing JSON file: {service_file}")

        # Process roleConfigGroups directory
        role_config_dir = os.path.join(input_dir, "roleConfigGroups")
        for role_file in os.listdir(role_config_dir):
            if role_file.endswith('.json'):
                role_name = role_file.split('_')[1]  # Assuming the format of file name
                with open(os.path.join(role_config_dir, role_file), 'r') as f:
                    try:
                        role_data = json.load(f)
                        for item in role_data.get('items', []):
                            key = item.get('name')
                            val = item.get('value', '')
                            sanitized_value = sanitize_value(val)

                            if is_sensitive_property(key):
                                sanitized_value = '****'

                            # Write role data to CSV
                            csv_writer.writerow(["role", role_name, key, f'"{sanitized_value}"'])

                            # Check if the value is XML (for nested properties)
                            if sanitized_value.startswith('<property'):
                                for sub_key, sub_val in process_xml_configuration(sanitized_value):
                                    csv_writer.writerow(["role", role_name, sub_key, f'"{sub_val}"'])
                    except json.JSONDecodeError:
                        print(f"Error processing JSON file: {role_file}")

def main():
    parser = argparse.ArgumentParser(description="Process Cloudera configuration files")
    parser.add_argument("input_dir", help="Path to the directory containing ServiceConfigs and roleConfigGroups folders")
    parser.add_argument("output_dir", help="Path to the directory where output CSV will be saved")

    args = parser.parse_args()

    if not os.path.exists(args.input_dir):
        print(f"❌ Error: The input directory '{args.input_dir}' does not exist.")
        return

    os.makedirs(args.output_dir, exist_ok=True)

    output_csv_file = os.path.join(args.output_dir, "all_services_config.csv")

    process_config_files(args.input_dir, output_csv_file)

    print(f"🎯 Output CSV file: {output_csv_file}")
    print("📦 Process completed!")

if __name__ == "__main__":
    main()