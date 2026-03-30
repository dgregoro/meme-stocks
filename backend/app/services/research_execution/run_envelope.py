"""Attach reproducible metadata to research runs (JSON-serializable).

Strategy-specific code can embed or store this alongside merit reports or future simulators.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


def _symbols_fingerprint(symbols: list[str]) -> str:
    norm = sorted({s.strip().upper() for s in symbols if s and str(s).strip()})
    payload = json.dumps(norm, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()[:16]


@dataclass(frozen=True)
class ResearchRunEnvelope:
    """Cross-strategy run metadata (no PnL — only audit / reproducibility context)."""

    run_kind: str
    strategy_family: str
    eval_start: date
    eval_end: date
    universe_label: str
    symbol_count: int
    symbols_fingerprint_sha256_16: str
    cost_round_trip_bps: float
    git_sha_or_version: str | None = None
    notes: str | None = None

    @staticmethod
    def from_context(
        *,
        run_kind: str,
        strategy_family: str,
        eval_start: date,
        eval_end: date,
        universe_label: str,
        symbols: list[str],
        cost_round_trip_bps: float,
        notes: str | None = None,
    ) -> ResearchRunEnvelope:
        fp = _symbols_fingerprint(symbols)
        version = os.environ.get("APP_VERSION") or os.environ.get("GIT_SHA")
        return ResearchRunEnvelope(
            run_kind=run_kind,
            strategy_family=strategy_family,
            eval_start=eval_start,
            eval_end=eval_end,
            universe_label=universe_label,
            symbol_count=len({s.strip().upper() for s in symbols if s and str(s).strip()}),
            symbols_fingerprint_sha256_16=fp,
            cost_round_trip_bps=float(cost_round_trip_bps),
            git_sha_or_version=version,
            notes=notes,
        )

    def to_json_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["eval_start"] = str(self.eval_start)
        d["eval_end"] = str(self.eval_end)
        return d

    @staticmethod
    def from_json_dict(d: dict[str, Any]) -> ResearchRunEnvelope:
        return ResearchRunEnvelope(
            run_kind=str(d["run_kind"]),
            strategy_family=str(d["strategy_family"]),
            eval_start=date.fromisoformat(str(d["eval_start"])[:10]),
            eval_end=date.fromisoformat(str(d["eval_end"])[:10]),
            universe_label=str(d["universe_label"]),
            symbol_count=int(d["symbol_count"]),
            symbols_fingerprint_sha256_16=str(d["symbols_fingerprint_sha256_16"]),
            cost_round_trip_bps=float(d["cost_round_trip_bps"]),
            git_sha_or_version=d.get("git_sha_or_version"),
            notes=d.get("notes"),
        )
