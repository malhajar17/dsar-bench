"""Turning matched predictions into a scorecard.

Three headline numbers, and none of them is meaningful alone:

  recall      share of the key's passages the system found. Return the whole
              archive and this is 100%.
  precision   share of what it returned that is in the key. Both annotators
              read all 615 messages for every subject, so a passage absent
              from the key was examined and rejected, not merely unseen.
              Return one certain passage and this is 100%.
  decoy rate  share of the explicitly-ruled-out passages it handed over. These
              are adjudicated wrong answers -- a namesake, or a role title that
              at that date denotes a different person -- so unlike precision
              this number does not inherit our own recall misses.

The breakdowns are where the diagnosis lives. A system that scores well on T0
and T7 and badly on T2 is matching names, not reading.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field

from .corpus import Entry, Key
from .matching import assign
from .submission import Prediction

HIT = "hit"
DECOY = "decoy"
SPURIOUS = "spurious"
UNLOCATABLE = "unlocatable"


@dataclass
class Counts:
    positives: int = 0
    found: int = 0
    negatives: int = 0
    decoys: int = 0
    returned: int = 0
    hits: int = 0
    spurious: int = 0
    unlocatable: int = 0

    @property
    def recall(self) -> float:
        return self.found / self.positives if self.positives else float("nan")

    @property
    def precision(self) -> float:
        return self.hits / self.returned if self.returned else float("nan")

    @property
    def decoy_rate(self) -> float:
        return self.decoys / self.negatives if self.negatives else float("nan")

    @property
    def f1(self) -> float:
        r, p = self.recall, self.precision
        return 2 * r * p / (r + p) if r and p and (r + p) else 0.0

    def as_dict(self) -> dict:
        d = asdict(self)
        d.update(recall=self.recall, precision=self.precision,
                 decoy_rate=self.decoy_rate, f1=self.f1)
        return d


@dataclass
class Scorecard:
    overall: Counts
    per_subject: dict[str, Counts]
    per_tier: dict[str, Counts]
    named: Counts
    unnamed: Counts
    misses: list[Entry] = field(default_factory=list)
    decoys: list[tuple[Prediction, Entry]] = field(default_factory=list)
    spurious: list[Prediction] = field(default_factory=list)
    unlocatable: list[Prediction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "overall": self.overall.as_dict(),
            "per_subject": {k: v.as_dict() for k, v in self.per_subject.items()},
            "per_tier": {k: v.as_dict() for k, v in self.per_tier.items()},
            "named_in_passage": self.named.as_dict(),
            "not_named_in_passage": self.unnamed.as_dict(),
            "counts": {"misses": len(self.misses), "decoys": len(self.decoys),
                       "spurious": len(self.spurious),
                       "unlocatable": len(self.unlocatable)},
            "warnings": self.warnings,
        }


def score(preds: list[Prediction], key: Key,
          warnings: list[str] | None = None) -> Scorecard:
    entries = key.entries
    p2e, e2p = assign(preds, entries)

    overall = Counts()
    per_subject: dict[str, Counts] = defaultdict(Counts)
    per_tier: dict[str, Counts] = defaultdict(Counts)
    named, unnamed = Counts(), Counts()
    card = Scorecard(overall=overall, per_subject=per_subject, per_tier=per_tier,
                     named=named, unnamed=unnamed, warnings=list(warnings or []))

    for j, e in enumerate(entries):
        buckets = [per_subject[e.subject_id], overall,
                   named if e.named else unnamed]
        if e.positive:
            buckets.append(per_tier[e.tier])
        for c in buckets:
            if e.positive:
                c.positives += 1
                c.found += j in e2p
            else:
                c.negatives += 1
                c.decoys += j in e2p
        if e.positive and j not in e2p:
            card.misses.append(e)

    for i, p in enumerate(preds):
        c_all = [per_subject[p.subject_id], overall]
        for c in c_all:
            c.returned += 1
        if not p.located:
            for c in c_all:
                c.unlocatable += 1
            card.unlocatable.append(p)
            continue
        j = p2e.get(i)
        if j is None:
            for c in c_all:
                c.spurious += 1
            card.spurious.append(p)
        elif entries[j].positive:
            for c in c_all:
                c.hits += 1
        else:
            card.decoys.append((p, entries[j]))

    card.per_subject = dict(per_subject)
    card.per_tier = dict(per_tier)
    return card
