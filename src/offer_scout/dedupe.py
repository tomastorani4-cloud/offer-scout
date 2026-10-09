from __future__ import annotations

from difflib import SequenceMatcher

from .models import Record
from .normalize import norm_text, tokens


def _same_listing(a: Record, b: Record) -> bool:
    if a.source_platform != b.source_platform:
        return False
    if norm_text(a.seller) != norm_text(b.seller):
        return False
    return SequenceMatcher(None, norm_text(a.product_name), norm_text(b.product_name)).ratio() >= 0.92


def dedupe(records: list[Record]) -> list[Record]:
    """Collapse near-identical records from the same seller/platform into one with `variants`.

    For ads, variants measure how many creative versions a seller is running.
    The survivor keeps the strongest observed values (max runtime, max reviews).
    """
    survivors: list[Record] = []
    for rec in records:
        for kept in survivors:
            if _same_listing(kept, rec):
                kept.variants += rec.variants
                for attr in ("runtime_days", "review_count", "recent_review_count_90d", "sales_count_visible"):
                    a, b = getattr(kept, attr), getattr(rec, attr)
                    if b is not None and (a is None or b > a):
                        setattr(kept, attr, b)
                break
        else:
            survivors.append(rec)
    return survivors


def saturation_share(records: list[Record], similarity: float) -> float:
    """Share of records whose title is a near-duplicate (Jaccard) of another SELLER's title."""
    if len(records) < 2:
        return 0.0
    toks = [tokens(r.product_name) for r in records]
    dup = 0
    for i, ti in enumerate(toks):
        if not ti:
            continue
        for j, tj in enumerate(toks):
            if i == j or not tj or records[i].seller == records[j].seller:
                continue
            inter = len(ti & tj)
            union = len(ti | tj)
            if union and inter / union >= similarity:
                dup += 1
                break
    return dup / len(records)
