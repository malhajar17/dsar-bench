"""Deciding when a predicted passage and a key entry are the same passage.

Boundaries are a matter of taste -- our own two annotators only agreed on
exact spans 58% of the time -- so the rule is overlap, not equality. Two
passages match when their intersection covers at least OVERLAP of the shorter
one, in the same block of the same document for the same subject.

Assignment is one-to-one and greedy by overlap. Without that, a system could
return one passage spanning a whole email and claim every key entry inside it.
"""

from __future__ import annotations

from .corpus import Entry
from .submission import Prediction

OVERLAP = 0.5

Span = tuple[int, int]


def overlap_frac(a: Span, b: Span) -> float:
    """Intersection as a fraction of the shorter span."""
    inter = min(a[1], b[1]) - max(a[0], b[0])
    if inter <= 0:
        return 0.0
    shorter = min(a[1] - a[0], b[1] - b[0])
    return inter / shorter if shorter > 0 else 0.0


def assign(preds: list[Prediction], entries: list[Entry],
           threshold: float = OVERLAP) -> tuple[dict[int, int], dict[int, int]]:
    """Greedy one-to-one match between predictions and key entries.

    Returns (pred_index -> entry_index, entry_index -> pred_index).
    """
    buckets: dict[tuple[str, str, int], list[int]] = {}
    for j, e in enumerate(entries):
        buckets.setdefault((e.subject_id, e.doc_id, e.block_id), []).append(j)

    scored: list[tuple[float, int, int]] = []
    for i, p in enumerate(preds):
        if not p.located:
            continue
        for j in buckets.get((p.subject_id, p.doc_id, p.block_id), ()):
            f = overlap_frac(p.span, entries[j].span)  # type: ignore[arg-type]
            if f >= threshold:
                scored.append((f, i, j))

    scored.sort(key=lambda t: (-t[0], t[1], t[2]))
    p2e: dict[int, int] = {}
    e2p: dict[int, int] = {}
    for f, i, j in scored:
        if i in p2e or j in e2p:
            continue
        p2e[i] = j
        e2p[j] = i
    return p2e, e2p
