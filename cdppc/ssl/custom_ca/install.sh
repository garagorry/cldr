#!/bin/bash
# Installation script for Custom Certificate Authority Generator
# Creates and configures a Python virtual environment for isolated execution

# Default values
VENV_DIR=""
CLEAN_VENV=false
HELP=false

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -v, --venv-dir DIR     Specify custom virtual environment directory"
    echo "  -c, --clean            Clean/remove existing virtual environment before installation"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                     # Install with default venv location (./venv)"
    echo "  $0 --clean             # Clean existing venv and reinstall"
    echo "  $0 --venv-dir /path/to/venv  # Install venv in custom location"
    echo "  $0 --clean --venv-dir /path/to/venv  # Clean and install in custom location"
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
        -c|--clean)
            CLEAN_VENV=true
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

echo "Installing Custom Certificate Authority Generator..."
echo "=================================================="

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

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    echo "Please install Python 3 and try again."
    exit 1
fi

# Check if venv module is available
if ! python3 -m venv --help &> /dev/null; then
    echo "Error: Python venv module is required but not available."
    echo "Please install python3-venv package and try again."
    exit 1
fi

echo "Creating Python virtual environment..."
echo "Virtual environment location: $VENV_DIR"

# Handle clean option
if [ "$CLEAN_VENV" = true ]; then
    if [ -d "$VENV_DIR" ]; then
        echo "Cleaning existing virtual environment..."
        rm -rf "$VENV_DIR"
        echo "✓ Existing virtual environment removed"
    else
        echo "No existing virtual environment found to clean"
    fi
elif [ -d "$VENV_DIR" ]; then
    echo "Warning: Virtual environment already exists at $VENV_DIR"
    echo "Use --clean option to remove and recreate it, or specify a different location with --venv-dir"
    echo "Continuing with existing virtual environment..."
fi

# Create virtual environment
python3 -m venv "$VENV_DIR"

if [ $? -ne 0 ]; then
    echo "✗ Failed to create virtual environment"
    exit 1
fi

echo "✓ Virtual environment created successfully"

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

if [ $? -ne 0 ]; then
    echo "✗ Failed to activate virtual environment"
    exit 1
fi

echo "✓ Virtual environment activated"

# Upgrade pip in virtual environment
echo "Upgrading pip in virtual environment..."
python -m pip install --upgrade pip

if [ $? -ne 0 ]; then
    echo "⚠ Warning: Failed to upgrade pip, continuing with existing version"
fi

# Install dependencies
echo "Installing dependencies in virtual environment..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✓ Dependencies installed successfully in virtual environment"
else
    echo "✗ Failed to install dependencies"
    exit 1
fi

# Make scripts executable
chmod +x certificate_authority.py

# Create a wrapper script for easy execution
echo "Creating wrapper script..."
cat > run_ca.sh << EOF
#!/bin/bash
# Wrapper script to run Certificate Authority in virtual environment

SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$VENV_DIR"

# Check if virtual environment exists
if [ ! -d "\$VENV_DIR" ]; then
    echo "Error: Virtual environment not found at \$VENV_DIR"
    echo "Please run ./install.sh first."
    exit 1
fi

# Activate virtual environment
source "\$VENV_DIR/bin/activate"

# Run the certificate authority script with all arguments
python certificate_authority.py "\$@"
EOF

chmod +x run_ca.sh

# Create a deactivate script for convenience
cat > deactivate_env.sh << 'EOF'
#!/bin/bash
# Script to deactivate the virtual environment
deactivate 2>/dev/null || true
echo "Virtual environment deactivated"
EOF

chmod +x deactivate_env.sh

echo ""
echo "Installation complete!"
echo "====================="
echo ""
echo "Virtual environment created at: $VENV_DIR"
echo ""
echo "Usage options:"
echo ""
echo "Option 1 - Use wrapper script (recommended):"
echo "  ./run_ca.sh internal-app.company.com"
echo "  ./run_ca.sh api.internal.company.com --verbose"
echo "  ./run_ca.sh \"*.internal.company.com\" --output-dir /path/to/certs"
echo ""
echo "Option 2 - Manual activation:"
echo "  source $VENV_DIR/bin/activate"
echo "  python certificate_authority.py internal-app.company.com"
echo "  deactivate"
echo ""
echo "Option 3 - Deactivate environment:"
echo "  ./deactivate_env.sh"
echo ""
echo "Management options:"
echo "  ./install.sh --help              # Show installation options"
echo "  ./install.sh --clean             # Clean and reinstall venv"
echo "  ./install.sh --venv-dir /path    # Install venv in custom location"
echo ""
echo "For more information, see README.md"
echo ""
echo "Note: The virtual environment isolates all dependencies and won't affect your system Python installation."
