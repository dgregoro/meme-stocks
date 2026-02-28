"""Optional ticker NER: extract candidate symbols via a HuggingFace NER model.

Lazy-loads model/tokenizer so importing this module does not load weights.
Enable with ENABLE_TICKER_NER=true. Requires transformers and torch (not in base requirements).
"""

from __future__ import annotations

import logging
import re
from typing import Set

logger = logging.getLogger(__name__)

# 1-5 uppercase letters (ticker-like span from NER)
NER_TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}$")


def extract_ner_candidates(text: str) -> Set[str]:
    """Extract candidate ticker symbols from text using NER model (if available).

    Model is lazy-loaded on first call. If the model or dependencies are missing,
    returns an empty set and logs a debug message.

    Returns:
        Set of uppercase candidate symbols (union with regex is done by caller).
    """
    try:
        from transformers import pipeline
    except ImportError:
        logger.debug("ticker_ner: transformers not installed, skipping NER")
        return set()

    try:
        # Lazy-load: pipeline loads model on first use
        if not hasattr(extract_ner_candidates, "_pipe"):
            extract_ner_candidates._pipe = pipeline(  # type: ignore[attr-defined]
                "token-classification",
                model="Jean-Baptiste/roberta-ticker",
                aggregation_strategy="simple",
            )
        pipe = extract_ner_candidates._pipe  # type: ignore[attr-defined]
        entities = pipe(text)
        candidates: Set[str] = set()
        for ent in entities:
            if isinstance(ent, dict):
                label = ent.get("entity_group") or ent.get("entity", "")
                word = (ent.get("word") or "").strip().upper()
            else:
                continue
            if "ticker" in label.lower() and word and NER_TICKER_PATTERN.match(word):
                candidates.add(word)
        return candidates
    except Exception as exc:
        logger.debug("ticker_ner: NER failed (%s), skipping", exc)
        return set()
