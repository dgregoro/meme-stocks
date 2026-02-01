# Quality Measurement Framework

This document defines how to measure and track the quality of the meme-stocks project.

---

## Quality Scorecard

Run `./scripts/quality-check.sh` to generate an automated score.

| Category | Weight | Score | Method |
|----------|--------|-------|--------|
| Test Coverage | 20% | _/100 | pytest-cov |
| Test Pass Rate | 15% | _/100 | pytest results |
| Type Safety | 15% | _/100 | mypy error count |
| Linting | 10% | _/100 | flake8 error count |
| Documentation | 10% | _/100 | docstring coverage |
| Error Handling | 10% | _/100 | manual audit |
| Architecture | 10% | _/100 | manual audit |
| Security | 10% | _/100 | automated + manual |
| **Total** | 100% | _/100 | Weighted average |

**Quality Grades:**
- A: 90-100 (Production ready)
- B: 80-89 (Good, minor issues)
- C: 70-79 (Acceptable, needs work)
- D: 60-69 (Below standard)
- F: <60 (Significant issues)

---

## Category 1: Test Coverage (20%)

### Measurement
```bash
pytest backend/tests/ --cov=backend/app --cov-report=term-missing
```

### Scoring
| Coverage | Score |
|----------|-------|
| ≥90% | 100 |
| 80-89% | 85 |
| 70-79% | 70 |
| 60-69% | 55 |
| 50-59% | 40 |
| <50% | 20 |

### What to Check
- [ ] All services have tests
- [ ] All repositories have tests
- [ ] All API endpoints have tests
- [ ] Edge cases covered (empty data, errors)
- [ ] External API mocking works

---

## Category 2: Test Pass Rate (15%)

### Measurement
```bash
pytest backend/tests/ -v --tb=no | grep -E "(passed|failed|error)"
```

### Scoring
| Pass Rate | Score |
|-----------|-------|
| 100% | 100 |
| 95-99% | 80 |
| 90-94% | 60 |
| 80-89% | 40 |
| <80% | 20 |

### What to Check
- [ ] All tests pass
- [ ] No flaky tests (run 3x to verify)
- [ ] Tests run in <60 seconds total
- [ ] No tests skipped without reason

---

## Category 3: Type Safety (15%)

### Measurement
```bash
mypy backend/app/ --ignore-missing-imports 2>&1 | grep -c "error:"
```

### Scoring
| Errors | Score |
|--------|-------|
| 0 | 100 |
| 1-5 | 80 |
| 6-15 | 60 |
| 16-30 | 40 |
| 31-50 | 20 |
| >50 | 0 |

### What to Check
- [ ] All functions have type hints
- [ ] Return types specified
- [ ] No `Any` types without justification
- [ ] Dataclasses/Pydantic models properly typed

---

## Category 4: Linting (10%)

### Measurement
```bash
flake8 backend/app/ --count --statistics 2>&1 | tail -1
```

### Scoring
| Errors | Score |
|--------|-------|
| 0 | 100 |
| 1-10 | 80 |
| 11-25 | 60 |
| 26-50 | 40 |
| >50 | 20 |

### What to Check
- [ ] No flake8 errors
- [ ] Consistent formatting (black)
- [ ] No unused imports
- [ ] No unused variables

---

## Category 5: Documentation (10%)

### Measurement
```bash
# Count functions/classes without docstrings
python scripts/check_docstrings.py
```

### Scoring
| Docstring Coverage | Score |
|--------------------|-------|
| ≥90% | 100 |
| 80-89% | 80 |
| 70-79% | 60 |
| 50-69% | 40 |
| <50% | 20 |

### What to Check
- [ ] All public functions have docstrings
- [ ] All classes have docstrings
- [ ] README.md is accurate and complete
- [ ] PLAN.md reflects current state
- [ ] API endpoints documented (FastAPI auto-docs work)

---

## Category 6: Error Handling (10%)

### Measurement
Manual audit using checklist below.

### Scoring Rubric
| Criteria | Points |
|----------|--------|
| No bare `except:` clauses | 20 |
| External APIs wrapped in try/except | 20 |
| Custom exceptions used appropriately | 20 |
| Errors logged before re-raising | 20 |
| API returns proper HTTP status codes | 20 |

### What to Check
- [ ] No `except: pass` or `except Exception: pass`
- [ ] Reddit API calls handle: network errors, rate limits, auth failures
- [ ] Yahoo API calls handle: network errors, invalid symbols, missing data
- [ ] Background jobs don't crash on errors
- [ ] API returns 4xx for client errors, 5xx for server errors
- [ ] Error messages don't expose stack traces to clients

### Audit Command
```bash
# Find bare except clauses
grep -rn "except:" backend/app/ --include="*.py" | grep -v "except.*:"

# Find pass-only exception handlers
grep -rn -A1 "except" backend/app/ --include="*.py" | grep "pass"
```

