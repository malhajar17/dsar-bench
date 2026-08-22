"""Rendering a scorecard for a human."""

from __future__ import annotations

import textwrap

from .corpus import Key
from .metrics import Counts, Scorecard

TIER_NAME = {
    "T0": "explicit name in the passage",
    "T1": "pronoun refers to him",
    "T2": "role or description refers to him",
    "T3": "quote attribution",
    "T4A": "forwarded / nested content",
    "T4B": "signature or footer",
    "T5": "multi-hop inference",
    "T6": "cross-document identity join",
    "T7": "he wrote it himself",
}


def _pct(x: float) -> str:
    return "  n/a" if x != x else f"{x:6.1%}"


def _row(label: str, c: Counts, width: int = 26) -> str:
    return (f"{label[:width]:<{width}}{c.positives:>6}{c.found:>7}{_pct(c.recall):>9}"
            f"{c.returned:>10}{c.hits:>7}{_pct(c.precision):>9}"
            f"{c.negatives:>6}{c.decoys:>7}{_pct(c.decoy_rate):>9}")


def _head(width: int = 26) -> str:
    return (f"{'':<{width}}{'key':>6}{'found':>7}{'recall':>9}"
            f"{'returned':>10}{'in key':>7}{'prec':>9}"
            f"{'traps':>6}{'hit':>7}{'decoy':>9}")


def render(card: Scorecard, key: Key, examples: int = 5) -> str:
    o = card.overall
    out: list[str] = []
    out.append("=" * 96)
    out.append("DSAR-BENCH SCORECARD")
    out.append("=" * 96)
    out.append("")
    out.append(f"  recall      {_pct(o.recall).strip():>7}   "
               f"{o.found} of {o.positives} passages in the key")
    out.append(f"  precision   {_pct(o.precision).strip():>7}   "
               f"{o.hits} of {o.returned} returned passages are in the key")
    out.append(f"  decoy rate  {_pct(o.decoy_rate).strip():>7}   "
               f"{o.decoys} of {o.negatives} explicitly wrong answers handed over")
    out.append(f"  F1          {o.f1:>7.1%}")
    if o.unlocatable:
        out.append(f"  NOTE: {o.unlocatable} returned passages could not be found "
                   f"in the document they cite")
    out.append("")

    out.append("BY SUBJECT")
    out.append(_head())
    for sid, c in sorted(card.per_subject.items(),
                         key=lambda kv: kv[0][0] + kv[0][1:].zfill(2)):
        out.append(_row(key.subjects[sid]["display"], c))
    out.append(_row("ALL", o))
    out.append("")

    out.append("RECALL BY DIFFICULTY  (what kind of reasoning the passage needs)")
    out.append(f"{'':<30}{'key':>6}{'found':>7}{'recall':>9}")
    for tier, c in sorted(card.per_tier.items()):
        out.append(f"{tier + '  ' + TIER_NAME.get(tier, ''):<30}"
                   f"{c.positives:>6}{c.found:>7}{_pct(c.recall):>9}")
    out.append("")

    out.append("THE PART THAT SEPARATES READING FROM SEARCHING")
    for label, c in (("subject named in the passage", card.named),
                     ("subject NOT named in the passage", card.unnamed)):
        out.append(f"  {label:<36}{c.found:>5} / {c.positives:<5}{_pct(c.recall)}")
    out.append("")

    if examples:
        if card.decoys:
            out.append(f"WRONG PEOPLE HANDED OVER  ({len(card.decoys)}, showing "
                       f"{min(examples, len(card.decoys))})")
            for p, e in card.decoys[:examples]:
                out.append(f"  [{key.subjects[e.subject_id]['display']}] "
                           f"\"{' '.join(e.text.split())[:70]}\"")
                out.append(textwrap.fill(e.rationale, 90,
                                         initial_indent="      why not him: ",
                                         subsequent_indent="      ")[:300])
            out.append("")
        if card.misses:
            hard = [e for e in card.misses if not e.named] or card.misses
            out.append(f"MISSED  ({len(card.misses)}, showing "
                       f"{min(examples, len(hard))} where he is not named)")
            for e in hard[:examples]:
                out.append(f"  [{key.subjects[e.subject_id]['display']} {e.tier}] "
                           f"\"{' '.join(e.text.split())[:70]}\"")
            out.append("")
        if card.spurious:
            out.append(f"RETURNED BUT NOT IN THE KEY  ({len(card.spurious)}, showing "
                       f"{min(examples, len(card.spurious))})")
            for p in card.spurious[:examples]:
                out.append(f"  [{key.subjects[p.subject_id]['display']}] "
                           f"\"{' '.join(p.text.split())[:70]}\"")
            out.append("")

    if card.warnings:
        out.append(f"WARNINGS ({len(card.warnings)})")
        out += [f"  {w}" for w in card.warnings[:10]]
        if len(card.warnings) > 10:
            out.append(f"  ... and {len(card.warnings) - 10} more")
        out.append("")

    return "\n".join(out)
