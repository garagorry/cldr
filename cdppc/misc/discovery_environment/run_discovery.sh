#!/bin/bash

# CDP Environment Discovery Tool - Quick Run Script
# This script makes it easy to run environment discovery with proper setup

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       CDP Environment Discovery Tool                          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if environment name provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Environment name required${NC}"
    echo ""
    echo "Usage: $0 <environment-name> [options]"
    echo ""
    echo "Examples:"
    echo "  $0 jdga-ent7217-cdp-env"
    echo "  $0 my-env --profile production"
    echo "  $0 my-env --include-services cde cdw cai"
    echo "  $0 my-env --debug"
    echo ""
    exit 1
fi

ENVIRONMENT_NAME="$1"
shift  # Remove first argument, keep the rest

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if CDP CLI is available
if ! command -v cdp &> /dev/null; then
    echo -e "${YELLOW}⚠️  CDP CLI not found in PATH${NC}"
    echo ""
    echo "If you're using CDP CLI in a virtual environment, activate it first:"
    echo "  source ~/venvs/cdpcli-beta/bin/activate"
    echo "  # or use your custom activation function:"
    echo "  a4"
    echo ""
    read -p "Press Enter to continue anyway, or Ctrl+C to abort..."
fi

# Verify CDP CLI works
echo -e "${BLUE}🔍 Verifying CDP CLI...${NC}"
if cdp --version &> /dev/null; then
    CDP_VERSION=$(cdp --version 2>&1 | head -1)
    echo -e "${GREEN}✅ CDP CLI found: ${CDP_VERSION}${NC}"
else
    echo -e "${RED}❌ CDP CLI verification failed${NC}"
    echo "Please ensure CDP CLI is properly configured and accessible."
    exit 1
fi

# Check Python version
echo -e "${BLUE}🐍 Checking Python...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✅ ${PYTHON_VERSION}${NC}"
else
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi

# Change to script directory
cd "$SCRIPT_DIR"

# Run discovery
echo ""
echo -e "${BLUE}🚀 Starting discovery for environment: ${GREEN}${ENVIRONMENT_NAME}${NC}"
echo -e "${BLUE}📂 Discovery tool location: ${SCRIPT_DIR}${NC}"
echo ""

# Run the discovery tool with all remaining arguments
python3 discover.py --environment-name "$ENVIRONMENT_NAME" "$@"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅ Discovery completed successfully!                         ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
else
    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ❌ Discovery failed with exit code: $EXIT_CODE                ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Try running with --debug flag for more information:"
    echo "  $0 $ENVIRONMENT_NAME --debug"
fi

exit $EXIT_CODE

