# Setting Up for Autonomous Agent Development

This guide explains how to configure a project so that a Cursor agent can independently implement large features with high-quality results.

---

## The Four Pillars

Successful autonomous agent development requires:

| Pillar | Purpose | How It Helps |
|--------|---------|--------------|
| **Context** | Agent understands project structure and patterns | Reduces guessing, follows conventions |
| **Guardrails** | Automated checks catch mistakes | Agent gets immediate feedback on errors |
| **Patterns** | Examples show "how we do things here" | Agent replicates existing patterns |
| **Verification** | Clear criteria for "done" | Agent knows when to stop |

---

## Current State Assessment

### What You Have ✅

| Component | Status | Location |
|-----------|--------|----------|
| Rules file | Good | `.cursorrules` |
| Modular architecture | Good | `backend/app/{models,services,api,data}/` |
| Pre-commit hooks | Partial | `.pre-commit-config.yaml` (missing mypy) |
| Test suite | Good | `backend/tests/` |
| Configuration management | Good | `backend/app/config.py` |
| Project plan | Good | `PLAN.md` |
| PRD | Good | `PRD.md` |
| Agent task plan | Good | `AGENT_PLAN.md` |

### What's Missing ❌

| Component | Impact | Priority |
|-----------|--------|----------|
| Architecture patterns doc | Agent doesn't know how to add new components | High |
| Type checking in CI/pre-commit | Type errors not caught automatically | High |
| Test coverage requirements | Agent might skip tests | Medium |
| Example-based patterns | Agent has to infer from code | Medium |
| Task specification template | Inconsistent task definitions | Medium |
| Verification checklists | Agent doesn't know "done" criteria | Medium |

---

## Recommended Improvements

### 1. Add Type Checking to Pre-commit

Update `.pre-commit-config.yaml` to catch type errors:

```yaml
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies:
          - pydantic
          - pydantic-settings
          - types-requests
        args: ["--ignore-missing-imports", "--no-error-summary"]
        files: ^backend/
```

### 2. Create Architecture Patterns Document

Create `ARCHITECTURE.md` with explicit patterns the agent should follow. See template below.

### 3. Add Test Coverage Enforcement

Add to `pytest.ini`:

```ini
[pytest]
addopts = --cov=backend/app --cov-fail-under=70
```

### 4. Enhance .cursorrules with Patterns

Add explicit "how to" sections for common tasks.

### 5. Create Task Specification Template

Standardize how tasks are specified for the agent.

### 6. Add Verification Checklists

Explicit checklists the agent runs through before marking work complete.

---

## Implementation: Architecture Patterns Document

Create this file to give the agent explicit patterns to follow:

```markdown
# Architecture Patterns

## Adding a New API Endpoint

### 1. Create/Update Model (if needed)
Location: `backend/app/models/{name}.py`

```python
from sqlalchemy import Column, Integer, String, DateTime
from backend.app.data.database import Base

class MyModel(Base):
    __tablename__ = "my_models"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
```

### 2. Create Repository
Location: `backend/app/data/repositories/{name}_repo.py`

```python
from sqlalchemy.orm import Session
from backend.app.models.my_model import MyModel

class MyModelRepository:
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, id: int) -> MyModel | None:
        return self.session.query(MyModel).filter(MyModel.id == id).first()
    
    def create(self, model: MyModel) -> MyModel:
        self.session.add(model)
        self.session.commit()
        return model
```

### 3. Create Service (business logic)
Location: `backend/app/services/{name}_service.py`

```python
from dataclasses import dataclass
from backend.app.data.repositories.my_model_repo import MyModelRepository

@dataclass
class MyModelResult:
    id: int
    name: str
    # Use dataclasses for service outputs, not ORM models

class MyModelService:
    def __init__(self, repo: MyModelRepository):
        self.repo = repo
    
    def get_by_id(self, id: int) -> MyModelResult | None:
        model = self.repo.get_by_id(id)
        if model is None:
            return None
        return MyModelResult(id=model.id, name=model.name)
```

### 4. Create API Route
Location: `backend/app/api/{name}.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.app.data.database import get_db
from backend.app.services.my_model_service import MyModelService
from backend.app.data.repositories.my_model_repo import MyModelRepository

router = APIRouter(prefix="/api/my-models", tags=["my-models"])

class MyModelResponse(BaseModel):
    id: int
    name: str

@router.get("/{id}", response_model=MyModelResponse)
def get_my_model(id: int, db = Depends(get_db)):
    repo = MyModelRepository(db)
    service = MyModelService(repo)
    result = service.get_by_id(id)
    if result is None:
        raise HTTPException(status_code=404, detail="Not found")
    return MyModelResponse(id=result.id, name=result.name)
```

### 5. Register Router
Location: `backend/app/main.py`

```python
from backend.app.api.my_model import router as my_model_router
app.include_router(my_model_router)
```

### 6. Add Tests
Location: `backend/tests/test_{name}.py`

```python
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_get_my_model_not_found():
    response = client.get("/api/my-models/999")
    assert response.status_code == 404

