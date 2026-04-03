#!/usr/bin/env bash
# Run S1–S6 daily-strategy single-symbol smoke and full-panel merit for the repo 100-ticker file.
# Requires price_data (and for S3, vol_term_structure_observations). Use preflight or --ensure-data.
#
# Usage (from repo root):
#   EVAL_START=2022-01-04 EVAL_END=2024-06-28 ./scripts/run_research_universe_strategy_eval.sh
# With Alpaca/Yahoo backfill when rows are missing:
#   ENSURE_DATA=1 EVAL_START=... EVAL_END=... ./scripts/run_research_universe_strategy_eval.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNI="${ROOT}/data/research/universes/s1_merit_100_under50b.txt"
EVAL_START="${EVAL_START:-2022-01-04}"
EVAL_END="${EVAL_END:-2024-06-28}"

if [[ ! -f "$UNI" ]]; then
  echo "Missing universe file: $UNI" >&2
  exit 1
fi

ONE="$(head -1 "$UNI" | tr -d '\r\n')"
LEG="$(sed -n '2p' "$UNI" | tr -d '\r\n')"
UNIV_CSV="$(paste -sd, "$UNI")"

cd "$ROOT"

ENS=()
if [[ "${ENSURE_DATA:-0}" == "1" ]]; then
  ENS=(--ensure-data)
fi

CLI=(python -m backend.app.cli evaluate daily-strategy)

echo "=== Single-symbol (${ONE}, leg B ${LEG} for S6) ==="
for strat in s1 s2 s3 s4; do
  echo "-- $strat"
  "${CLI[@]}" "$strat" -s "$ONE" --start "$EVAL_START" --end "$EVAL_END" "${ENS[@]}"
done
echo "-- s5"
"${CLI[@]}" s5 -s "$ONE" -u "$UNIV_CSV" --start "$EVAL_START" --end "$EVAL_END" "${ENS[@]}"
echo "-- s6"
"${CLI[@]}" s6 -s "$ONE" --leg-b "$LEG" --start "$EVAL_START" --end "$EVAL_END" "${ENS[@]}"

echo "=== Merit / eval-bundle (100 symbols from file) ==="
for strat in s1 s2 s3 s4 s5; do
  echo "-- eval-bundle $strat"
  "${CLI[@]}" eval-bundle --strategy "$strat" --start "$EVAL_START" --end "$EVAL_END" \
    --symbols-file "$UNI" --rolling-splits 1 "${ENS[@]}"
done
echo "-- eval-bundle s6"
"${CLI[@]}" eval-bundle --strategy s6 --leg-b "$LEG" --start "$EVAL_START" --end "$EVAL_END" \
  --symbols-file "$UNI" --rolling-splits 1 "${ENS[@]}"

echo "Done."
