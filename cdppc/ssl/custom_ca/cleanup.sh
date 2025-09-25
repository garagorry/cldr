#!/bin/bash
# Cleanup script for Custom Certificate Authority Generator
# Removes virtual environment and generated files

# Default values
VENV_DIR=""
CLEAN_CERTS=false
HELP=false

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -v, --venv-dir DIR     Specify virtual environment directory to clean"
    echo "  -c, --clean-certs      Also remove generated certificate directories"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                     # Clean default venv (./venv)"
    echo "  $0 --clean-certs       # Clean venv and certificate directories"
    echo "  $0 --venv-dir /path/to/venv  # Clean specific venv location"
    echo ""
    echo "Default virtual environment location: ./venv"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--venv-dir)
            VENV_DIR="$2"
            shift 2
            ;;
        -c|--clean-certs)
            CLEAN_CERTS=true
            shift
            ;;
        -h|--help)
            HELP=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Show help if requested
if [ "$HELP" = true ]; then
    show_usage
    exit 0
fi

echo "Cleaning Custom Certificate Authority Generator..."
echo "================================================"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set default venv directory if not specified
if [ -z "$VENV_DIR" ]; then
    VENV_DIR="$SCRIPT_DIR/venv"
fi

# Convert relative path to absolute path
if [[ "$VENV_DIR" != /* ]]; then
    VENV_DIR="$SCRIPT_DIR/$VENV_DIR"
fi

# Clean virtual environment
if [ -d "$VENV_DIR" ]; then
    echo "Removing virtual environment at: $VENV_DIR"
    rm -rf "$VENV_DIR"
    echo "✓ Virtual environment removed"
else
    echo "No virtual environment found at: $VENV_DIR"
fi

# Clean certificate directories if requested
if [ "$CLEAN_CERTS" = true ]; then
    CERTS_DIR="$SCRIPT_DIR/certs"
    if [ -d "$CERTS_DIR" ]; then
        echo "Removing certificate directories at: $CERTS_DIR"
        rm -rf "$CERTS_DIR"
        echo "✓ Certificate directories removed"
    else
        echo "No certificate directories found at: $CERTS_DIR"
    fi
fi

# Clean wrapper scripts
WRAPPER_SCRIPTS=("run_ca.sh" "deactivate_env.sh")
for script in "${WRAPPER_SCRIPTS[@]}"; do
    if [ -f "$SCRIPT_DIR/$script" ]; then
        echo "Removing wrapper script: $script"
        rm -f "$SCRIPT_DIR/$script"
        echo "✓ $script removed"
    fi
done

echo ""
echo "Cleanup complete!"
echo "================="
echo ""
echo "To reinstall, run:"
echo "  ./install.sh"
echo ""
echo "To install with custom options, run:"
echo "  ./install.sh --help"
