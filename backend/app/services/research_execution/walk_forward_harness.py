"""Generic walk-forward orchestration: windows → callbacks → collected results.

See specs/020-shared-research-execution/walk-forward-harness.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Callable, Generic, Sequence, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class WalkForwardWindowResult(Generic[T]):
    start: date
    end: date
    metrics: T | None
    error: str | None


def run_walk_forward_windows(
    windows: Sequence[tuple[date, date]],
    callback: Callable[[date, date], T],
    *,
    strict: bool = False,
) -> list[WalkForwardWindowResult[T]]:
    """Invoke ``callback(start, end)`` for each inclusive window.

    * Default: exceptions are caught, logged at WARNING, stored in ``error``; ``metrics`` is None.
    * ``strict=True``: re-raise after logging the first failure.
    """
    out: list[WalkForwardWindowResult[T]] = []
    for start, end in windows:
        if start > end:
            msg = f"window start {start} after end {end}"
            logger.warning("walk_forward skip: %s", msg)
            out.append(WalkForwardWindowResult(start=start, end=end, metrics=None, error=msg))
            continue
        try:
            metrics = callback(start, end)
            out.append(WalkForwardWindowResult(start=start, end=end, metrics=metrics, error=None))
        except Exception as e:
            logger.exception(
                "walk_forward window failed start=%s end=%s strict=%s",
                start,
                end,
                strict,
            )
            if strict:
                raise
            err = str(e).strip() or type(e).__name__
            out.append(WalkForwardWindowResult(start=start, end=end, metrics=None, error=err))
    return out
