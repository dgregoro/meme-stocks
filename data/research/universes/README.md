# Research universes

## S&P Composite 1500 + market-cap filter

This folder holds **optional** constituent lists for:

`python -m backend.app.cli research universe sp1500-cap-filter`

### Quick start

1. **Unofficial constituents (Wikipedia)** — not licensed S&P data; fine for exploration.

   ```bash
   python -m backend.app.cli research universe sp1500-fetch-wikipedia \
     -o data/research/universes/sp_composite_1500_constituents.csv
   ```

   Or copy `sp_composite_1500_constituents.example.csv` to `sp_composite_1500_constituents.csv` and edit.

2. **Filter by market cap** (Yahoo Finance via yfinance; cap is **latest available**, not a true historical point-in-time):

   ```bash
   python -m backend.app.cli research universe sp1500-cap-filter \
     --as-of 2026-03-29 \
     --max-market-cap-usd 50000000000 \
     --constituents-file data/research/universes/sp_composite_1500_constituents.csv \
     --output-json data/research/universes/sp1500_under_50b_2026-03-29.json \
     --output-symbols-file data/research/universes/last_sp1500_under50b_symbols.txt \
     --seed-stocks
   ```

   Use **`evaluate daily-strategy … --symbols-file data/research/universes/last_sp1500_under50b_symbols.txt`** (or `--print-comma-symbols` on stderr for a comma line).

3. **One command for cap-filter + S1 merit** (edit the YAML once):

   ```bash
   python -m backend.app.cli research recipe run \
     specs/018-hypothesis-research-recipe/examples/sp1500-under50b-s1-merit-pipeline.yaml
   ```

### Configuration

- `research_sp1500_constituents_csv` in `backend/app/config.py` (env: `RESEARCH_SP1500_CONSTITUENTS_CSV`) defaults to `data/research/universes/sp_composite_1500_constituents.csv`.

### Rigorous runs

For publication-grade membership and **as-of** market cap, replace Wikipedia/Yahoo with a licensed index vendor and load tickers + caps into CSV yourself.
