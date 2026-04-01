"""S7: single-split quantile threshold grid (train thresholds, test metrics only)."""

from __future__ import annotations

import csv
import logging
import statistics
from datetime import date
from pathlib import Path
from typing import Any, Literal, cast

from backend.app.config import get_settings
from backend.app.services.research_execution import ResearchRunEnvelope

logger = logging.getLogger(__name__)

Direction = Literal["gt", "lte"]


def _infer_label_column(fieldnames: list[str] | None) -> str:
    cands = [f for f in fieldnames or [] if f.startswith("fwd_") and f.endswith("_pct")]
    if len(cands) != 1:
        raise ValueError(f"expected exactly one label column matching fwd_*_pct, found {cands!r}")
    return cands[0]


def load_matrix_csv(path: Path) -> tuple[list[dict[str, Any]], str]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"matrix file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError("empty matrix CSV")
        label = _infer_label_column(list(reader.fieldnames))
        rows: list[dict[str, Any]] = []
        for raw in reader:
            d_raw = raw.get("date", "").strip()
            if not d_raw:
                continue
            row: dict[str, Any] = {
                "date": date.fromisoformat(d_raw[:10]),
                "symbol": str(raw.get("symbol", "")).strip().upper(),
            }
            for k in reader.fieldnames:
                if k in ("date", "symbol"):
                    continue
                s = (raw.get(k) or "").strip()
                if s == "":
                    row[k] = None
                else:
                    row[k] = float(s)
            rows.append(row)
    if not rows:
        raise ValueError(f"no data rows in {path}")
    return rows, label


def _feature_keys(rows: list[dict[str, Any]], label_key: str) -> list[str]:
    skip = {"date", "symbol", label_key}
    keys: set[str] = set()
    for r in rows[: min(len(rows), 200)]:
        for k, v in r.items():
            if k in skip:
                continue
            if isinstance(v, (int, float)):
                keys.add(k)
    return sorted(keys)


def _mean(xs: list[float]) -> float | None:
    if not xs:
        return None
    return sum(xs) / len(xs)


def _signals(vals: list[float | None], thr: float, direction: Direction) -> list[bool]:
    out: list[bool] = []
    for v in vals:
        if v is None:
            out.append(False)
            continue
        fv = float(v)
        if fv != fv:  # NaN
            out.append(False)
            continue
        out.append(fv > thr if direction == "gt" else fv <= thr)
    return out


