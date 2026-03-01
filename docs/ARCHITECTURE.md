# Architecture Patterns

This document defines the patterns an agent should follow when implementing features in this codebase.

**Write code to be easily understood by AI agents.** Clear structure, meaningful names, explicit docstrings, and consistent conventions help both humans and AI navigate and modify the codebase.

---

## Documentation

**When you add or modify a feature, update the project documentation as well.** Keep these in sync:

- **PRD.md** — Update requirement status (e.g. FR-x.x from ❌ Future to ✅ Complete), add or adjust acceptance criteria.
- **README.md** — Update feature lists and API examples if endpoints or capabilities change.
- **PLAN.md** — Update milestones, checklists, and implementation notes.
- **ARCHITECTURE.md** — Document new patterns, models, or conventions if they establish precedent.

Do not treat documentation as optional; incomplete or stale docs create confusion and rework.

---

## Project Structure

```
backend/app/
├── main.py              # FastAPI app entry, router registration
├── config.py            # All configuration via environment variables
├── models/              # SQLAlchemy ORM models
├── data/
│   ├── database.py      # DB session management
│   └── repositories/    # Data access layer (one per model)
├── services/            # Business logic (pure functions preferred)
├── api/                 # FastAPI route handlers
└── utils/               # Shared utilities, custom exceptions
```

## Layered Architecture

```
┌─────────────────────────────────────────────────┐
│                  API Routes                      │
│  - HTTP handling, request/response validation    │
│  - Delegates to services, never contains logic   │
└─────────────────────┬───────────────────────────┘
                      │ calls
┌─────────────────────▼───────────────────────────┐
│                  Services                        │
│  - Business logic, orchestration                 │
│  - Pure functions where possible                 │
│  - Returns dataclasses, not ORM models           │
└─────────────────────┬───────────────────────────┘
                      │ calls
┌─────────────────────▼───────────────────────────┐
│                Repositories                      │
│  - Data access only (CRUD operations)            │
│  - One repository per model                      │
│  - Returns ORM models                            │
└─────────────────────┬───────────────────────────┘
                      │ queries
┌─────────────────────▼───────────────────────────┐
│                  Database                        │
│  - SQLite via SQLAlchemy                         │
└─────────────────────────────────────────────────┘
```

---

## CLI Architecture

The CLI (`meme-stocks`) is an **API client**: it does not contain business logic or access the database directly. It requires a running backend and issues HTTP requests to the REST API. This keeps a single source of truth and avoids duplicating service logic.

### Design Principles

- **API-first**: Every CLI command maps to one or more API endpoints. No direct imports of services or repositories.
- **Stateless**: The CLI has no local state; all data comes from the backend.
- **Scriptable**: All commands work non-interactively (no prompts, no TTY required). JSON output enables piping to `jq` and other tools.

### Component Layout

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI (meme-stocks)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Commands   │  │ HTTP Client │  │  Output Formatters      │  │
│  │  (argparse/ │──│  (requests/ │  │  (table, JSON)          │  │
│  │   click/    │  │   httpx)    │  │                         │  │
│  │   typer)    │  │             │  │                         │  │
│  └─────────────┘  └──────┬──────┘  └─────────────────────────┘  │
└──────────────────────────┼──────────────────────────────────────┘
                           │ HTTP
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (running)                     │
│                    GET/POST /api/... endpoints                   │
└─────────────────────────────────────────────────────────────────┘
```

### Suggested Structure

```
backend/
├── cli/
│   ├── __init__.py
│   ├── main.py           # Entry point, top-level parser
│   ├── client.py         # HTTP client wrapper (base URL, auth, error handling)
│   ├── commands/
│   │   ├── stocks.py     # stocks list, show, add
│   │   ├── trades.py     # trades list, create, close
│   │   ├── jobs.py       # jobs reddit, prices, notifications, runs, recent-posts
│   │   ├── symbols.py    # symbols refresh, stats
│   │   └── ...
│   └── output.py         # Table and JSON formatters
```

### Command Hierarchy

- **Resource-based**: `meme-stocks <resource> <action> [args]` (e.g. `stocks list`, `trades create`).
- **Top-level shortcuts**: Frequently used commands (`health`, `analysis`, `portfolio`, `sentiment SYMBOL`, `prices SYMBOL`) stay at top level for brevity.
- **Config**: Base URL from `MEME_STOCKS_API_URL` or `--base-url`; output format from `MEME_STOCKS_OUTPUT` or `--output json|table`.

### Output and Errors

- **Table** (default): Human-readable tables for list endpoints. Columns adapt to terminal width; truncate or wrap as needed.
- **JSON** (`--output json`): Raw JSON for scripting.
- **Errors**: Connection failures → exit 3, clear message ("Backend not reachable. Is the server running?"). API 4xx/5xx → exit 1 or 2, display `error_type` and `message` from the response.

### Checklist for Adding a CLI Command

- [ ] Add subcommand under the appropriate resource (or top-level).
- [ ] Map to existing API endpoint(s); no new backend logic for CLI-only use.
- [ ] Support both table and JSON output.
- [ ] Handle connection errors and API errors with clear messages and correct exit codes.
- [ ] Provide `--help` for the command.
- [ ] Add a test that exercises the command (with mocked HTTP or against a test server).

---

## Pattern: Adding a New Model

**Location**: `backend/app/models/{name}.py`

```python
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from backend.app.data.database import Base


