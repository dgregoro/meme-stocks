"""Backfill VIX / VIX3M observations for S3 (persist + CLI orchestration)."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.app.clients.yahoo_vol_index_client import YahooVolIndexClient
from backend.app.config import get_settings
from backend.app.data.repositories.vol_term_structure_repo import VolTermStructureRepository

logger = logging.getLogger(__name__)


def backfill_vol_term_observations(
    db: Session,
    start: dt.date,
    end: dt.date,
    *,
    replace_range: bool = False,
    client: YahooVolIndexClient | None = None,
) -> dict[str, Any]:
    """Fetch aligned closes from Yahoo and upsert ``vol_term_structure_observations``."""
    if start > end:
        return {"rows_upserted": 0, "range": f"{start}..{end}", "errors": ["start after end"]}

    settings = get_settings()
    vix_sym = settings.s3_vix_symbol.strip() or "^VIX"
    v3_sym = settings.s3_vix3m_symbol.strip() or "^VIX3M"
    cli = client or YahooVolIndexClient()
    repo = VolTermStructureRepository(db)

    if replace_range:
        deleted = repo.delete_between(start, end)
        logger.info("vol_term backfill: deleted %s rows in [%s, %s]", deleted, start, end)

    errors: list[str] = []
    try:
        aligned = cli.fetch_vix_vix3m_closes(start, end, vix_symbol=vix_sym, vix3m_symbol=v3_sym)
    except Exception as exc:
        logger.warning("vol_term Yahoo fetch failed: %s", exc)
        errors.append(str(exc))
        return {"rows_upserted": 0, "range": f"{start}..{end}", "errors": errors}

    n = 0
    for d, vx, v3 in aligned:
        if start <= d <= end:
            repo.upsert_row(d, vx, v3)
            n += 1

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("vol_term backfill commit failed: %s", exc, exc_info=True)
        errors.append(str(exc))
        return {"rows_upserted": 0, "range": f"{start}..{end}", "errors": errors}

    return {"rows_upserted": n, "range": f"{start}..{end}", "errors": errors}
