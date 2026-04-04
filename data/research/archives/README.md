# Research archives

Versioned snapshots of CLI outputs (JSON, logs, table counts) for reproducibility.

- Each run lives in a dated folder: `YYYY-MM-DD-short-label/`.
- **`MANIFEST.json`** records git SHA, commands, and short validation summaries (not a substitute for re-running against your DB).
- Regenerate artifacts after backfill or DB changes; hashes and counts will differ.
- Do not put secrets or full `DATABASE_URL` values in manifests committed to git.

## Example layout

```text
2026-04-04-leader-follower-h1/
  MANIFEST.json
  b1_holdout.json
  near_miss_upgrade_h5.json
  db_row_counts.txt
  b1_holdout.stderr.log
```