def test_get_my_model_success():
    # Setup test data...
    response = client.get("/api/my-models/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1
```

---

## Adding a New Background Job

### Pattern
Location: `backend/app/services/scheduler_service.py`

1. Add job function (idempotent, handles errors gracefully)
2. Register in scheduler with appropriate interval
3. Add job execution tracking
4. Add catch-up logic if needed

### Template
```python
def my_new_job(self) -> None:
    """Description of what this job does."""
    try:
        # Job logic here
        self._record_job_execution("my_new_job")
    except Exception as e:
        logger.error(f"my_new_job failed: {e}")
        # Don't re-raise - job failures shouldn't crash the app
```

---

## Error Handling Pattern

### In Services
```python
from backend.app.utils.errors import DataFetchError

def fetch_external_data(self) -> Data:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return self._parse_response(response.json())
    except requests.RequestException as e:
        raise DataFetchError(f"Failed to fetch from {url}: {e}") from e
```

### In API Routes
```python
from fastapi import HTTPException
from backend.app.utils.errors import DataFetchError

@router.get("/data")
def get_data():
    try:
        return service.fetch_external_data()
    except DataFetchError as e:
        raise HTTPException(status_code=502, detail=str(e))
```
```

---

## Implementation: Enhanced .cursorrules

Add these sections to your existing `.cursorrules`:

```markdown
# How to add a new feature

1. **Read ARCHITECTURE.md** for the pattern to follow
2. **Create in order**: Model → Repository → Service → API Route → Tests
3. **Register the router** in main.py
4. **Run tests** before considering done: `pytest backend/tests/ -v`
5. **Run pre-commit** to catch formatting/type issues: `pre-commit run --all-files`

# Verification checklist (run before marking task complete)

- [ ] All new code has type hints
- [ ] No hardcoded values (use config.py)
- [ ] Error cases handled explicitly
- [ ] At least one happy-path test exists
- [ ] At least one error-case test exists
- [ ] Pre-commit passes
- [ ] All tests pass
- [ ] Router registered in main.py (if new endpoint)

# Common mistakes to avoid

- Don't put business logic in API routes - delegate to services
- Don't return ORM models from services - use dataclasses/Pydantic
- Don't swallow exceptions - log and re-raise or handle explicitly
- Don't use `datetime.utcnow()` - use `datetime.now(timezone.utc)`
- Don't add features not in PLAN.md or PRD.md without updating them first
```

---

## Implementation: Task Specification Template

Use this format when specifying tasks for the agent:

```markdown
## Task: [Short Name]

### Context
- **PRD Requirement**: FR-X.X (or "New feature - update PRD after")
- **Related code**: `backend/app/services/related_service.py`
- **Pattern to follow**: See ARCHITECTURE.md section "Adding a New X"

### Requirements
1. [Specific requirement 1]
2. [Specific requirement 2]
3. [Specific requirement 3]

### Acceptance Criteria
- [ ] [Measurable criterion 1]
- [ ] [Measurable criterion 2]
- [ ] All tests pass
- [ ] Pre-commit passes

### Files Expected to Change
- `backend/app/models/new_model.py` (create)
- `backend/app/services/new_service.py` (create)
- `backend/app/api/new_endpoint.py` (create)
- `backend/app/main.py` (modify - register router)
- `backend/tests/test_new_feature.py` (create)

### Do NOT
- Change unrelated files
- Add dependencies not discussed
- Skip tests
```

---

## Implementation: Verification Script

Create `scripts/verify.sh` for the agent to run:

```bash
#!/bin/bash
set -e

echo "=== Running pre-commit ==="
pre-commit run --all-files

echo "=== Running tests ==="
python -m pytest backend/tests/ -v --tb=short

echo "=== Checking for type errors ==="
mypy backend/app/ --ignore-missing-imports

echo "=== All checks passed ==="
```

---

## Quick Setup Checklist

Run these commands to implement the improvements:

```bash
# 1. Update pre-commit with mypy
# (Edit .pre-commit-config.yaml as shown above)

# 2. Install pre-commit hooks
pip install pre-commit mypy
pre-commit install

# 3. Create architecture doc
# (Create ARCHITECTURE.md with patterns from your existing code)

# 4. Create verification script
mkdir -p scripts
# (Create scripts/verify.sh as shown above)
chmod +x scripts/verify.sh

# 5. Update .cursorrules
# (Add the sections shown above)

# 6. Test the setup
./scripts/verify.sh
```

---

## Summary: What Good Looks Like

When properly configured, an agent should be able to:

1. **Read the task** from AGENT_PLAN.md or a task specification
2. **Understand the pattern** from ARCHITECTURE.md
3. **Implement the feature** following established conventions
4. **Verify its work** by running `./scripts/verify.sh`
5. **Know when it's done** by checking the acceptance criteria

The agent should almost never need to ask "how should I structure this?" because the patterns are documented.

---

## Measuring Success

Track these metrics to assess if your setup is working:

| Metric | Good | Needs Work |
|--------|------|------------|
| Agent asks clarifying questions | Occasionally | Constantly |
| Tests pass on first attempt | >80% | <50% |
| Pre-commit passes on first attempt | >90% | <70% |
| Agent follows project patterns | Consistently | Rarely |
| Manual fixes needed after agent work | Minimal | Extensive |