def run_quantile_rule_grid(
    rows: list[dict[str, Any]],
    *,
    train_end: date,
    label_key: str,
    ack_overfitting_risk: bool,
) -> dict[str, Any]:
    """Fit quantile thresholds on train dates only; compute metrics on test dates only.

    Raises ``ValueError`` if ``ack_overfitting_risk`` is False (CLI must set True).
    """
    if not ack_overfitting_risk:
        raise ValueError("S7 search refused: operator must set ack_overfitting_risk=True (see --ack-overfitting-risk)")

    settings = get_settings()
    nq = max(3, min(50, int(settings.s7_rule_discovery_n_quantiles)))
    cap = max(50, int(settings.s7_rule_discovery_max_rules))

    train = [r for r in rows if r["date"] <= train_end]
    test = [r for r in rows if r["date"] > train_end]
    if len(train) < 30:
        raise ValueError(f"train segment too small ({len(train)} rows); need more history before train_end")
    if len(test) < 10:
        raise ValueError(f"test segment too small ({len(test)} rows); choose earlier train_end")

    features = _feature_keys(rows, label_key)
    if not features:
        raise ValueError("no numeric feature columns found besides label")

    rule_results: list[dict[str, Any]] = []
    n_rules = 0
    hit_cap = False

    for feat in features:
        train_vals = [float(r[feat]) for r in train if r.get(feat) is not None and r.get(label_key) is not None]
        if len(train_vals) < nq * 3:
            logger.warning("S7: skip feature %s (only %s usable train points)", feat, len(train_vals))
            continue
        try:
            cuts = statistics.quantiles(train_vals, n=nq)
        except (ValueError, statistics.StatisticsError) as exc:
            logger.warning("S7: quantiles failed for %s: %s", feat, exc)
            continue

        test_feat_aln: list[float | None] = []
        test_y_aln: list[float] = []
        for r in test:
            if r.get(label_key) is None:
                continue
            test_feat_aln.append(r.get(feat))
            test_y_aln.append(float(r[label_key]))

        train_feat_aln: list[float | None] = []
        train_y_aln: list[float] = []
        for r in train:
            if r.get(label_key) is None:
                continue
            train_feat_aln.append(r.get(feat))
            train_y_aln.append(float(r[label_key]))

        for thr in cuts:
            for direction in ("gt", "lte"):
                dir_c = cast(Direction, direction)
                if n_rules >= cap:
                    hit_cap = True
                    break
                sig_tr = _signals(train_feat_aln, thr, dir_c)
                sig_te = _signals(test_feat_aln, thr, dir_c)
                tr_y_sig = [y for y, s in zip(train_y_aln, sig_tr) if s]
                tr_y_not = [y for y, s in zip(train_y_aln, sig_tr) if not s]
                te_y_sig = [y for y, s in zip(test_y_aln, sig_te) if s]
                te_y_not = [y for y, s in zip(test_y_aln, sig_te) if not s]
                rule_results.append(
                    {
                        "feature": feat,
                        "direction": direction,
                        "threshold": round(thr, 8),
                        "train_mean_when_signal": _mean(tr_y_sig),
                        "train_mean_when_not_signal": _mean(tr_y_not),
                        "train_n_signal": len(tr_y_sig),
                        "test_mean_when_signal": _mean(te_y_sig),
                        "test_mean_when_not_signal": _mean(te_y_not),
                        "test_n_signal": len(te_y_sig),
                    }
                )
                n_rules += 1
            if hit_cap:
                break
        if hit_cap:
            break

    sym = rows[0].get("symbol", "UNKNOWN")
    sym_u = sym.strip().upper() if isinstance(sym, str) else "UNKNOWN"
    d_min = min(r["date"] for r in rows)
    d_max = max(r["date"] for r in rows)
    envelope = ResearchRunEnvelope.from_context(
        run_kind="s7_rule_discovery_search",
        strategy_family="S7_rule_discovery",
        eval_start=d_min,
        eval_end=d_max,
        universe_label="rule_discovery_csv",
        symbols=[sym_u],
        cost_round_trip_bps=float(settings.research_default_round_trip_cost_bps),
        notes="single-split quantile grid; multiple testing inflates false positives",
    )

    warnings = [
        "S7 grid search is exploratory: many rules are tested; expectations under the null spike.",
        "Do not treat top test bucket mean as validated edge without pre-registration and replication.",
        "Not integrated with eval-bundle or daily_strategy merit.",
    ]
    if hit_cap:
        warnings.append(f"Stopped early at s7_rule_discovery_max_rules={cap}")

    logger.info("S7 grid: evaluated %s rules (cap=%s)", n_rules, cap)

    return {
        "kind": "s7_rule_discovery_search",
        "label_column": label_key,
        "train_end": str(train_end),
        "train_rows": len(train),
        "test_rows": len(test),
        "n_rules_evaluated": n_rules,
        "n_quantiles_setting": nq,
        "rule_results": rule_results,
        "research_envelope": envelope.to_json_dict(),
        "warnings": warnings,
    }


def run_search_from_matrix_path(
    matrix_path: Path,
    *,
    train_end: date,
    label_key: str | None,
    ack_overfitting_risk: bool,
) -> dict[str, Any]:
    rows, inferred_label = load_matrix_csv(matrix_path)
    lab = (label_key or inferred_label).strip()
    if lab != inferred_label:
        raise ValueError(f"label {lab!r} must match CSV label column {inferred_label!r}")
    return run_quantile_rule_grid(
        rows,
        train_end=train_end,
        label_key=lab,
        ack_overfitting_risk=ack_overfitting_risk,
    )
