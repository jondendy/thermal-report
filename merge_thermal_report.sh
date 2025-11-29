#!/bin/bash
#
# Safe Merge & Backup Script for thermal-report
# Creates a backup branch, merges testing-improvements into main, and runs tests
#
# Usage: bash merge_thermal_report.sh
#

set -e  # Exit on any error

echo "=========================================="
echo "Thermal-Report Safe Merge Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_DIR="${1:-.}"
MAIN_BRANCH="main"
FEATURE_BRANCH="testing-improvements"
BACKUP_BRANCH="main-pre-merge-backup"

# Change to repo directory
cd "$REPO_DIR"

echo -e "${BLUE}Step 1: Verifying repository structure${NC}"
if [ ! -d ".git" ]; then
    echo -e "${RED}ERROR: Not a git repository. Run this script from the thermal-report root directory.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Git repository found${NC}"
echo ""

echo -e "${BLUE}Step 2: Fetching latest changes from origin${NC}"
git fetch origin
echo -e "${GREEN}✓ Fetch complete${NC}"
echo ""

echo -e "${BLUE}Step 3: Ensuring main is up-to-date${NC}"
git checkout $MAIN_BRANCH
git pull origin $MAIN_BRANCH
echo -e "${GREEN}✓ main branch updated${NC}"
echo ""

echo -e "${BLUE}Step 4: Creating backup branch (${BACKUP_BRANCH})${NC}"
# Check if backup branch already exists
if git rev-parse --verify $BACKUP_BRANCH >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Warning: ${BACKUP_BRANCH} already exists. Skipping creation.${NC}"
else
    git checkout -b $BACKUP_BRANCH
    git push origin $BACKUP_BRANCH
    echo -e "${GREEN}✓ Backup branch created and pushed to origin${NC}"
fi
echo ""

echo -e "${BLUE}Step 5: Switching to ${FEATURE_BRANCH}${NC}"
git checkout $FEATURE_BRANCH
git pull origin $FEATURE_BRANCH
echo -e "${GREEN}✓ Feature branch checked out and updated${NC}"
echo ""

echo -e "${BLUE}Step 6: Switching back to ${MAIN_BRANCH}${NC}"
git checkout $MAIN_BRANCH
echo -e "${GREEN}✓ Switched to main${NC}"
echo ""

echo -e "${BLUE}Step 7: Merging ${FEATURE_BRANCH} into ${MAIN_BRANCH}${NC}"
if git merge $FEATURE_BRANCH; then
    echo -e "${GREEN}✓ Merge successful${NC}"
else
    echo -e "${RED}✗ Merge conflict detected!${NC}"
    echo "Please resolve conflicts manually, then run:"
    echo "  git add ."
    echo "  git commit -m 'Merge ${FEATURE_BRANCH} into ${MAIN_BRANCH}'"
    echo "  git push origin ${MAIN_BRANCH}"
    exit 1
fi
echo ""

echo -e "${BLUE}Step 8: Pushing merged main to origin${NC}"
git push origin $MAIN_BRANCH
echo -e "${GREEN}✓ Changes pushed to origin/main${NC}"
echo ""

echo -e "${BLUE}Step 9: Verifying merged files${NC}"
echo "Files in current merge:"
git log --oneline -n 5
echo ""

echo -e "${BLUE}Step 10: Running test suite${NC}"
if [ -f "run_tests.py" ]; then
    python run_tests.py
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ All tests passed!${NC}"
    else
        echo -e "${RED}✗ Some tests failed. Review output above.${NC}"
        echo "To rollback, run: git reset --hard origin/${BACKUP_BRANCH} && git push --force origin ${MAIN_BRANCH}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ run_tests.py not found. Skipping automated tests.${NC}"
fi
echo ""

echo "=========================================="
echo -e "${GREEN}✓ Merge Complete!${NC}"
echo "=========================================="
echo ""
echo "Summary:"
echo "  • Backup branch: ${BACKUP_BRANCH}"
echo "  • Feature branch merged: ${FEATURE_BRANCH}"
echo "  • Main branch updated: ${MAIN_BRANCH}"
echo "  • All changes pushed to origin"
echo ""
echo "Next steps:"
echo "  1. Update README.md to reference TESTING.md"
echo "  2. Test in Docker: docker build -t thermal-report:latest ."
echo "  3. Test in Codespaces (if applicable)"
echo "  4. Review TESTING.md and WEB_TOOL_README.md"
echo ""
echo "To rollback if needed:"
echo "  git reset --hard origin/${BACKUP_BRANCH} && git push --force origin ${MAIN_BRANCH}"
echo ""
