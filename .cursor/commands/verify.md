---
description: Run the verification script (pre-commit, tests, bandit, app import, container check)
---

## Run Verification

1. From project root, run:

```bash
./scripts/verify.sh
```

2. Fix any failures before considering work complete. The script runs:

- Pre-commit hooks (formatting, linting, mypy)
- Bandit (security lint)
- Pytest with coverage
- App import check
- Container build check

3. Do not claim task completion if verification fails.
