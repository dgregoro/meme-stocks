#!/bin/bash
# Automated quality measurement for meme-stocks project
# Run from project root: ./scripts/quality-check.sh

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

REPORT_DATE=$(date '+%Y-%m-%d %H:%M:%S')
COVERAGE_REPORT=".coverage-report.md"

echo "========================================"
echo "  Quality Check Report"
echo "  ${REPORT_DATE}"
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

# Generate detailed coverage report for AI agent consumption
python -m pytest backend/tests/ --cov=backend/app --cov-report=term-missing --cov-report=json -q 2>/dev/null > /tmp/coverage_output.txt || true

# Extract total coverage percentage
coverage_output=$(grep "TOTAL" /tmp/coverage_output.txt || echo "TOTAL 0 0 0%")
coverage_pct=$(echo "$coverage_output" | awk '{print $NF}' | tr -d '%')
coverage_pct=${coverage_pct:-0}

# Generate markdown coverage report for AI agent
generate_coverage_report() {
    echo "# Test Coverage Report"
    echo ""
    echo "**Generated**: ${REPORT_DATE}"
    echo "**Overall Coverage**: ${coverage_pct}%"
    echo ""
    echo "## Summary"
    echo ""
    echo "| Metric | Value |"
    echo "|--------|-------|"
    echo "| Total Coverage | ${coverage_pct}% |"
    echo "| Target | 80% |"
    echo "| Gap | $((80 - coverage_pct))% |"
    echo ""
    echo "## Per-File Coverage"
    echo ""
    echo "Files sorted by coverage (lowest first) to prioritize improvement:"
    echo ""
    echo "| File | Statements | Missed | Coverage | Missing Lines |"
    echo "|------|------------|--------|----------|---------------|"

    # Parse JSON coverage report if it exists
    if [ -f "coverage.json" ]; then
        python3 << 'PYTHON_SCRIPT'
import json
import sys

try:
    with open("coverage.json", "r") as f:
        data = json.load(f)

    files = []
    for filepath, info in data.get("files", {}).items():
        # Simplify path for readability
        short_path = filepath.replace("backend/app/", "")
        stmts = info["summary"]["num_statements"]
        missed = info["summary"]["missing_lines"]
        covered = info["summary"]["covered_lines"]
        pct = info["summary"]["percent_covered"]
        missing = info.get("missing_lines", [])

        # Format missing lines compactly
        if len(missing) > 10:
            missing_str = f"{missing[0]}-{missing[-1]} ({len(missing)} lines)"
        elif missing:
            missing_str = ",".join(map(str, missing[:10]))
        else:
            missing_str = "-"

        files.append((pct, short_path, stmts, missed, missing_str))

    # Sort by coverage percentage (lowest first)
    files.sort(key=lambda x: x[0])

    for pct, path, stmts, missed, missing_str in files:
        print(f"| {path} | {stmts} | {missed} | {pct:.0f}% | {missing_str} |")

except Exception as e:
    print(f"| Error parsing coverage.json: {e} | - | - | - | - |")
    sys.exit(0)
PYTHON_SCRIPT
    else
        echo "| coverage.json not found | - | - | - | - |"
    fi

    echo ""
    echo "## Files Needing Most Improvement"
    echo ""
    echo "Focus on these files to increase coverage:"
    echo ""

    if [ -f "coverage.json" ]; then
        python3 << 'PYTHON_SCRIPT'
import json

try:
    with open("coverage.json", "r") as f:
        data = json.load(f)

    files = []
    for filepath, info in data.get("files", {}).items():
        short_path = filepath.replace("backend/app/", "")
        pct = info["summary"]["percent_covered"]
        missed = info["summary"]["missing_lines"]
        missing_lines = info.get("missing_lines", [])
        files.append((pct, missed, short_path, missing_lines))

    # Sort by missed lines (most missed first), then by coverage
    files.sort(key=lambda x: (-x[1], x[0]))

    # Show top 10 files needing improvement
    for i, (pct, missed, path, missing_lines) in enumerate(files[:10]):
        if missed > 0:
            print(f"{i+1}. **{path}** - {missed} lines uncovered ({pct:.0f}% covered)")
            if missing_lines:
                # Group consecutive lines into ranges
                ranges = []
                start = missing_lines[0]
                end = start
                for line in missing_lines[1:]:
                    if line == end + 1:
                        end = line
                    else:
                        ranges.append(f"{start}-{end}" if start != end else str(start))
                        start = end = line
                ranges.append(f"{start}-{end}" if start != end else str(start))
                print(f"   - Lines: {', '.join(ranges[:5])}" + ("..." if len(ranges) > 5 else ""))

except Exception as e:
    print(f"Error: {e}")
PYTHON_SCRIPT
    fi

    echo ""
    echo "## How to Improve Coverage"
    echo ""
    echo "1. Run tests with coverage to see current state:"
    echo "   \`\`\`bash"
    echo "   pytest backend/tests/ --cov=backend/app --cov-report=term-missing"
    echo "   \`\`\`"
    echo ""
    echo "2. Focus on files with lowest coverage first"
    echo "3. Add tests for uncovered lines listed above"
    echo "4. Re-run \`./scripts/quality-check.sh\` to update this report"
}

if (( coverage_pct >= 90 )); then scores[coverage]=100
elif (( coverage_pct >= 80 )); then scores[coverage]=85
elif (( coverage_pct >= 70 )); then scores[coverage]=70
elif (( coverage_pct >= 60 )); then scores[coverage]=55
elif (( coverage_pct >= 50 )); then scores[coverage]=40
else scores[coverage]=20
fi
echo "  Coverage: ${coverage_pct}% → Score: ${scores[coverage]}/100"

# Generate the coverage report file for AI agent
generate_coverage_report > "${COVERAGE_REPORT}"
echo "  Coverage report written to: ${COVERAGE_REPORT}"
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
