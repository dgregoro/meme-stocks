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
echo "[1/5] Running pre-commit hooks..."
pre-commit clean 2>/dev/null || true  # Clear cache to avoid stale pass (matches CI)
if pre-commit run --all-files; then
    echo "✓ Pre-commit passed"
else
    echo "✗ Pre-commit failed - fix issues above"
    exit 1
fi
echo ""

# Step 2: Bandit (security lint)
echo "[2/5] Running bandit (security lint)..."
if bandit -r backend -x backend/tests -q; then
    echo "✓ Bandit passed"
else
    echo "✗ Bandit failed - fix issues above (pip install bandit if not installed)"
    exit 1
fi
echo ""

# Step 3: Run test suite with coverage
echo "[3/5] Running pytest with coverage..."
if python -m pytest backend/tests/ -v --tb=short --cov=backend/app --cov-report=term --cov-config=pyproject.toml; then
    echo "✓ All tests passed"
else
    echo "✗ Tests failed - fix issues above"
    exit 1
fi
echo ""

# Step 4: Quick sanity check - can the app start?
echo "[4/5] Checking app can be imported..."
if python -c "from backend.app.main import app; print('✓ App imports successfully')"; then
    :
else
    echo "✗ App import failed"
    exit 1
fi
echo ""

# Step 5: Container check - can the backend run in containers?
echo "[5/5] Checking containers can run..."
if command -v podman-compose &>/dev/null; then
    # Stop any existing containers first
    podman-compose down 2>/dev/null || true
    # Build and start backend
    if ! podman-compose up -d --build backend; then
        echo "✗ Failed to start backend container"
        podman-compose down 2>/dev/null || true
        exit 1
    fi
    # Wait for backend to be ready
    HEALTHY=false
    for _ in {1..30}; do
        if curl -sf http://localhost:8000/health &>/dev/null; then
            HEALTHY=true
            break
        fi
        sleep 1
    done
    podman-compose down 2>/dev/null || true
    if [ "$HEALTHY" != "true" ]; then
        echo "✗ Backend container did not become healthy (health check timeout)"
        exit 1
    fi
    echo "✓ Backend container is healthy"
else
    echo "⊘ Skipping container check (podman-compose not found)"
fi
echo ""

echo "========================================"
echo "  All checks passed!"
echo "========================================"
