import json
import csv
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

def parse_xml_properties(xml_string, filename, parent_key):
    """Extract properties from an embedded XML string."""
    results = []
    wrapped = f"<configuration>{xml_string}</configuration>"
    try:
        root = ET.fromstring(wrapped)
        for prop in root.findall("property"):
            key = prop.findtext("name")
            val = prop.findtext("value")
            if key is not None and val is not None:
                results.append((filename, parent_key, key, val))
    except ET.ParseError as e:
        results.append((filename, parent_key, "INVALID_XML", f"{e}"))
    return results

def process_json_file(filepath):
    """Parse one JSON file and extract all config properties."""
    rows = []
    with open(filepath, "r") as f:
        data = json.load(f)
    
    for item in data.get("items", []):
        key = item.get("name")
        val = item.get("value", "")
        
        # If the value contains embedded XML <property> tags
        if isinstance(val, str) and "<property>" in val:
            rows.extend(parse_xml_properties(val, filepath.name, key))
        else:
            rows.append((filepath.name, key, val))
    
    return rows

def main():
    parser = argparse.ArgumentParser(description="Extract Cloudera configuration properties from JSON files.")
    parser.add_argument("input_dir", help="Directory containing JSON files")
    parser.add_argument("output_csv", help="Path to output CSV file")
    args = parser.parse_args()

    input_path = Path(args.input_dir)
    all_rows = []

    for json_file in sorted(input_path.glob("*.json")):
        print(f"Processing: {json_file.name}")
        all_rows.extend(process_json_file(json_file))

    # Decide column count based on presence of XML-expanded rows
    has_xml = any(len(row) == 4 for row in all_rows)
    headers = ["filename", "key", "value"] if not has_xml else ["filename", "key", "value", "property value"]

    with open(args.output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in all_rows:
            writer.writerow(row)

    print(f"\n✅ Done! Output written to {args.output_csv}")

if __name__ == "__main__":
    main()