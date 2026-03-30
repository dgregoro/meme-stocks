"""Static catalog of daily-frequency research strategies (S1–S7) plus optional evidence file.

See docs/STRATEGY_EXPLORATION.md for narrative; this module is the machine-readable
summary used by ``python -m backend.app.cli strategies list``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

ToolingLevel = Literal["implemented", "planned"]

ALLOWED_EVIDENCE: Final[frozenset[str]] = frozenset({"not_tested", "in_progress", "tested"})
ALLOWED_VERDICT: Final[frozenset[str]] = frozenset({"kill", "maybe", "pursue"})
KNOWN_IDS: Final[frozenset[str]] = frozenset(f"S{i}" for i in range(1, 8))


@dataclass(frozen=True)
class StrategyDefinition:
    strategy_id: str
    name: str
    description: str
    primary_data: str
    tooling: ToolingLevel
    cli_hint: str | None


STRATEGY_DEFINITIONS: tuple[StrategyDefinition, ...] = (
    StrategyDefinition(
        "S1",
        "Volume vs. realized-vol mismatch",
        "Compare rolling realized volatility of daily returns to volume (e.g. volume z-score). "
        "Hypothesis: mismatch regimes (high vol/low volume or the inverse) predict different "
        "forward return profiles.",
        "Daily OHLCV",
        "implemented",
        "evaluate daily-strategy s1 | s1-merit | eval-bundle --strategy s1",
    ),
    StrategyDefinition(
        "S2",
        "Gap ecology",
        "Classify overnight gaps using daily OHLC (size vs prior range, trend vs MA). "
        "Hypothesis: forward expectancy differs by gap type, not just up/down gap.",
        "Daily OHLC (open vs prior close)",
        "implemented",
        "evaluate daily-strategy s2 | s2-merit | eval-bundle --strategy s2",
    ),
    StrategyDefinition(
        "S3",
        "Volatility term-structure regime",
        "Label regimes from VIX vs medium-term vol (e.g. VIX3M) and relate to equity "
        "rule performance out-of-sample.",
        "VIX + longer vol index + equity returns",
        "implemented",
        "backfill vol-term | evaluate daily-strategy s3 | s3-merit | eval-bundle --strategy s3",
    ),
    StrategyDefinition(
        "S4",
        "Calendar / scheduled-event skeleton",
        "Scheduled calendar flags (e.g. OpEx, FOMC) interact with returns; pre-register "
        "flags and avoid post-hoc flag shopping.",
        "Daily returns + calendar flags",
        "planned",
        None,
    ),
    StrategyDefinition(
        "S5",
        "Cross-sectional dispersion",
        "Panel-level dispersion or factor-like structure across a defined universe.",
        "Panel of daily returns + universe rules",
        "planned",
        None,
    ),
    StrategyDefinition(
        "S6",
        "Slow pairs / relative value",
        "Two (or few) daily series with corporate-action and two-leg execution awareness.",
        "Paired daily returns",
        "planned",
        None,
    ),
    StrategyDefinition(
        "S7",
        "Rule discovery on daily features",
        "Search over rules with strict hold-out and complexity limits (high overfitting risk).",
        "Daily feature matrix",
        "planned",
        None,
    ),
)


class StrategyEvidenceFileError(ValueError):
    """Invalid or unreadable strategy evidence JSON."""


def _normalize_strategy_key(key: str) -> str:
    return key.strip().upper()


def _normalize_evidence_token(raw: str) -> str:
    s = raw.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {"nottested": "not_tested", "no_results": "not_tested", "none": "not_tested"}
    return aliases.get(s, s)


def load_evidence_overrides(path: Path | None) -> dict[str, dict[str, Any]]:
    """Load optional per-strategy evidence metadata from JSON.

    Expected shape (keys are strategy IDs, values are objects)::

        {
          "S1": {
            "evidence": "tested",
            "verdict": "maybe",
            "last_run_date": "2026-03-15",
            "notes": "Logged in docs/STRATEGY_EXPLORATION.md"
          }
        }

    Unknown top-level keys (not S1..S7) are ignored. Empty or missing file returns ``{}``.
    """
    if path is None or not path.is_file():
        return {}
    try:
        top = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StrategyEvidenceFileError(f"Invalid JSON in strategy evidence file {path}: {exc}") from exc
    if not isinstance(top, dict):
        raise StrategyEvidenceFileError(f"Strategy evidence file {path} must be a JSON object at the top level.")
    out: dict[str, dict[str, Any]] = {}
    for key, val in top.items():
        sid = _normalize_strategy_key(str(key))
        if sid not in KNOWN_IDS:
            continue
        if not isinstance(val, dict):
            raise StrategyEvidenceFileError(f"Entry {sid!r} in {path} must be a JSON object, not {type(val).__name__}.")
        out[sid] = dict(val)
    return _validate_evidence_entries(out, path)


def _validate_evidence_entries(data: dict[str, dict[str, Any]], path: Path) -> dict[str, dict[str, Any]]:
    for sid, entry in data.items():
        ev = entry.get("evidence")
        if ev is not None:
            if not isinstance(ev, str):
                raise StrategyEvidenceFileError(f"{sid}.evidence in {path} must be a string, not {type(ev).__name__}.")
            ev_n = _normalize_evidence_token(ev)
            if ev_n not in ALLOWED_EVIDENCE:
                raise StrategyEvidenceFileError(
                    f"{sid}.evidence in {path} must be one of " f"{sorted(ALLOWED_EVIDENCE)}, got {ev!r}."
                )
            entry["evidence"] = ev_n
        vd = entry.get("verdict")
        if vd is not None:
            if not isinstance(vd, str):
                raise StrategyEvidenceFileError(
                    f"{sid}.verdict in {path} must be a string or omitted, not {type(vd).__name__}."
                )
            v_n = vd.strip().lower()
            if v_n not in ALLOWED_VERDICT:
                raise StrategyEvidenceFileError(
                    f"{sid}.verdict in {path} must be one of " f"{sorted(ALLOWED_VERDICT)}, got {vd!r}."
                )
            entry["verdict"] = v_n
        for opt_key in ("last_run_date", "notes"):
            if opt_key in entry and entry[opt_key] is not None and not isinstance(entry[opt_key], str):
                raise StrategyEvidenceFileError(
                    f"{sid}.{opt_key} in {path} must be a string or omitted, " f"not {type(entry[opt_key]).__name__}."
                )
    return data


@dataclass
class StrategyListRow:
    strategy_id: str
    name: str
    description: str
    primary_data: str
    tooling: ToolingLevel
    cli_hint: str | None
    evidence: str
    verdict: str | None = None
    last_run_date: str | None = None
    notes: str | None = None


def build_strategy_list_rows(
    overrides: dict[str, dict[str, Any]] | None = None,
) -> list[StrategyListRow]:
    """Merge static definitions with optional file overrides into display rows."""
    ov = overrides or {}
    rows: list[StrategyListRow] = []
    for d in STRATEGY_DEFINITIONS:
        o = ov.get(d.strategy_id, {})
        ev_raw = o.get("evidence")
        if isinstance(ev_raw, str):
            evidence = _normalize_evidence_token(ev_raw)
            if evidence not in ALLOWED_EVIDENCE:
                evidence = "not_tested" if d.tooling == "implemented" else "n_a"
        elif d.tooling == "planned":
            evidence = "n_a"
        else:
            evidence = "not_tested"
        verdict = o.get("verdict") if isinstance(o.get("verdict"), str) else None
        last_run = o.get("last_run_date") if isinstance(o.get("last_run_date"), str) else None
        notes = o.get("notes") if isinstance(o.get("notes"), str) else None
        rows.append(
            StrategyListRow(
                strategy_id=d.strategy_id,
                name=d.name,
                description=d.description,
                primary_data=d.primary_data,
                tooling=d.tooling,
                cli_hint=d.cli_hint,
                evidence=evidence,
                verdict=verdict,
                last_run_date=last_run,
                notes=notes,
            )
        )
    return rows


def rows_to_json_serializable(rows: list[StrategyListRow]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": r.strategy_id,
            "name": r.name,
            "description": r.description,
            "primary_data": r.primary_data,
            "tooling": r.tooling,
            "cli_hint": r.cli_hint,
            "evidence": r.evidence,
            "verdict": r.verdict,
            "last_run_date": r.last_run_date,
            "notes": r.notes,
        }
        for r in rows
    ]
