# FreeIPA Image Candidate Finder

A Python tool for analyzing the FreeIPA image catalog to find newer image candidates based on source image UUID, cloud provider, and OS compatibility. This tool helps identify suitable base images for creating or updating FreeIPA images used by Cloudera Environments Service.

## Features

- **Source Image Analysis**: Find and analyze existing FreeIPA images by UUID
- **Cloud Provider Filtering**: Filter candidates by target cloud provider (AWS, Azure, GCP)
- **OS Compatibility**: Check OS family and version compatibility with configurable upgrade policies
- **Date-based Filtering**: Find newer images based on creation/published timestamps
- **Comprehensive Reporting**: Generate both human-readable and CSV reports
- **Flexible Output**: Customizable output locations and formats

## Requirements

- Python 3.6+
- `requests` library for HTTP requests

## Installation

```bash
pip install requests
```

## Usage

### Basic Usage

```bash
python freeipa_image_candidate_finder.py --source-imageId <uuid> --cloud-provider <aws|azure|gcp>
```

### Examples

**Find AWS candidates for a specific image:**

```bash
python freeipa_image_candidate_finder.py --source-imageId 81851893-8340-411d-afb7-e1b55107fb10 --cloud-provider aws
```

**Allow major OS upgrades (e.g., RHEL 7 → RHEL 8):**

```bash
python freeipa_image_candidate_finder.py --source-imageId 81851893-8340-411d-afb7-e1b55107fb10 --cloud-provider azure --allow-major-os-upgrade
```

**Limit results and generate custom CSV:**

```bash
python freeipa_image_candidate_finder.py --source-imageId 81851893-8340-411d-afb7-e1b55107fb10 --cloud-provider aws --newer 3 --csv-output ipa_candidates.csv
```

**Use custom catalog URL:**

```bash
python freeipa_image_candidate_finder.py --source-imageId 81851893-8340-411d-afb7-e1b55107fb10 --cloud-provider gcp --catalog-url https://custom-catalog.example.com/freeipa-catalog.json
```

**Specify output folder:**

```bash
python freeipa_image_candidate_finder.py --source-imageId 81851893-8340-411d-afb7-e1b55107fb10 --cloud-provider aws --output-folder /path/to/reports
```

## Command Line Options

| Option                     | Required | Description                                              |
| -------------------------- | -------- | -------------------------------------------------------- |
| `--source-imageId`         | Yes      | Source FreeIPA image UUID to analyze (36 characters)     |
| `--cloud-provider`         | Yes      | Target cloud provider: `aws`, `azure`, or `gcp`          |
| `--catalog-url`            | No       | Custom FreeIPA catalog URL (default: production catalog) |
| `--csv-output`             | No       | Custom CSV output filename                               |
| `--newer`                  | No       | Limit number of newer images to show (e.g., `--newer 3`) |
| `--output-folder`          | No       | Output folder for CSV report (appends timestamp)         |
| `--allow-major-os-upgrade` | No       | Allow OS family/major upgrades (e.g., redhat7 → redhat8) |

## Output

### Console Report

The tool generates a detailed console report showing:

- **Source Image Information**: UUID, date, OS, package versions
- **Candidate Images**: Newer compatible images with region mappings
- **Cloud Provider Details**: Region-specific image IDs for each provider

### CSV Report

A comprehensive CSV file is automatically generated with the following columns:

- `Image_Type`: SOURCE or CANDIDATE
- `UUID`: Image UUID
- `Date`: Image date string
- `Created`: Formatted creation timestamp
- `OS`: Operating system
- `OS_Type`: OS type specification
- `Cloud_Provider`: Target cloud provider
- `Region`: Cloud region
- `Image_ID`: Region-specific image ID (AMI, VHD, etc.)
- `Package_Versions`: Package version information

### Output Location

- **Default**: `/tmp/freeipa_image_<timestamp>/`
- **Custom**: `<output-folder>_<timestamp>/`

## OS Compatibility Logic

### Default Behavior

- Images must have the same OS family and major version
- Examples: `redhat7` matches `redhat7`, `centos7` matches `centos7`

### With Major OS Upgrade (`--allow-major-os-upgrade`)

- Allows upgrades within the same OS family
- Supports cross-family compatibility (CentOS ↔ RHEL)
- Examples: `redhat7` → `redhat8`, `centos7` → `rhel8`

### Supported OS Families

- Red Hat Enterprise Linux (RHEL)
- CentOS
- Compatible derivatives

## Image Timestamp Handling

The tool handles various timestamp formats:

1. **Numeric timestamps**: Unix epoch seconds from `created` field
2. **Date strings**: Parsed from `date` field in formats:
   - `YYYY-MM-DD`
   - `YYYY/MM/DD`
   - `YYYY-MM-DD HH:MM:SS`
3. **Fallback**: Uses `0` if no valid timestamp found

## Error Handling

- **Network Issues**: Graceful handling of catalog fetch failures
- **Invalid UUIDs**: Validation of 36-character UUID format
- **JSON Parsing**: Error handling for malformed catalog data
- **Missing Images**: Clear reporting when source image not found

## Use Cases

1. **Image Migration**: Find newer base images for existing FreeIPA deployments
2. **Version Updates**: Identify latest images for OS or package updates
3. **Cloud Migration**: Find equivalent images across different cloud providers
4. **Compliance**: Ensure OS compatibility for security and compliance requirements
5. **Cost Optimization**: Evaluate newer images that might offer better performance or features

## Integration

This tool is designed to work with:

- Cloudera Environments Service
- FreeIPA image catalogs
- Multi-cloud deployments (AWS, Azure, GCP)
- CI/CD pipelines for automated image updates

## Troubleshooting

### Common Issues

**"Source image not found"**

- Verify the UUID is correct and exists in the catalog
- Check if using the correct catalog URL

**"No newer images found"**

- Try enabling `--allow-major-os-upgrade` for broader compatibility
- Verify the source image timestamp is valid
- Check if newer images exist for the target cloud provider

**"Error fetching catalog"**

- Verify network connectivity
- Check if the catalog URL is accessible
- Try with a different catalog URL if available

### Debug Information

The tool provides verbose output including:

- Catalog fetch status
- Source image details
- Number of candidates found
- Output file locations

## License

This tool is part of the Cloudera Data Platform (CDP) utilities and follows the same licensing terms as the CDP software.

## Contributing

For issues, feature requests, or contributions, please refer to the internal Cloudera development processes and guidelines.