class MyNewModel(Base):
    """Brief description of what this model represents."""

    __tablename__ = "my_new_models"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Required fields
    name = Column(String, nullable=False)
    value = Column(Float, nullable=False)

    # Optional fields
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    # Foreign key example
    stock_symbol = Column(String, ForeignKey("stocks.symbol"), nullable=False)

    # Timestamps (always include these)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=True, onupdate=lambda: datetime.now(timezone.utc))

    # Relationship example
    stock = relationship("Stock", back_populates="my_new_models")
```

**Checklist**:
- [ ] Uses `from __future__ import annotations`
- [ ] Has docstring
- [ ] Uses `timezone.utc` for datetime defaults
- [ ] Nullable fields explicitly marked
- [ ] Foreign keys have corresponding relationships

---

## Pattern: Adding a Repository

**Location**: `backend/app/data/repositories/{name}_repo.py`

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy.orm import Session

from backend.app.models.my_new_model import MyNewModel


class MyNewModelRepository:
    """Data access layer for MyNewModel."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, id: int) -> MyNewModel | None:
        """Get a single record by ID, or None if not found."""
        return self.session.query(MyNewModel).filter(MyNewModel.id == id).first()

    def get_all(self) -> Sequence[MyNewModel]:
        """Get all records."""
        return self.session.query(MyNewModel).all()

    def get_by_symbol(self, symbol: str) -> Sequence[MyNewModel]:
        """Get all records for a stock symbol."""
        return (
            self.session.query(MyNewModel)
            .filter(MyNewModel.stock_symbol == symbol)
            .all()
        )

    def create(self, model: MyNewModel) -> MyNewModel:
        """Create a new record."""
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return model

    def delete(self, model: MyNewModel) -> None:
        """Delete a record."""
        self.session.delete(model)
        self.session.commit()
```

**Checklist**:
- [ ] Constructor takes `Session`
- [ ] All methods have type hints
- [ ] All methods have docstrings
- [ ] Returns `None` (not exception) when record not found
- [ ] Uses `Sequence` for list returns (not `list`)

---

## Pattern: Adding a Service

**Location**: `backend/app/services/{name}_service.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from backend.app.config import get_settings
from backend.app.utils.errors import ValidationError


# Output dataclass (never return ORM models from services)
@dataclass(frozen=True)
class MyNewModelResult:
    """Result object for MyNewModel operations."""
    id: int
    name: str
    value: float
    created_at: datetime


# Protocol for dependency injection (optional but recommended)
class MyNewModelRepoProtocol(Protocol):
    def get_by_id(self, id: int) -> object | None: ...
    def create(self, model: object) -> object: ...


def calculate_something(value: float, multiplier: float | None = None) -> float:
    """Pure function for business logic.

    Pure functions are preferred because they are:
    - Easy to test
    - Easy to understand
    - Have no side effects
    """
    settings = get_settings()
    if multiplier is None:
        multiplier = settings.some_threshold
    return value * multiplier


class MyNewModelService:
    """Service for MyNewModel business logic."""

    def __init__(self, repo: MyNewModelRepoProtocol) -> None:
        self.repo = repo

    def get_by_id(self, id: int) -> MyNewModelResult | None:
        """Get a model by ID, returning None if not found."""
        model = self.repo.get_by_id(id)
        if model is None:
            return None
        return MyNewModelResult(
            id=model.id,
            name=model.name,
            value=model.value,
            created_at=model.created_at,
        )

    def create(self, name: str, value: float) -> MyNewModelResult:
        """Create a new model with validation."""
        if not name:
            raise ValidationError("Name cannot be empty")
        if value < 0:
            raise ValidationError("Value must be non-negative")

        # Create and save
        from backend.app.models.my_new_model import MyNewModel
        model = MyNewModel(name=name, value=value)
        saved = self.repo.create(model)

        return MyNewModelResult(
            id=saved.id,
            name=saved.name,
            value=saved.value,
            created_at=saved.created_at,
        )
```

