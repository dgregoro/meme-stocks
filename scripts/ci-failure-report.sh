#!/usr/bin/env bash
# Extract CI failure details from a downloaded GitHub Actions log archive.
# Usage: ./scripts/ci-failure-report.sh [path-to-logs_*.zip]
#        Default: latest logs_*.zip in repo root.
# Output: Failing job/step names and the relevant log excerpt so an AI or
#         human can fix the issue without opening the zip manually.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ZIP_PATH="${1:-}"

if [ -z "$ZIP_PATH" ]; then
  ZIP_PATH="$(ls -t "$PROJECT_ROOT"/logs_*.zip 2>/dev/null | head -1)"
fi

if [ -z "$ZIP_PATH" ] || [ ! -f "$ZIP_PATH" ]; then
  echo "No log archive found. Download the run's log archive from GitHub Actions, save as logs_<run_id>.zip in repo root, then run this script again." >&2
  exit 1
fi

EXTRACT_DIR="$(mktemp -d)"
trap 'rm -rf "$EXTRACT_DIR"' EXIT

unzip -o -q "$ZIP_PATH" -d "$EXTRACT_DIR"

# Find all .txt files that contain a CI error marker
ERROR_FILES="$(grep -rl "##\[error\]" "$EXTRACT_DIR" --include="*.txt" 2>/dev/null || true)"
if [ -z "$ERROR_FILES" ]; then
  echo "No ##[error] lines found in extracted logs. The run may have failed for a different reason (e.g. timeout). Check the logs manually." >&2
  exit 1
fi

echo "CI failure report from: $ZIP_PATH"
echo "----------------------------------------"

# Prefer step logs (in subdirs like lint-and-test/6_Run mypy.txt) over the big job log.
# Use a while-read loop so filenames with spaces are preserved.
while IFS= read -r -d '' f; do
  [ -n "$f" ] || continue
  basename_f="$(basename "$f")"
  dir_f="$(dirname "$f")"
  if [[ "$basename_f" =~ ^[0-9]+_.*\.txt$ ]] && [ "$dir_f" = "$EXTRACT_DIR" ]; then
    job_name="${basename_f#*_}"
    job_name="${job_name%.txt}"
    if [ -d "$EXTRACT_DIR/$job_name" ]; then
      continue
    fi
  fi
  echo ""
  echo "=== $f ==="
  cat "$f"
  echo ""
done < <(grep -rl "##\[error\]" "$EXTRACT_DIR" --include="*.txt" 2>/dev/null | sort | tr '\n' '\0')

# If we skipped the main job log because a step dir existed, we already printed the step logs above.
# Otherwise we printed the main log. Either way we've emitted the failure.

exit 0
