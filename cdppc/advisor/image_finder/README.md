# Cloudbreak Runtime Image Candidate Finder

This tool analyzes the Cloudbreak image catalog to find runtime image candidates based on a source image ID and cloud provider. It helps identify newer images that can be used as base images for creating custom runtime images or for external tools to copy and prepare custom images.

## Features

- **Source Image Analysis**: Finds and analyzes the specified source image by UUID
- **Cloud Provider Support**: Supports AWS, Azure, and GCP image analysis
- **Date Comparison**: Compares images based on `created` and `published` timestamps
- **Comprehensive Reporting**: Generates detailed reports showing runtime image candidates
- **Region Information**: Displays available regions and image IDs for each cloud provider
- **Architecture Filtering**: Ensures candidates have the same architecture as the source image
- **CSV Export**: Generates CSV reports for external tool integration

## Installation

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Usage

```bash
python runtime_image_candidate_finder.py --source-imageId <uuid> --cloud-provider <aws|azure|gcp>
```

### Examples

**Find AWS runtime image candidates:**

```bash
python runtime_image_candidate_finder.py --source-imageId d60091f7-06e4-4042-8dbc-13c2cdc0dd5c --cloud-provider aws
```

**Find Azure runtime image candidates:**

```bash
python runtime_image_candidate_finder.py --source-imageId d60091f7-06e4-4042-8dbc-13c2cdc0dd5c --cloud-provider azure
```

**Find GCP runtime image candidates:**

```bash
python runtime_image_candidate_finder.py --source-imageId d60091f7-06e4-4042-8dbc-13c2cdc0dd5c --cloud-provider gcp
```

**Specify custom output folder:**

```bash
python runtime_image_candidate_finder.py --source-imageId d60091f7-06e4-4042-8dbc-13c2cdc0dd5c --cloud-provider aws --output-folder /path/to/reports
```

**Combine custom output folder and filename:**

```bash
python runtime_image_candidate_finder.py --source-imageId d60091f7-06e4-4042-8dbc-13c2cdc0dd5c --cloud-provider aws --output-folder /path/to/reports --csv-output my_report.csv
```

**Limit to latest 3 images (console shows only latest, CSV contains limited images):**

```bash
python runtime_image_candidate_finder.py --source-imageId d60091f7-06e4-4042-8dbc-13c2cdc0dd5c --cloud-provider aws --newer 3
```

### Command Line Arguments

- `--source-imageId`: **Required**. The UUID of the source image to analyze
- `--cloud-provider`: **Required**. Target cloud provider (`aws`, `azure`, or `gcp`)
- `--catalog-url`: **Optional**. Custom image catalog URL (defaults to the official Cloudbreak catalog)
- `--csv-output`: **Optional**. Custom CSV output filename
- `--newer`: **Optional**. Limit the number of newer images to show (e.g., `--newer 3` for latest 3 images). When not provided or > 1, console report shows only the latest image, but CSV contains all available/limited images.
- `--output-folder`: **Optional**. Output folder for CSV report (will append `_<timestamp>` to folder name)

## Output

The tool generates both a console report and a CSV file:

### Console Report Behavior

- **No `--newer` parameter**: Shows only the latest candidate image with a note that CSV contains all available images
- **`--newer 1`**: Shows the single latest candidate image
- **`--newer > 1`**: Shows only the latest candidate image with a note that CSV contains the limited candidate images

### CSV Report Behavior

The CSV contains all candidate images based on the `--newer` parameter:

- **No `--newer` parameter**: Contains all available candidate images with all regions
- **`--newer 1`**: Contains 1 candidate image with all regions
- **`--newer > 1`**: Contains the limited candidate images with all regions
- **Source image**: Always 1 row with all details
- **Complete data**: Full package versions, repository information, and region-specific image IDs

### Report Content

### Source Image Information

- UUID
- Date
- Created timestamp
- Published timestamp
- OS and OS type

### Runtime Image Candidates Analysis

- UUID of each newer image
- Creation and publication dates
- OS information
- Cloud provider specific details:
  - **AWS**: Region names and AMI IDs
  - **Azure**: Region names and VHD URLs
  - **GCP**: Region names and image names
- Package versions (if available)

## How It Works

1. **Catalog Fetching**: Downloads the latest image catalog from the Cloudbreak S3 bucket
2. **Source Image Search**: Locates the specified source image by UUID in both base-images and versions sections
3. **Architecture Detection**: Identifies the source image architecture (x86_64, arm64, etc.)
4. **Timestamp Comparison**: Compares image timestamps using `created` field (with `published` as fallback)
5. **Architecture Filtering**: Ensures candidate images have the same architecture as the source image
6. **Cloud Provider Filtering**: Ensures candidate images support the specified cloud provider
7. **Report Generation**: Creates a detailed report showing all runtime image candidates

## Example Output

```
================================================================================
CLOUDBREAK RUNTIME IMAGE CANDIDATE FINDER REPORT
================================================================================

SOURCE IMAGE:
  UUID: d60091f7-06e4-4042-8dbc-13c2cdc0dd5c
  Date: 2023-02-28
  Created: 2023-02-28 10:30:26
  Published: 2023-02-28 12:30:47
  OS: centos7
  OS Type: redhat7

RUNTIME IMAGE CANDIDATES FOR AWS (3 found):
------------------------------------------------------------

Image 1:
  UUID: 8b6ea689-5dc7-47ea-bb55-816a4b1d9173
  Date: 2023-03-01
  Created: 2023-03-01 10:30:33
  Published: 2023-03-01 12:30:34
  OS: centos7
  OS Type: redhat7
  AWS Regions: 24 regions available
    us-east-1: ami-0b35cb48f30fef562
    us-west-2: ami-0ff7ec0f576bc07be
    eu-west-1: ami-0c3bf6dfee34f7138
    ap-southeast-1: ami-06ee65023ad734b8a
    ca-central-1: ami-095c3f0f552011109
    ... and 19 more regions
  Package Versions:
    blackbox-exporter: 0.19.0
    cdp-logging-agent: 0.3.6
    cdp-minifi-agent: 1.22.07
    cdp-prometheus: 2.36.2
    cdp-request-signer: 0.2.4
    ... and 8 more packages

================================================================================
```

## Error Handling

The tool handles various error scenarios:

- Network connectivity issues when fetching the catalog
- Invalid JSON responses
- Missing source images
- Invalid UUID formats

## Dependencies

- Python 3.6+
- `requests` library for HTTP operations
- Standard library modules: `argparse`, `json`, `datetime`, `typing`, `sys`

## Output Folder Behavior

The tool automatically creates output folders and manages CSV file placement:

- **Default behavior**: Creates `/tmp/runtime_image_<timestamp>/` folder with auto-generated CSV filename
- **Custom folder**: Automatically appends `_<timestamp>` to the specified `--output-folder` name
- **Custom folder + filename**: Uses timestamped folder with specified `--csv-output` filename
- **Auto-creation**: Output folders are automatically created if they don't exist
- **Timestamp format**: All folder names use format `YYYYMMDD_HHMMSS`

## Notes

- The tool fetches the live catalog from the Cloudbreak S3 bucket, ensuring you always have the latest information
- Image timestamps are compared using Unix timestamps for accurate chronological ordering
- The tool searches both the `base-images` and `versions` sections of the catalog for comprehensive coverage
- Architecture filtering ensures candidates are compatible with your source image
- Cloud provider support is verified before including images in the candidate analysis
- CSV export enables integration with external tools for custom image creation
- Output folders are automatically created and managed for organized file storage
