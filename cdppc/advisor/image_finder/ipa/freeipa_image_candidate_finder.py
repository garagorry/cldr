#!/usr/bin/env python3
"""
FreeIPA Image Candidate Finder

This script analyzes the FreeIPA image catalog to find image candidates based on:
- Source image ID (UUID)
- Cloud provider (aws, azure, gcp)
- Image creation/published dates (falls back to human date string when numeric is missing)
- OS compatibility (same OS family/major by default; can allow major upgrades)

It identifies newer images that can be used as base images for creating/updating
FreeIPA images used by Cloudera Environments Service.

Usage:
    python freeipa_image_candidate_finder.py --source-imageId <uuid> --cloud-provider <aws|azure|gcp>
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from typing import Dict, List, Optional

import requests


class FreeIPAImageCandidateFinder:
    def __init__(self, catalog_url: str = "https://cloudbreak-imagecatalog.s3.amazonaws.com/v3-prod-freeipa-image-catalog.json"):
        self.catalog_url = catalog_url
        self.catalog_data: Optional[Dict] = None

    def fetch_catalog(self) -> bool:
        try:
            print(f"Fetching FreeIPA catalog from: {self.catalog_url}")
            response = requests.get(self.catalog_url, timeout=30)
            response.raise_for_status()
            self.catalog_data = response.json()
            print("✓ Successfully fetched FreeIPA catalog")
            return True
        except requests.RequestException as e:
            print(f"✗ Error fetching catalog: {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"✗ Error parsing catalog JSON: {e}")
            return False

    def find_source_image(self, source_uuid: str) -> Optional[Dict]:
        if not self.catalog_data:
            return None

        images_root = self.catalog_data.get("images", {})
        ipa_images = images_root.get("freeipa-images", [])
        for image in ipa_images:
            if isinstance(image, dict) and image.get("uuid") == source_uuid:
                return image

        # Fallback: recursive search anywhere
        return self._search_recursively(self.catalog_data, source_uuid)

    def _search_recursively(self, data, target_uuid: str) -> Optional[Dict]:
        if isinstance(data, dict):
            if data.get("uuid") == target_uuid:
                return data
            for _k, v in data.items():
                res = self._search_recursively(v, target_uuid)
                if res:
                    return res
        elif isinstance(data, list):
            for item in data:
                res = self._search_recursively(item, target_uuid)
                if res:
                    return res
        return None

    def get_image_timestamp(self, image: Dict) -> int:
        # Prefer numeric created/published if available
        created_ts = image.get("created")
        if isinstance(created_ts, int) and created_ts > 0:
            return created_ts

        # Many FreeIPA entries use only a date string (YYYY-MM-DD)
        date_str = image.get("date")
        if isinstance(date_str, str):
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
                try:
                    return int(datetime.strptime(date_str, fmt).timestamp())
                except ValueError:
                    pass

        # Fallback to 0 if nothing usable
        return 0

    def same_or_allowed_os(self, source_image: Dict, candidate_image: Dict, allow_major_os_upgrade: bool) -> bool:
        source_os_type = source_image.get("os_type") or source_image.get("os") or ""
        cand_os_type = candidate_image.get("os_type") or candidate_image.get("os") or ""

        if not source_os_type or not cand_os_type:
            return True

        if source_os_type == cand_os_type:
            return True

        if not allow_major_os_upgrade:
            return False

        # Allow upgrade: treat redhat7/centos7 compatible; redhat8 is higher than 7, etc.
        def extract_family_major(value: str) -> (str, int):
            family = ""
            major = 0
            for fam in ("redhat", "centos", "rhel"):
                if value.startswith(fam):
                    family = fam
                    rest = value[len(fam):]
                    try:
                        major = int("".join(ch for ch in rest if ch.isdigit()) or "0")
                    except ValueError:
                        major = 0
                    break
            if not family and value:
                # fallback: any alpha prefix + trailing digits
                prefix = "".join(ch for ch in value if ch.isalpha())
                digits = "".join(ch for ch in value if ch.isdigit())
                family = prefix or value
                try:
                    major = int(digits or "0")
                except ValueError:
                    major = 0
            return family, major

        src_family, src_major = extract_family_major(source_os_type)
        cand_family, cand_major = extract_family_major(cand_os_type)

        if src_family == cand_family and cand_major >= src_major:
            return True
        # Treat centos and redhat/rhel as same family for upgrade purposes
        families_equiv = {"centos", "redhat", "rhel"}
        if src_family in families_equiv and cand_family in families_equiv and cand_major >= src_major:
            return True

        return False

    def find_newer_images(
        self,
        source_image: Dict,
        cloud_provider: str,
        allow_major_os_upgrade: bool
    ) -> List[Dict]:
        newer_images: List[Dict] = []
        if not self.catalog_data:
            return newer_images

        images_root = self.catalog_data.get("images", {})
        ipa_images = images_root.get("freeipa-images", [])

        source_ts = self.get_image_timestamp(source_image)

        for image in ipa_images:
            if not isinstance(image, dict):
                continue

            # Must be newer by timestamp
            image_ts = self.get_image_timestamp(image)
            if image_ts <= source_ts:
                continue

            # Must have provider mapping
            images_map = image.get("images", {})
            if cloud_provider not in images_map:
                continue

            # Must be compatible OS (or allowed upgrade)
            if not self.same_or_allowed_os(source_image, image, allow_major_os_upgrade):
                continue

            newer_images.append(image)

        # Sort by newest first
        newer_images.sort(key=lambda x: self.get_image_timestamp(x), reverse=True)

        return newer_images

    def format_timestamp(self, ts: int) -> str:
        try:
            return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, OSError):
            return str(ts)

    def generate_report(self, source_image: Dict, newer_images: List[Dict], cloud_provider: str) -> str:
        lines: List[str] = []
        lines.append("=" * 80)
        lines.append("FREEIPA IMAGE CANDIDATE FINDER REPORT")
        lines.append("=" * 80)
        lines.append("")

        lines.append("SOURCE IMAGE:")
        lines.append(f"  UUID: {source_image.get('uuid', 'N/A')}")
        lines.append(f"  Date: {source_image.get('date', 'N/A')}")
        lines.append(f"  Created: {self.format_timestamp(self.get_image_timestamp(source_image))}")
        lines.append(f"  OS: {source_image.get('os', 'N/A')}")
        lines.append(f"  OS Type: {source_image.get('os_type', 'N/A')}")
        if 'package-versions' in source_image:
            lines.append("  Package Versions:")
            for pkg, ver in list(source_image.get('package-versions', {}).items())[:5]:
                lines.append(f"    {pkg}: {ver}")

        lines.append("")

        if newer_images:
            lines.append(f"CANDIDATE IMAGES FOR {cloud_provider.upper()} ({len(newer_images)} found):")
            lines.append("-" * 60)
            for idx, image in enumerate(newer_images[:1], 1):
                lines.append("")
                lines.append(f"Image {idx}:")
                lines.append(f"  UUID: {image.get('uuid', 'N/A')}")
                lines.append(f"  Date: {image.get('date', 'N/A')}")
                lines.append(f"  Created: {self.format_timestamp(self.get_image_timestamp(image))}")
                lines.append(f"  OS: {image.get('os', 'N/A')}")
                lines.append(f"  OS Type: {image.get('os_type', 'N/A')}")

                provider_images = image.get('images', {}).get(cloud_provider, {})
                if cloud_provider == 'aws':
                    lines.append(f"  AWS Regions: {len(provider_images)} regions available")
                    for region, ami in list(provider_images.items())[:5]:
                        lines.append(f"    {region}: {ami}")
                    if len(provider_images) > 5:
                        lines.append(f"    ... and {len(provider_images) - 5} more regions")
                elif cloud_provider == 'azure':
                    lines.append(f"  Azure Regions: {len(provider_images)} regions available")
                    for region, vhd in list(provider_images.items())[:5]:
                        lines.append(f"    {region}: {str(vhd)[:50]}...")
                    if len(provider_images) > 5:
                        lines.append(f"    ... and {len(provider_images) - 5} more regions")
                elif cloud_provider == 'gcp':
                    lines.append(f"  GCP Regions: {len(provider_images)} regions available")
                    for region, image_name in list(provider_images.items())[:5]:
                        lines.append(f"    {region}: {image_name}")
                    if len(provider_images) > 5:
                        lines.append(f"    ... and {len(provider_images) - 5} more regions")
        else:
            lines.append(f"No newer images found for {cloud_provider.upper()}")

        lines.append("")
        lines.append("=" * 80)
        return "\n".join(lines)

    def _create_base_row(self, image: Dict, image_type: str, cloud_provider: str) -> Dict:
        pkg_versions = image.get('package-versions', {})
        if pkg_versions:
            package_list = [f"{k}: {v}" for k, v in pkg_versions.items()]
            pkg_str = "; ".join(package_list)
        else:
            pkg_str = 'N/A'

        return {
            'Image_Type': image_type,
            'UUID': image.get('uuid', 'N/A'),
            'Date': image.get('date', 'N/A'),
            'Created': self.format_timestamp(self.get_image_timestamp(image)),
            'OS': image.get('os', 'N/A'),
            'OS_Type': image.get('os_type', 'N/A'),
            'Cloud_Provider': cloud_provider,
            'Region': 'N/A',
            'Image_ID': 'N/A',
            'Package_Versions': pkg_str,
        }

    def _create_rows_with_regions(self, image: Dict, image_type: str, cloud_provider: str) -> List[Dict]:
        rows: List[Dict] = []
        provider_map = image.get('images', {}).get(cloud_provider, {})
        if provider_map:
            for region, image_id in provider_map.items():
                row = self._create_base_row(image, image_type, cloud_provider)
                row['Region'] = region
                row['Image_ID'] = image_id
                rows.append(row)
        else:
            rows.append(self._create_base_row(image, image_type, cloud_provider))
        return rows

    def generate_csv_report(
        self,
        source_image: Dict,
        newer_images: List[Dict],
        cloud_provider: str,
        output_file: Optional[str] = None,
        output_folder: Optional[str] = None
    ) -> str:
        import os
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not output_folder:
            out_dir = f"/tmp/freeipa_image_{timestamp}"
        else:
            out_dir = f"{output_folder}_{timestamp}"
        os.makedirs(out_dir, exist_ok=True)

        if not output_file:
            output_file = f"freeipa_image_candidates_{cloud_provider}_{timestamp}.csv"

        out_path = os.path.join(out_dir, output_file)
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            headers = [
                'Image_Type', 'UUID', 'Date', 'Created', 'OS', 'OS_Type',
                'Cloud_Provider', 'Region', 'Image_ID', 'Package_Versions'
            ]
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()

            # Source row (no per-region mapping recorded for the source specifically)
            src_row = self._create_base_row(source_image, 'SOURCE', cloud_provider)
            writer.writerow(src_row)

            for image in newer_images:
                for row in self._create_rows_with_regions(image, 'CANDIDATE', cloud_provider):
                    writer.writerow(row)

        return out_path

    def analyze(
        self,
        source_uuid: str,
        cloud_provider: str,
        allow_major_os_upgrade: bool,
        csv_output: Optional[str] = None,
        newer_limit: Optional[int] = None,
        output_folder: Optional[str] = None,
    ) -> bool:
        if not self.fetch_catalog():
            return False

        source_image = self.find_source_image(source_uuid)
        if not source_image:
            print(f"✗ Source image with UUID {source_uuid} not found in catalog")
            return False

        newer_images = self.find_newer_images(source_image, cloud_provider, allow_major_os_upgrade)
        total_found = len(newer_images)
        if newer_limit and newer_limit > 0:
            newer_images = newer_images[:newer_limit]

        print(f"✓ Found {len(newer_images)} FreeIPA image candidates (of {total_found} available) for {cloud_provider}")

        report = self.generate_report(source_image, newer_images, cloud_provider)
        print("\n" + report)

        csv_file = self.generate_csv_report(source_image, newer_images, cloud_provider, csv_output, output_folder)
        print(f"✓ CSV report generated: {csv_file}")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Find FreeIPA image candidates for Cloudera Environments (filters by provider and OS compatibility)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python freeipa_image_candidate_finder.py --source-imageId 81851893-8340-411d-afb7-e1b55107fb10 --cloud-provider aws
  python freeipa_image_candidate_finder.py --source-imageId 81851893-8340-411d-afb7-e1b55107fb10 --cloud-provider azure --allow-major-os-upgrade
  python freeipa_image_candidate_finder.py --source-imageId 81851893-8340-411d-afb7-e1b55107fb10 --cloud-provider aws --newer 3 --csv-output ipa.csv
  python freeipa_image_candidate_finder.py --source-imageId 81851893-8340-411d-afb7-e1b55107fb10 --cloud-provider gcp --catalog-url https://cloudbreak-imagecatalog.s3.amazonaws.com/v3-prod-freeipa-image-catalog.json
        """
    )

    parser.add_argument('--source-imageId', required=True, help='Source FreeIPA image UUID to analyze')
    parser.add_argument('--cloud-provider', required=True, choices=['aws', 'azure', 'gcp'], help='Target cloud provider')
    parser.add_argument('--catalog-url', default="https://cloudbreak-imagecatalog.s3.amazonaws.com/v3-prod-freeipa-image-catalog.json", help='Custom FreeIPA catalog URL (optional)')
    parser.add_argument('--csv-output', help='Custom CSV output filename (optional)')
    parser.add_argument('--newer', type=int, help='Limit the number of newer images to show (e.g., --newer 3)')
    parser.add_argument('--output-folder', help='Output folder for CSV report (will append _<timestamp> to folder name)')
    parser.add_argument('--allow-major-os-upgrade', action='store_true', help='Allow OS family/major upgrades (e.g., redhat7 -> redhat8)')

    args = parser.parse_args()

    if not args.source_imageId or len(args.source_imageId) != 36:
        print("✗ Invalid UUID format. UUID should be 36 characters long.")
        sys.exit(1)

    finder = FreeIPAImageCandidateFinder(args.catalog_url)
    ok = finder.analyze(
        source_uuid=args.source_imageId,
        cloud_provider=args.cloud_provider,
        allow_major_os_upgrade=args.allow_major_os_upgrade,
        csv_output=args.csv_output,
        newer_limit=args.newer,
        output_folder=args.output_folder,
    )
    if ok:
        print("\n✓ FreeIPA image candidate search completed successfully")
    else:
        print("\n✗ FreeIPA image candidate search failed")
        sys.exit(1)


if __name__ == "__main__":
    main()


