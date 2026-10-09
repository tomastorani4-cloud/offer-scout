"""Source reliability x information credibility, in the style of the Admiralty (NATO 4x4) system.

Letter = how reliable the SOURCE is (A best). Number = how credible the INFORMATION is (1 best).
We use it to decide confidence levels and to let the dashboard show how strong each signal is.
"""
from __future__ import annotations

SOURCE_RELIABILITY = {
    "operator": "A",          # data the operator owns (sales exports, checkout)
    "official_api": "A",      # marketplace/ads official API
    "ad_library": "B",
    "marketplace_public": "B",
    "csv_import": "C",        # unknown provenance unless the operator states it
    "blog_aggregator": "D",
    "synthetic": "F",
}

SIGNAL_CREDIBILITY = {
    "OPERATOR_DATA": 1,
    "SEARCH_TREND": 2,
    "AD_PERSISTENCE": 3,
    "MARKETPLACE_SALES": 3,
    "REVIEW_VELOCITY": 3,
    "COMMENT_INTENT": 4,
}


def grade(source_class: str, signal_type: str) -> str:
    return f"{SOURCE_RELIABILITY.get(source_class, 'F')}{SIGNAL_CREDIBILITY.get(signal_type, 5)}"


def is_authoritative(g: str) -> bool:
    return g.startswith("A") and g[1:] in {"1", "2"}
