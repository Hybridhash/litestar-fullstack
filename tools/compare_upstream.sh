#!/bin/bash
# Compare your implementation with upstream changes
# Usage: ./tools/compare_upstream.sh <file_path>

set -e

UPSTREAM_COMMIT="4fab0fbc3f233167c257690c933866a79e324cf9"
UPSTREAM_BASE="src/py/app"
LOCAL_BASE="src/app"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Upstream Comparison Tool ===${NC}"
echo ""

if [ $# -eq 0 ]; then
    echo "Usage: $0 <relative_path_from_app>"
    echo ""
    echo "Examples:"
    echo "  $0 lib/service.py              # Compare service.py"
    echo "  $0 domain/teams/services.py    # Compare team services"
    echo "  $0 lib/log.py                  # Compare logging"
    echo ""
    echo "Available upstream files to compare:"
    echo "  - lib/service.py (NEW - AutoSlugServiceMixin)"
    echo "  - lib/log.py (Enhanced logging)"
    echo "  - lib/deps.py (Cleaner DI)"
    echo "  - utils/oauth.py (OAuth improvements)"
    echo "  - domain/teams/services/_team.py (Service patterns)"
    echo "  - domain/accounts/services/_user.py (Service patterns)"
    exit 1
fi

FILE_PATH="$1"
UPSTREAM_FILE="${UPSTREAM_BASE}/${FILE_PATH}"
LOCAL_FILE="${LOCAL_BASE}/${FILE_PATH}"

echo -e "${YELLOW}Comparing:${NC}"
echo "  Upstream: ${UPSTREAM_FILE} @ ${UPSTREAM_COMMIT}"
echo "  Local:    ${LOCAL_FILE}"
echo ""

# Check if upstream file exists
if ! git show "${UPSTREAM_COMMIT}:${UPSTREAM_FILE}" > /dev/null 2>&1; then
    echo -e "${RED}Error: Upstream file not found: ${UPSTREAM_FILE}${NC}"
    echo ""
    echo "This might be a new file in upstream. Try:"
    echo "  git show ${UPSTREAM_COMMIT}:${UPSTREAM_FILE}"
    exit 1
fi

# Check if local file exists
if [ ! -f "${LOCAL_FILE}" ]; then
    echo -e "${YELLOW}Warning: Local file does not exist: ${LOCAL_FILE}${NC}"
    echo ""
    echo "This is a NEW file in upstream. View it with:"
    echo "  git show ${UPSTREAM_COMMIT}:${UPSTREAM_FILE}"
    echo ""
    read -p "Would you like to view the upstream file? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git show "${UPSTREAM_COMMIT}:${UPSTREAM_FILE}"
    fi
    exit 0
fi

# Create temp file for upstream version
TEMP_FILE=$(mktemp)
git show "${UPSTREAM_COMMIT}:${UPSTREAM_FILE}" > "${TEMP_FILE}"

echo -e "${GREEN}Running diff...${NC}"
echo ""

# Run diff with color if available
if command -v colordiff > /dev/null 2>&1; then
    diff -u "${TEMP_FILE}" "${LOCAL_FILE}" | colordiff || true
else
    diff -u "${TEMP_FILE}" "${LOCAL_FILE}" || true
fi

# Cleanup
rm "${TEMP_FILE}"

echo ""
echo -e "${GREEN}=== Comparison Complete ===${NC}"
echo ""
echo "Legend:"
echo "  - (red/minus)  = In upstream but not in your code"
echo "  + (green/plus) = In your code but not in upstream"
echo ""
echo "Next steps:"
echo "  1. Review differences above"
echo "  2. Decide which changes to adopt"
echo "  3. Test after making changes: make lint && pytest"
