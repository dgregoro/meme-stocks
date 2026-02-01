#!/bin/bash
# Automated quality measurement for meme-stocks project
# Run from project root: ./scripts/quality-check.sh

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "========================================"
echo "  Quality Check Report"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

# Initialize scores
declare -A scores
declare -A weights
weights[coverage]=20
weights[tests]=15
weights[types]=15
weights[lint]=10

# --- Test Coverage ---
echo "[1/4] Measuring test coverage..."
coverage_output=$(python -m pytest backend/tests/ --cov=backend/app --cov-report=term -q 2>/dev/null | grep "TOTAL" || echo "TOTAL 0 0 0%")
coverage_pct=$(echo "$coverage_output" | awk '{print $NF}' | tr -d '%')
coverage_pct=${coverage_pct:-0}

if (( coverage_pct >= 90 )); then scores[coverage]=100
elif (( coverage_pct >= 80 )); then scores[coverage]=85
elif (( coverage_pct >= 70 )); then scores[coverage]=70
elif (( coverage_pct >= 60 )); then scores[coverage]=55
elif (( coverage_pct >= 50 )); then scores[coverage]=40
else scores[coverage]=20
fi
echo "  Coverage: ${coverage_pct}% → Score: ${scores[coverage]}/100"
echo ""

# --- Test Pass Rate ---
echo "[2/4] Running tests..."
test_output=$(python -m pytest backend/tests/ -q 2>&1 | tail -1)
passed=$(echo "$test_output" | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+" || echo "0")
failed=$(echo "$test_output" | grep -oE "[0-9]+ failed" | grep -oE "[0-9]+" || echo "0")
errors=$(echo "$test_output" | grep -oE "[0-9]+ error" | grep -oE "[0-9]+" || echo "0")
total=$((passed + failed + errors))

if (( total > 0 )); then
    pass_rate=$((100 * passed / total))
else
    pass_rate=0
fi

if (( pass_rate == 100 )); then scores[tests]=100
elif (( pass_rate >= 95 )); then scores[tests]=80
elif (( pass_rate >= 90 )); then scores[tests]=60
elif (( pass_rate >= 80 )); then scores[tests]=40
else scores[tests]=20
fi
echo "  Results: ${passed} passed, ${failed} failed, ${errors} errors"
echo "  Pass rate: ${pass_rate}% → Score: ${scores[tests]}/100"
echo ""

# --- Type Safety ---
echo "[3/4] Checking types (mypy)..."
mypy_output=$(mypy backend/app/ --ignore-missing-imports 2>&1 || true)
type_errors=$(echo "$mypy_output" | grep -c "error:" || echo "0")

if (( type_errors == 0 )); then scores[types]=100
elif (( type_errors <= 5 )); then scores[types]=80
elif (( type_errors <= 15 )); then scores[types]=60
elif (( type_errors <= 30 )); then scores[types]=40
elif (( type_errors <= 50 )); then scores[types]=20
else scores[types]=0
fi
echo "  Type errors: ${type_errors} → Score: ${scores[types]}/100"
echo ""

# --- Linting ---
echo "[4/4] Linting (flake8)..."
# Use same args as .pre-commit-config.yaml
lint_output=$(flake8 backend/app/ --max-line-length=120 --extend-ignore=E501 --count 2>&1 || true)
# Extract just the final count number (last line, first number)
lint_errors=$(echo "$lint_output" | tail -1 | grep -oE "^[0-9]+" | head -1 || echo "0")
lint_errors=${lint_errors:-0}

if (( lint_errors == 0 )); then scores[lint]=100
elif (( lint_errors <= 10 )); then scores[lint]=80
elif (( lint_errors <= 25 )); then scores[lint]=60
elif (( lint_errors <= 50 )); then scores[lint]=40
else scores[lint]=20
fi
echo "  Lint errors: ${lint_errors} → Score: ${scores[lint]}/100"
echo ""

# --- Calculate Weighted Score ---
weighted_sum=0
weight_total=0
for category in coverage tests types lint; do
    weighted_sum=$((weighted_sum + scores[$category] * weights[$category]))
    weight_total=$((weight_total + weights[$category]))
done

# Add manual categories at neutral score (50) for now
manual_weight=40  # documentation + error handling + architecture + security
weighted_sum=$((weighted_sum + 50 * manual_weight))
weight_total=$((weight_total + manual_weight))

overall_score=$((weighted_sum / weight_total))

# Determine grade
if (( overall_score >= 90 )); then grade="A"
elif (( overall_score >= 80 )); then grade="B"
elif (( overall_score >= 70 )); then grade="C"
elif (( overall_score >= 60 )); then grade="D"
else grade="F"
fi

echo "========================================"
echo "  Summary"
echo "========================================"
echo ""
printf "  %-15s %6s  %s\n" "Category" "Score" "Weight"
printf "  %-15s %6s  %s\n" "--------" "-----" "------"
printf "  %-15s %5d%%  %d%%\n" "Coverage" "${scores[coverage]}" "${weights[coverage]}"
printf "  %-15s %5d%%  %d%%\n" "Tests" "${scores[tests]}" "${weights[tests]}"
printf "  %-15s %5d%%  %d%%\n" "Type Safety" "${scores[types]}" "${weights[types]}"
printf "  %-15s %5d%%  %d%%\n" "Linting" "${scores[lint]}" "${weights[lint]}"
printf "  %-15s %5d%%  %s\n" "Manual*" "50" "40% (audit needed)"
echo ""
echo "  * Manual categories (docs, errors, arch, security) default to 50%"
echo "    Run manual audit per QUALITY.md to get accurate scores"
echo ""
echo "========================================"
printf "  Overall Score: %d/100 (Grade: %s)\n" "$overall_score" "$grade"
echo "========================================"
echo ""

# Raw metrics for tracking
echo "--- Raw Metrics (for tracking) ---"
echo "DATE=$(date '+%Y-%m-%d')"
echo "COVERAGE_PCT=${coverage_pct}"
echo "TESTS_PASSED=${passed}"
echo "TESTS_FAILED=${failed}"
echo "TYPE_ERRORS=${type_errors}"
echo "LINT_ERRORS=${lint_errors}"
echo "OVERALL_SCORE=${overall_score}"
echo "GRADE=${grade}"
