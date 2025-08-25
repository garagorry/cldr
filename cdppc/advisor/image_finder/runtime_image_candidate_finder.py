#!/usr/bin/env python3
"""
Cloudbreak Runtime Image Candidate Finder

This script analyzes the Cloudbreak image catalog to find runtime image candidates based on:
- Source image ID (UUID)
- Cloud provider (aws, azure, gcp)
- Image creation/published dates

The script identifies newer images that can be used as base images for creating custom runtime images
or for external tools to copy and prepare custom images.

Usage:
    python runtime_image_candidate_finder.py --source-imageId <uuid> --cloud-provider <aws|azure|gcp>
"""

import argparse
import json
import requests
import csv
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import sys


class RuntimeImageCandidateFinder:
    def __init__(self, catalog_url: str = "https://cloudbreak-imagecatalog.s3.amazonaws.com/v3-prod-cb-image-catalog.json"):
        self.catalog_url = catalog_url
        self.catalog_data = None
        
    def fetch_catalog(self) -> bool:
        """Fetch the image catalog from the URL"""
        try:
            print(f"Fetching image catalog from: {self.catalog_url}")
            response = requests.get(self.catalog_url, timeout=30)
            response.raise_for_status()
            self.catalog_data = response.json()
            print("✓ Successfully fetched image catalog")
            return True
        except requests.RequestException as e:
            print(f"✗ Error fetching catalog: {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"✗ Error parsing catalog JSON: {e}")
            return False
    
    def find_source_image(self, source_uuid: str) -> Optional[Dict]:
        """Find the source image in the catalog"""
        if not self.catalog_data:
            return None
            
        # Search in base-images
        if 'images' in self.catalog_data and 'base-images' in self.catalog_data['images']:
            for base_image in self.catalog_data['images']['base-images']:
                if base_image.get('uuid') == source_uuid:
                    return base_image
        
        # Search in versions - handle both direct images and nested structures
        if 'versions' in self.catalog_data:
            for i, version in enumerate(self.catalog_data['versions']):
                # Skip if version is not a dictionary
                if not isinstance(version, dict):
                    continue
                
                # Check if version has direct images
                if 'images' in version:
                    for image in version['images']:
                        if isinstance(image, dict) and image.get('uuid') == source_uuid:
                            return image
                
                # Check if version itself is an image
                if version.get('uuid') == source_uuid:
                    return version
        
        # Search recursively in the entire catalog structure
        found_image = self._search_recursively(self.catalog_data, source_uuid)
        return found_image
    
    def _search_recursively(self, data, target_uuid: str) -> Optional[Dict]:
        """Recursively search for an image with the target UUID"""
        if isinstance(data, dict):
            # Check if this dict is the target image
            if data.get('uuid') == target_uuid:
                return data
            
            # Recursively search in all values
            for key, value in data.items():
                result = self._search_recursively(value, target_uuid)
                if result:
                    return result
        elif isinstance(data, list):
            # Recursively search in all list items
            for item in data:
                result = self._search_recursively(item, target_uuid)
                if result:
                    return result
        
        return None
    
    def get_image_timestamp(self, image: Dict) -> int:
        """Get the timestamp for comparison (prefer created, fallback to published)"""
        return image.get('created', image.get('published', 0))
    
    def find_newer_images(self, source_image: Dict, cloud_provider: str, source_timestamp: int, source_architecture: str) -> List[Dict]:
        """Find newer images for the specified cloud provider"""
        newer_images = []
        
        if not self.catalog_data:
            return newer_images
        
        # Search in base-images
        if 'images' in self.catalog_data and 'base-images' in self.catalog_data['images']:
            for base_image in self.catalog_data['images']['base-images']:
                if self._is_newer_image(base_image, source_timestamp, cloud_provider, source_architecture):
                    newer_images.append(base_image)
        
        # Search in versions - handle both direct images and nested structures
        if 'versions' in self.catalog_data:
            for version in self.catalog_data['versions']:
                # Skip if version is not a dictionary
                if not isinstance(version, dict):
                    continue
                
                # Check if version has direct images
                if 'images' in version:
                    for image in version['images']:
                        if isinstance(image, dict) and self._is_newer_image(image, source_timestamp, cloud_provider, source_architecture):
                            newer_images.append(image)
                
                # Check if version itself is an image
                if self._is_newer_image(version, source_timestamp, cloud_provider, source_architecture):
                    newer_images.append(version)
        
        # Also search recursively for any images we might have missed
        all_images = self._find_all_images_recursively(self.catalog_data)
        for image in all_images:
            if self._is_newer_image(image, source_timestamp, cloud_provider, source_architecture):
                # Avoid duplicates
                if not any(existing.get('uuid') == image.get('uuid') for existing in newer_images):
                    newer_images.append(image)
        
        # Sort by timestamp (newest first)
        newer_images.sort(key=lambda x: self.get_image_timestamp(x), reverse=True)
        return newer_images
    
    def _find_all_images_recursively(self, data) -> List[Dict]:
        """Recursively find all image objects in the catalog"""
        images = []
        
        if isinstance(data, dict):
            # Check if this dict is an image (has uuid and images fields)
            if data.get('uuid') and 'images' in data:
                images.append(data)
            
            # Recursively search in all values
            for key, value in data.items():
                images.extend(self._find_all_images_recursively(value))
        elif isinstance(data, list):
            # Recursively search in all list items
            for item in data:
                images.extend(self._find_all_images_recursively(item))
        
        return images
    
    def _is_newer_image(self, image: Dict, source_timestamp: int, cloud_provider: str, source_architecture: str) -> bool:
        """Check if an image is newer and supports the specified cloud provider and architecture"""
        image_timestamp = self.get_image_timestamp(image)
        
        # Must be newer than source
        if image_timestamp <= source_timestamp:
            return False
        
        # Must have the same architecture as source
        if image.get('architecture') != source_architecture:
            return False
        
        # Must support the specified cloud provider
        if 'images' not in image:
            return False
            
        # Check if cloud provider is supported
        if cloud_provider == 'aws':
            return 'aws' in image['images']
        elif cloud_provider == 'azure':
            return 'azure' in image['images']
        elif cloud_provider == 'gcp':
            return 'gcp' in image['images']
        
        return False
    
    def format_timestamp(self, timestamp: int) -> str:
        """Convert Unix timestamp to readable date"""
        try:
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, OSError):
            return str(timestamp)
    
    def generate_report(self, source_image: Dict, newer_images: List[Dict], cloud_provider: str) -> str:
        """Generate a detailed report of the analysis"""
        report = []
        report.append("=" * 80)
        report.append("CLOUDBREAK RUNTIME IMAGE CANDIDATE FINDER REPORT")
        report.append("=" * 80)
        report.append("")
        
        # Source image info
        report.append("SOURCE IMAGE:")
        report.append(f"  UUID: {source_image.get('uuid', 'N/A')}")
        report.append(f"  Date: {source_image.get('date', 'N/A')}")
        report.append(f"  Created: {self.format_timestamp(source_image.get('created', 0))}")
        report.append(f"  Published: {self.format_timestamp(source_image.get('published', 0))}")
        report.append(f"  OS: {source_image.get('os', 'N/A')}")
        report.append(f"  OS Type: {source_image.get('os_type', 'N/A')}")
        report.append(f"  Architecture: {source_image.get('architecture', 'N/A')}")
        
        # Repository version information for source image
        if 'stack-details' in source_image and 'repo' in source_image['stack-details']:
            repo_info = source_image['stack-details']['repo']
            if 'stack' in repo_info and 'repository-version' in repo_info['stack']:
                report.append(f"  Repository Version: {repo_info['stack']['repository-version']}")
            if 'stack' in repo_info and 'repoid' in repo_info['stack']:
                report.append(f"  Repository ID: {repo_info['stack']['repoid']}")
        elif 'version' in source_image:
            report.append(f"  Version: {source_image['version']}")
        if 'build-number' in source_image:
            report.append(f"  Build Number: {source_image['build-number']}")
        
        report.append("")
        
        # Candidate images
        if newer_images:
            report.append(f"CANDIDATE IMAGES FOR {cloud_provider.upper()} ({len(newer_images)} found):")
            report.append("-" * 60)
            
            for i, image in enumerate(newer_images, 1):
                report.append(f"")
                report.append(f"Image {i}:")
                report.append(f"  UUID: {image.get('uuid', 'N/A')}")
                report.append(f"  Date: {image.get('date', 'N/A')}")
                report.append(f"  Created: {self.format_timestamp(image.get('created', 0))}")
                report.append(f"  Published: {self.format_timestamp(image.get('published', 0))}")
                report.append(f"  OS: {image.get('os', 'N/A')}")
                report.append(f"  OS Type: {image.get('os_type', 'N/A')}")
                report.append(f"  Architecture: {image.get('architecture', 'N/A')}")
                
                # Cloud provider specific details
                if 'images' in image and cloud_provider in image['images']:
                    cloud_images = image['images'][cloud_provider]
                    if cloud_provider == 'aws':
                        report.append(f"  AWS Regions: {len(cloud_images)} regions available")
                        for region, ami in list(cloud_images.items())[:5]:  # Show first 5 regions
                            report.append(f"    {region}: {ami}")
                        if len(cloud_images) > 5:
                            report.append(f"    ... and {len(cloud_images) - 5} more regions")
                    elif cloud_provider == 'azure':
                        report.append(f"  Azure Regions: {len(cloud_images)} regions available")
                        for region, vhd_url in list(cloud_images.items())[:5]:  # Show first 5 regions
                            report.append(f"    {region}: {vhd_url[:50]}...")
                        if len(cloud_images) > 5:
                            report.append(f"    ... and {len(cloud_images) - 5} more regions")
                    elif cloud_provider == 'gcp':
                        report.append(f"  GCP Regions: {len(cloud_images)} regions available")
                        for region, image_name in list(cloud_images.items())[:5]:  # Show first 5 regions
                            report.append(f"    {region}: {image_name}")
                        if len(cloud_images) > 5:
                            report.append(f"    ... and {len(cloud_images) - 5} more regions")
                
                # Package versions if available
                if 'package-versions' in image:
                    report.append(f"  Package Versions:")
                    for pkg, version in list(image['package-versions'].items())[:5]:  # Show first 5 packages
                        report.append(f"    {pkg}: {version}")
                    if len(image['package-versions']) > 5:
                        report.append(f"    ... and {len(image['package-versions']) - 5} more packages")
                
                # Repository version information
                if 'stack-details' in image and 'repo' in image['stack-details']:
                    repo_info = image['stack-details']['repo']
                    if 'stack' in repo_info and 'repository-version' in repo_info['stack']:
                        report.append(f"  Repository Version: {repo_info['stack']['repository-version']}")
                    if 'stack' in repo_info and 'repoid' in repo_info['stack']:
                        report.append(f"  Repository ID: {repo_info['stack']['repoid']}")
                elif 'version' in image:
                    report.append(f"  Version: {image['version']}")
                if 'build-number' in image:
                    report.append(f"  Build Number: {image['build-number']}")
        else:
            report.append(f"No newer images found for {cloud_provider.upper()}")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def generate_csv_report(self, source_image: Dict, newer_images: List[Dict], cloud_provider: str, output_file: str = None, output_folder: str = None) -> str:
        """Generate a CSV report with all image details including all regions"""
        # Determine output folder
        if not output_folder:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_folder = f"/tmp/runtime_image_{timestamp}"
        else:
            # Append timestamp to custom output folder
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_folder = f"{output_folder}_{timestamp}"
        
        # Create output folder if it doesn't exist
        import os
        os.makedirs(output_folder, exist_ok=True)
        
        # Determine output filename
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"runtime_image_candidates_{cloud_provider}_{timestamp}.csv"
        
        # Combine folder and filename
        full_output_path = os.path.join(output_folder, output_file)
        
        with open(full_output_path, 'w', newline='', encoding='utf-8') as csvfile:
            # Define CSV headers
            headers = [
                'Image_Type', 'UUID', 'Date', 'Created', 'Published', 'OS', 'OS_Type', 'Architecture',
                'Repository_Version', 'Repository_ID', 'Build_Number', 'Version',
                'Cloud_Provider', 'Region', 'Image_ID', 'Package_Versions'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            
            # Write source image row
            source_row = self._create_image_row(source_image, 'SOURCE', cloud_provider)
            writer.writerow(source_row)
            
            # Write candidate images rows
            for image in newer_images:
                image_rows = self._create_image_rows(image, 'CANDIDATE', cloud_provider)
                for row in image_rows:
                    writer.writerow(row)
        
        return full_output_path
    
    def _create_image_row(self, image: Dict, image_type: str, cloud_provider: str) -> Dict:
        """Create a single CSV row for an image"""
        # Get repository version info
        repo_version = 'N/A'
        repo_id = 'N/A'
        if 'stack-details' in image and 'repo' in image['stack-details']:
            repo_info = image['stack-details']['repo']
            if 'stack' in repo_info and 'repository-version' in repo_info['stack']:
                repo_version = repo_info['stack']['repository-version']
            if 'stack' in repo_info and 'repoid' in repo_info['stack']:
                repo_id = repo_info['stack']['repoid']
        elif 'version' in image:
            repo_version = image['version']
        
        # Get package versions list
        package_versions = image.get('package-versions', {})
        if package_versions:
            # Convert package versions dict to a formatted string
            package_list = []
            for pkg, version in package_versions.items():
                package_list.append(f"{pkg}: {version}")
            package_versions_str = "; ".join(package_list)
        else:
            package_versions_str = 'N/A'
        
        # Create base row
        row = {
            'Image_Type': image_type,
            'UUID': image.get('uuid', 'N/A'),
            'Date': image.get('date', 'N/A'),
            'Created': self.format_timestamp(image.get('created', 0)),
            'Published': self.format_timestamp(image.get('published', 0)),
            'OS': image.get('os', 'N/A'),
            'OS_Type': image.get('os_type', 'N/A'),
            'Architecture': image.get('architecture', 'N/A'),
            'Repository_Version': repo_version,
            'Repository_ID': repo_id,
            'Build_Number': image.get('build-number', 'N/A'),
            'Version': image.get('version', 'N/A'),
            'Cloud_Provider': cloud_provider,
            'Region': 'N/A',
            'Image_ID': 'N/A',
            'Package_Versions': package_versions_str
        }
        
        return row
    
    def _create_image_rows(self, image: Dict, image_type: str, cloud_provider: str) -> List[Dict]:
        """Create CSV rows for an image with all its regions"""
        rows = []
        
        if 'images' in image and cloud_provider in image['images']:
            cloud_images = image['images'][cloud_provider]
            
            # Create one row per region
            for region, image_id in cloud_images.items():
                base_row = self._create_image_row(image, image_type, cloud_provider)
                base_row['Region'] = region
                base_row['Image_ID'] = image_id
                rows.append(base_row)
        else:
            # If no cloud provider images, create one row with N/A values
            base_row = self._create_image_row(image, image_type, cloud_provider)
            rows.append(base_row)
        
        return rows
    
    def analyze(self, source_uuid: str, cloud_provider: str, csv_output: str = None, newer_limit: int = None, output_folder: str = None) -> bool:
        """Main analysis method"""
        # Fetch catalog
        if not self.fetch_catalog():
            return False
        
        # Find source image
        source_image = self.find_source_image(source_uuid)
        
        if not source_image:
            print(f"✗ Source image with UUID {source_uuid} not found in catalog")
            return False
        
        # Get source timestamp and architecture
        source_timestamp = self.get_image_timestamp(source_image)
        source_architecture = source_image.get('architecture', 'unknown')
        
        # Find newer images
        newer_images = self.find_newer_images(source_image, cloud_provider, source_timestamp, source_architecture)
        
        # Store original count before limiting
        original_count = len(newer_images)
        
        # Apply newer limit if specified
        if newer_limit and newer_limit > 0:
            newer_images = newer_images[:newer_limit]
        
        print(f"✓ Found {len(newer_images)} runtime image candidates with {source_architecture} architecture")
        
        # Generate and display report (show only latest image by default, or when newer_limit > 1)
        if not newer_limit or newer_limit > 1:
            # For display, show only the latest image
            display_images = newer_images[:1] if newer_images else []
            report = self.generate_report(source_image, display_images, cloud_provider)
            print("\n" + report)
            if newer_limit and newer_limit > 1:
                print(f"Note: Showing latest image only. CSV contains the {len(newer_images)} limited candidate images.")
            else:
                print(f"Note: Showing latest image only. CSV contains all {original_count} available candidate images.")
        else:
            # Show all images in report (when newer_limit = 1)
            report = self.generate_report(source_image, newer_images, cloud_provider)
            print("\n" + report)
        
        # Generate CSV report (always include all images)
        csv_file = self.generate_csv_report(source_image, newer_images, cloud_provider, csv_output, output_folder)
        print(f"✓ CSV report generated: {csv_file}")
        
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Find Cloudbreak runtime image candidates for custom image creation (filters by same architecture)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python runtime_image_candidate_finder.py --source-imageId d60091f7-06e4-4042-8dbc-13c2cdc0dd5c --cloud-provider aws
  python runtime_image_candidate_finder.py --source-imageId d60091f7-06e4-4042-8dbc-13c2cdc0dd5c --cloud-provider azure
  python runtime_image_candidate_finder.py --source-imageId d60091f7-06e4-4042-8dbc-13c2cdc0dd5c --cloud-provider gcp
  python runtime_image_candidate_finder.py --source-imageId d60091f7-06e4-4042-8dbc-13c2cdc0dd5c --cloud-provider aws --csv-output my_report.csv
  python runtime_image_candidate_finder.py --source-imageId d60091f7-06e4-4042-8dbc-13c2cdc0dd5c --cloud-provider aws --newer 3
  python runtime_image_candidate_finder.py --source-imageId d60091f7-06e4-4042-8dbc-13c2cdc0dd5c --cloud-provider aws --output-folder ./reports
        """
    )
    
    parser.add_argument(
        '--source-imageId',
        required=True,
        help='Source image UUID to analyze'
    )
    
    parser.add_argument(
        '--cloud-provider',
        required=True,
        choices=['aws', 'azure', 'gcp'],
        help='Target cloud provider for upgrade analysis'
    )
    
    parser.add_argument(
        '--catalog-url',
        default="https://cloudbreak-imagecatalog.s3.amazonaws.com/v3-prod-cb-image-catalog.json",
        help='Custom image catalog URL (optional)'
    )
    
    parser.add_argument(
        '--csv-output',
        help='Custom CSV output filename (optional)'
    )
    
    parser.add_argument(
        '--newer',
        type=int,
        help='Limit the number of newer images to show (e.g., --newer 3 for latest 3 images)'
    )
    
    parser.add_argument(
        '--output-folder',
        help='Output folder for CSV report (will append _<timestamp> to folder name)'
    )
    
    args = parser.parse_args()
    
    # Validate UUID format (basic check)
    if not args.source_imageId or len(args.source_imageId) != 36:
        print("✗ Invalid UUID format. UUID should be 36 characters long.")
        sys.exit(1)
    
    # Create candidate finder and run analysis
    candidate_finder = RuntimeImageCandidateFinder(args.catalog_url)
    
    if candidate_finder.analyze(args.source_imageId, args.cloud_provider, args.csv_output, args.newer, args.output_folder):
        print("\n✓ Runtime image candidate search completed successfully")
    else:
        print("\n✗ Runtime image candidate search failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
