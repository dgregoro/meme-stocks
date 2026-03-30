"""Unit tests for strategy catalog and evidence file parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.services.strategy_catalog import (
    STRATEGY_DEFINITIONS,
    StrategyEvidenceFileError,
    build_strategy_list_rows,
    load_evidence_overrides,
    rows_to_json_serializable,
)


@pytest.mark.unit
def test_strategy_definitions_count_and_ids() -> None:
    assert len(STRATEGY_DEFINITIONS) == 7
    ids = [d.strategy_id for d in STRATEGY_DEFINITIONS]
    assert ids == [f"S{i}" for i in range(1, 8)]


@pytest.mark.unit
def test_build_strategy_list_rows_defaults() -> None:
    rows = build_strategy_list_rows(None)
    s1 = next(r for r in rows if r.strategy_id == "S1")
    s3 = next(r for r in rows if r.strategy_id == "S3")
    assert s1.tooling == "implemented"
    assert s1.evidence == "not_tested"
    assert s3.tooling == "planned"
    assert s3.evidence == "n_a"


@pytest.mark.unit
def test_build_strategy_list_rows_with_override(tmp_path: Path) -> None:
    path = tmp_path / "st.json"
    path.write_text(
        json.dumps(
            {
                "S1": {
                    "evidence": "tested",
                    "verdict": "maybe",
                    "last_run_date": "2026-03-01",
                    "notes": "see log",
                }
            }
        ),
        encoding="utf-8",
    )
    ov = load_evidence_overrides(path)
    rows = build_strategy_list_rows(ov)
    s1 = next(r for r in rows if r.strategy_id == "S1")
    assert s1.evidence == "tested"
    assert s1.verdict == "maybe"
    assert s1.last_run_date == "2026-03-01"
    assert s1.notes == "see log"


@pytest.mark.unit
def test_load_evidence_invalid_evidence(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"S1": {"evidence": "bogus"}}), encoding="utf-8")
    with pytest.raises(StrategyEvidenceFileError, match="evidence"):
        load_evidence_overrides(path)


@pytest.mark.unit
def test_load_evidence_invalid_verdict(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"S2": {"evidence": "tested", "verdict": "winning"}}), encoding="utf-8")
    with pytest.raises(StrategyEvidenceFileError, match="verdict"):
        load_evidence_overrides(path)


@pytest.mark.unit
def test_rows_to_json_serializable_round_trip_keys() -> None:
    rows = build_strategy_list_rows({})
    payload = rows_to_json_serializable(rows)
    assert len(payload) == 7
    assert set(payload[0]) >= {
        "strategy_id",
        "name",
        "description",
        "tooling",
        "evidence",
    }
