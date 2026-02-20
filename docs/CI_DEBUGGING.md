# CI debugging

When a GitHub Actions run fails, you don't have to guess. Use this to find the cause quickly.

## Run the same checks locally (avoid push-and-see)

CI runs, in order:

1. **Pre-commit** (black, flake8, mypy, etc.)
2. **Standalone mypy** (`MYPYPATH=. python -m mypy -p backend.app -p backend.tests`)
3. **pytest** with coverage

To match that **before** pushing:

```bash
# From repo root, with backend deps installed
pre-commit run --all-files
MYPYPATH=. python -m mypy -p backend.app -p backend.tests
pytest backend/tests/ -q --cov=backend/app --cov-report=term --cov-config=pyproject.toml
```

Or use the project script (includes container check):

```bash
./scripts/verify.sh
```

Note: `verify.sh` runs pre-commit (which includes mypy). CI also runs a separate mypy step with the job’s Python env; that env needs `types-requests` (CI installs it). Locally, pre-commit’s mypy gets `types-requests` from its own env. If you run the standalone mypy command above, install stubs with `pip install types-requests`.

## When a run has already failed

1. **Download logs** from the failed run (Actions → run → “Download log archive”). Save the zip in the repo root as `logs_<run_id>.zip` (or pass its path to the script).
2. **Have the AI find the issue**: from repo root run
   `./scripts/ci-failure-report.sh`
   (or `./scripts/ci-failure-report.sh path/to/logs_12345.zip`). The script prints the failing job/step and the relevant log excerpt so the AI (or you) can fix it without opening the zip manually.
3. **Fix** the reported issue, then run the local commands above and push again.

## Why it felt painful

- **Different environments**: Pre-commit uses its own env (with e.g. `types-requests` for mypy). The workflow also runs `python -m mypy` in the job’s env; if that env doesn’t have the same deps (e.g. stubs), mypy fails only in CI.
- **Discovering failures only after push**: Running the same sequence locally (including the standalone mypy command and pytest) catches most CI failures before you push.
- **Logs are in zips**: Grepping for `##[error]` in the extracted logs gets you to the failing step and message quickly; this doc and the local commands above should reduce how often you need to do that.

## Keeping CI and local in sync

- CI installs `types-requests` so the standalone mypy step has stubs; pre-commit’s mypy already had them.
- If you add a new CI step or dependency, run that step (and install that dependency) locally and add it to this doc or to `scripts/verify.sh` so the next run doesn’t fail only in CI.
