#!/bin/bash
# Verification script for agent development
# Run this before marking any task as complete

set -e  # Exit on first error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "========================================"
echo "  Meme Stocks Verification Script"
echo "========================================"
echo ""

# Step 1: Pre-commit checks (formatting, linting, types)
echo "[1/3] Running pre-commit hooks..."
if pre-commit run --all-files; then
    echo "✓ Pre-commit passed"
else
    echo "✗ Pre-commit failed - fix issues above"
    exit 1
fi
echo ""

# Step 2: Run test suite
echo "[2/3] Running pytest..."
if python -m pytest backend/tests/ -v --tb=short; then
    echo "✓ All tests passed"
else
    echo "✗ Tests failed - fix issues above"
    exit 1
fi
echo ""

# Step 3: Quick sanity check - can the app start?
echo "[3/3] Checking app can be imported..."
if python -c "from backend.app.main import app; print('✓ App imports successfully')"; then
    :
else
    echo "✗ App import failed"
    exit 1
fi
echo ""

echo "========================================"
echo "  All checks passed!"
echo "========================================"