---

## Category 7: Architecture (10%)

### Measurement
Manual audit using checklist below.

### Scoring Rubric
| Criteria | Points |
|----------|--------|
| Clear layer separation (API → Service → Repo) | 25 |
| No business logic in API routes | 25 |
| Services don't return ORM models | 20 |
| Configuration centralized | 15 |
| No circular imports | 15 |

### What to Check
- [ ] API routes only handle HTTP, delegate to services
- [ ] Services contain business logic, return dataclasses
- [ ] Repositories handle data access only
- [ ] All thresholds in config.py, not hardcoded
- [ ] Models don't import from services
- [ ] No God classes (>500 lines)

### Audit Commands
```bash
# Check for large files
wc -l backend/app/**/*.py | sort -n | tail -10

# Check for circular imports
python -c "from backend.app.main import app" 2>&1 | grep -i "circular"
```

---

## Category 8: Security (10%)

### Measurement
Automated scan + manual checklist.

### Scoring Rubric
| Criteria | Points |
|----------|--------|
| No secrets in code | 30 |
| Input validation on all endpoints | 25 |
| Dependencies up to date | 20 |
| CORS properly configured | 15 |
| No SQL injection vectors | 10 |

### What to Check
- [ ] No API keys, passwords, or secrets in code
- [ ] .env files in .gitignore
- [ ] All user input validated (Pydantic models)
- [ ] No raw SQL queries (use SQLAlchemy ORM)
- [ ] Dependencies have no critical CVEs
- [ ] CORS origins are restrictive

### Audit Commands
```bash
# Check for hardcoded secrets
grep -rn "api_key\|password\|secret" backend/app/ --include="*.py" | grep -v "config"

# Check for raw SQL
grep -rn "execute(" backend/app/ --include="*.py"

# Check dependencies for vulnerabilities
pip-audit
```

---

## Automated Quality Check Script

Create `scripts/quality-check.sh`:

```bash
#!/bin/bash
# Automated quality measurement

echo "================================"
echo "  Quality Check Report"
echo "  $(date)"
echo "================================"
echo ""

# Test coverage
echo "## Test Coverage"
coverage_output=$(pytest backend/tests/ --cov=backend/app --cov-report=term 2>/dev/null | grep "TOTAL")
coverage_pct=$(echo "$coverage_output" | awk '{print $4}' | tr -d '%')
echo "Coverage: ${coverage_pct}%"
echo ""

# Test pass rate
echo "## Test Results"
test_output=$(pytest backend/tests/ -v --tb=no 2>/dev/null | tail -1)
echo "$test_output"
echo ""

# Type checking
echo "## Type Errors (mypy)"
mypy_errors=$(mypy backend/app/ --ignore-missing-imports 2>&1 | grep -c "error:" || echo "0")
echo "Errors: $mypy_errors"
echo ""

# Linting
echo "## Lint Errors (flake8)"
flake8_errors=$(flake8 backend/app/ --count 2>&1 | tail -1 || echo "0")
echo "Errors: $flake8_errors"
echo ""

# Summary
echo "================================"
echo "  Summary"
echo "================================"
echo "Coverage:    ${coverage_pct:-N/A}%"
echo "Type Errors: $mypy_errors"
echo "Lint Errors: $flake8_errors"
```

---

## Quality Tracking Over Time

### Baseline Measurement
Run quality check and record baseline:

| Date | Coverage | Tests Pass | Type Errors | Lint Errors | Overall |
|------|----------|------------|-------------|-------------|---------|
| YYYY-MM-DD | __% | __/__ | __ | __ | _/100 |

### Improvement Targets

| Metric | Current | Target | Deadline |
|--------|---------|--------|----------|
| Test Coverage | __% | 80% | |
| Type Errors | __ | 0 | |
| Lint Errors | __ | 0 | |

### Quality Gates

Before merging any PR:
- [ ] All tests pass
- [ ] Coverage doesn't decrease
- [ ] No new type errors
- [ ] No new lint errors

---

## Quick Quality Commands

```bash
# Full quality check
./scripts/quality-check.sh

# Just tests
pytest backend/tests/ -v

# Just coverage
pytest backend/tests/ --cov=backend/app --cov-report=html
# Open htmlcov/index.html in browser

# Just types
mypy backend/app/ --ignore-missing-imports

# Just lint
flake8 backend/app/

# Security scan
pip-audit

# Find TODOs/FIXMEs
grep -rn "TODO\|FIXME\|XXX\|HACK" backend/app/
```

---

## Improvement Priorities

When quality score is low, fix in this order:

1. **Failing tests** (blocks everything)
2. **Type errors** (catch bugs early)
3. **Security issues** (critical risk)
4. **Error handling gaps** (reliability)
5. **Test coverage** (confidence)
6. **Lint errors** (maintainability)
7. **Documentation** (onboarding)
8. **Architecture** (long-term health)