**Checklist**:
- [ ] Returns dataclasses, not ORM models
- [ ] Uses frozen dataclasses for immutability
- [ ] Pure functions for calculation logic
- [ ] Gets thresholds from `get_settings()`, not hardcoded
- [ ] Raises custom exceptions for validation errors
- [ ] Has type hints on all methods

---

## Pattern: Adding an API Route

**Location**: `backend/app/api/{name}.py`

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.data.database import get_db
from backend.app.data.repositories.my_new_model_repo import MyNewModelRepository
from backend.app.services.my_new_model_service import MyNewModelService
from backend.app.utils.errors import ValidationError


router = APIRouter(prefix="/api/my-new-models", tags=["my-new-models"])


# Request/Response models (Pydantic)
class CreateMyNewModelRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Name of the model")
    value: float = Field(..., ge=0, description="Value must be non-negative")


class MyNewModelResponse(BaseModel):
    id: int
    name: str
    value: float
    created_at: str  # ISO format string for JSON


# Helper to build service (keeps routes clean)
def _get_service(db: Session) -> MyNewModelService:
    repo = MyNewModelRepository(db)
    return MyNewModelService(repo)


@router.get("", response_model=list[MyNewModelResponse])
def list_my_new_models(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[MyNewModelResponse]:
    """List all models."""
    service = _get_service(db)
    results = service.get_all()[:limit]
    return [
        MyNewModelResponse(
            id=r.id,
            name=r.name,
            value=r.value,
            created_at=r.created_at.isoformat(),
        )
        for r in results
    ]


@router.get("/{id}", response_model=MyNewModelResponse)
def get_my_new_model(
    id: int,
    db: Session = Depends(get_db),
) -> MyNewModelResponse:
    """Get a single model by ID."""
    service = _get_service(db)
    result = service.get_by_id(id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Model with id {id} not found")
    return MyNewModelResponse(
        id=result.id,
        name=result.name,
        value=result.value,
        created_at=result.created_at.isoformat(),
    )


@router.post("", response_model=MyNewModelResponse, status_code=201)
def create_my_new_model(
    request: CreateMyNewModelRequest,
    db: Session = Depends(get_db),
) -> MyNewModelResponse:
    """Create a new model."""
    service = _get_service(db)
    try:
        result = service.create(name=request.name, value=request.value)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return MyNewModelResponse(
        id=result.id,
        name=result.name,
        value=result.value,
        created_at=result.created_at.isoformat(),
    )
```

**Register in main.py**:
```python
from backend.app.api.my_new_model import router as my_new_model_router
app.include_router(my_new_model_router)
```

**Checklist**:
- [ ] Uses `APIRouter` with prefix and tags
- [ ] Request/Response models are Pydantic `BaseModel`
- [ ] Validation in Pydantic models (Field constraints)
- [ ] Delegates to service, no business logic in route
- [ ] Catches service exceptions and converts to HTTPException
- [ ] Returns appropriate status codes (201 for create, 404 for not found)
- [ ] Registered in `main.py`

---

## Pattern: Adding Tests

**Location**: `backend/tests/test_{feature}.py`

**Coverage and test types**:

- **Target**: 80%+ line coverage on `backend/app`. Run `pytest backend/tests/ --cov=backend/app --cov-report=term-missing` to measure.
- **Prioritize**: Consult the "Test coverage opportunities" table in this section for modules with the lowest coverage and suggested tests.
- **Unit tests** (`@pytest.mark.unit`): Fast, isolated; test pure functions or logic with mocked dependencies. No DB, no external APIs.
- **Integration tests** (`@pytest.mark.integration`): Hit DB or API routes. Use `TestClient` for endpoints; use test DB or mocks for external services. Mock Reddit/Yahoo/SEC when possible.

```python
from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.my_new_model_service import calculate_something


client = TestClient(app)


# --- Unit tests for pure functions ---

def test_calculate_something_basic() -> None:
    """Test the pure calculation function."""
    result = calculate_something(10.0, multiplier=2.0)
    assert result == 20.0


def test_calculate_something_uses_default() -> None:
    """Test that default multiplier is used from config."""
    result = calculate_something(10.0)
    # Don't assert exact value since it comes from config
    assert result > 0


# --- Integration tests for API endpoints ---

def test_list_my_new_models_empty() -> None:
    """Test listing when no models exist."""
    response = client.get("/api/my-new-models")
    assert response.status_code == 200
    assert response.json() == []


def test_get_my_new_model_not_found() -> None:
    """Test 404 when model doesn't exist."""
    response = client.get("/api/my-new-models/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_my_new_model_success() -> None:
    """Test successful creation."""
    response = client.post(
        "/api/my-new-models",
        json={"name": "Test Model", "value": 42.5},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Model"
    assert data["value"] == 42.5
    assert "id" in data


def test_create_my_new_model_validation_error() -> None:
    """Test validation error for invalid input."""
    response = client.post(
        "/api/my-new-models",
        json={"name": "", "value": -1},
    )
    assert response.status_code == 422  # Pydantic validation


# --- Tests with mocked dependencies ---

@dataclass
class MockModel:
    id: int
    name: str
    value: float
    created_at: datetime


class MockRepository:
    """Mock repository for unit testing services."""

    def __init__(self, models: list[MockModel] | None = None):
        self.models = models or []

    def get_by_id(self, id: int) -> MockModel | None:
        return next((m for m in self.models if m.id == id), None)

    def create(self, model: object) -> MockModel:
        new_model = MockModel(
            id=len(self.models) + 1,
            name=model.name,
            value=model.value,
            created_at=datetime.now(timezone.utc),
        )
        self.models.append(new_model)
        return new_model


def test_service_get_by_id_found() -> None:
    """Test service returns result when model exists."""
    from backend.app.services.my_new_model_service import MyNewModelService

    mock_model = MockModel(
        id=1,
        name="Test",
        value=10.0,
        created_at=datetime.now(timezone.utc),
    )
    repo = MockRepository([mock_model])
    service = MyNewModelService(repo)

    result = service.get_by_id(1)
    assert result is not None
    assert result.name == "Test"


def test_service_get_by_id_not_found() -> None:
    """Test service returns None when model doesn't exist."""
    from backend.app.services.my_new_model_service import MyNewModelService

    repo = MockRepository([])
    service = MyNewModelService(repo)

    result = service.get_by_id(999)
    assert result is None
```

**Test coverage opportunities** — When improving coverage, target these gaps first. Run `pytest backend/tests/ --cov=backend/app --cov-report=term-missing` to refresh the analysis:

| Module | Priority | Gap | Suggested tests |
|--------|----------|-----|-----------------|
| `api/symbol_universe.py` | High | 57% — error paths, refresh API | Test ExternalAPIError, DataAccessError handling; refresh failure; stats endpoint errors |
| `services/scheduler_service.py` | High | 66% — catch-up, job execution | Test catch-up logic with mocked job_repo; job failure handling; price/notification job paths |
| `services/symbol_universe_service.py` | High | 69% — refresh, SEC parsing | Test refresh failure paths; SEC response parsing edge cases; empty/invalid data |
| `api/paper_trading.py` | Medium | 82% — error paths | Test 404 on trade close; validation errors; portfolio edge cases |
| `api/jobs.py` | Medium | 85% — exception handlers | Test 500 on job failure; scheduler unavailable (503) |
| `services/paper_trading_service.py` | Medium | 88% — exit trade, portfolio | Test trade not found; portfolio with no trades |
| `data/repositories/reddit_post_repo.py` | Medium | 78% — error paths | Test DataAccessError on commit/flush |
| `data/repositories/reddit_symbol_mention_repo.py` | Medium | 78% | Test add/get error paths |
| `data/database.py` | Low | 80% — migrations | Test migration idempotency; skip on :memory: |
| `main.py` | Low | 77% — lifespan, SPA | Test SPA routing; frontend mount when dist exists |

**Checklist**:
- [ ] Uses `from __future__ import annotations`
- [ ] All test functions have type hints (`: None`)
- [ ] Each test has a docstring explaining what it tests
- [ ] Tests both happy path and error cases
- [ ] Uses mocks for unit testing services in isolation
- [ ] Uses `TestClient` for API integration tests
- [ ] Uses `datetime.now(timezone.utc)` for timestamps
- [ ] Mark unit tests with `@pytest.mark.unit`, integration with `@pytest.mark.integration` when helpful

---

## Pattern: Error Handling

**Custom Exceptions**: `backend/app/utils/errors.py`

```python
class AppError(Exception):
    """Base exception for application errors."""
    pass


class ValidationError(AppError):
    """Raised when input validation fails."""
    pass


class NotFoundError(AppError):
    """Raised when a requested resource doesn't exist."""
    pass


class DataFetchError(AppError):
    """Raised when external API calls fail."""
    pass
```

**In Services** (external API calls):
```python
import requests
from backend.app.utils.errors import DataFetchError

def fetch_external_data(url: str) -> dict:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise DataFetchError(f"Failed to fetch from {url}: {e}") from e
```

**In API Routes**:
```python
from fastapi import HTTPException
from backend.app.utils.errors import DataFetchError, NotFoundError, ValidationError

@router.get("/{id}")
def get_item(id: int):
    try:
        return service.get_item(id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DataFetchError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

---

## Pattern: Configuration

**All configurable values go in** `backend/app/config.py`:

```python
class Settings(BaseSettings):
    # New threshold example
    my_new_threshold: float = 0.5  # Default value
    my_new_feature_enabled: bool = True
```

**Usage in code**:
```python
from backend.app.config import get_settings

def my_function():
    settings = get_settings()
    if settings.my_new_feature_enabled:
        return value * settings.my_new_threshold
```

**Never do this**:
```python
# BAD - hardcoded magic number
if value > 0.5:
    ...

# GOOD - from config
if value > settings.my_threshold:
    ...
```

---

## Database Migrations

**Location**: `backend/app/data/database.py`

This project does **not** use Alembic. Schema changes are handled as follows:

1. **New schemas** — `Base.metadata.create_all(bind=engine)` in `init_db()` creates tables from current models on startup.

2. **Schema changes** — Add a migration function (e.g. `_migrate_drop_reddit_posts_stock_symbol`) and call it from `init_db()` after `create_all()`. Use raw SQL with `text()` for DDL when needed. Run migrations only on SQLite (skip for `:memory:` or non-SQLite).

3. **Conventions** — Keep migrations idempotent (check before altering). Log failures instead of swallowing them silently when practical.

To adopt Alembic in the future, add it to requirements and initialize with `alembic init`; then generate migrations from model changes.

**Governance lock**: The `job_locks` table (see `backend/app/models/job_lock.py`) is created via `create_all()` like other models. It is used for intraday ingestion to prevent overlapping runs (scheduler and API). When moving to Postgres or formal migrations, add a migration for `job_locks` if needed.

---

## Quick Reference: File Locations

| Type | Location | Naming |
|------|----------|--------|
| CLI | `backend/cli/` | `main.py`, `client.py`, `commands/{resource}.py`, `output.py` |
| Model | `backend/app/models/{name}.py` | `snake_case.py`, class `PascalCase` |
| Repository | `backend/app/data/repositories/{name}_repo.py` | `{model}_repo.py` |
| Service | `backend/app/services/{name}_service.py` | `{feature}_service.py` |
| API Route | `backend/app/api/{name}.py` | `{resource}.py` |
| Test | `backend/tests/test_{feature}.py` | `test_{what_is_tested}.py` |
| Utility | `backend/app/utils/{name}.py` | `{purpose}.py` |
