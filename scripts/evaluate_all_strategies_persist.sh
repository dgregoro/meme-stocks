#!/usr/bin/env bash
# Run S1–S6 merit bundles + S7 rule search and persist each row to daily_strategy_merit_runs.
#
# From repo root:
#   EVAL_START=2022-01-04 EVAL_END=2024-06-28 TRAIN_END=2023-12-29 ./scripts/evaluate_all_strategies_persist.sh
# With backfill when data is missing:
#   ENSURE_DATA=1 ./scripts/evaluate_all_strategies_persist.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNI="${SYMBOLS_FILE:-${ROOT}/data/research/universes/s1_merit_100_under50b.txt}"
EVAL_START="${EVAL_START:-2022-01-04}"
EVAL_END="${EVAL_END:-2024-06-28}"
TRAIN_END="${TRAIN_END:-2023-12-29}"

if [[ ! -f "$UNI" ]]; then
  echo "Symbol list not found: $UNI (set SYMBOLS_FILE=...)" >&2
  exit 1
fi

LEG="${LEG_B:-$(sed -n '2p' "$UNI" | tr -d '\r\n')}"
S7SYM="${S7_SYMBOL:-$(head -1 "$UNI" | tr -d '\r\n')}"

cd "$ROOT"

ENS=()
if [[ "${ENSURE_DATA:-0}" == "1" ]]; then
  ENS=(--ensure-data)
fi

exec python -m backend.app.cli evaluate daily-strategy suite-all \
  --symbols-file "$UNI" \
  --start "$EVAL_START" \
  --end "$EVAL_END" \
  --train-end "$TRAIN_END" \
  --leg-b "$LEG" \
  --s7-symbol "$S7SYM" \
  --rolling-splits "${ROLLING_SPLITS:-1}" \
  --split-mode "${SPLIT_MODE:-trading}" \
  --ack-s7-overfitting-risk \
  "${ENS[@]}"
