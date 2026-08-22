"""Loading the corpus, the subject definitions and the answer key."""

from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass, field

ROOT = pathlib.Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Entry:
    """One item of the answer key: a passage that is, or is not, the subject."""

    subject_id: str
    doc_id: str
    block_id: int
    span: tuple[int, int]
    text: str
    tier: str
    positive: bool
    rationale: str = ""
    gdpr_category: str = ""

    @property
    def named(self) -> bool:
        """Whether the subject is named inside the passage itself.

        Set by load_key, which owns the subject patterns. Cached on the
        instance because the regex work is not free over ~1,500 entries.
        """
        return self._named  # type: ignore[attr-defined]


@dataclass
class Key:
    subjects: dict[str, dict]
    positives: list[Entry]
    negatives: list[Entry]
    docs: dict[str, dict]

    @property
    def entries(self) -> list[Entry]:
        return self.positives + self.negatives

    def by_subject(self, sid: str) -> tuple[list[Entry], list[Entry]]:
        return ([e for e in self.positives if e.subject_id == sid],
                [e for e in self.negatives if e.subject_id == sid])


def load_corpus(path: str | pathlib.Path | None = None) -> dict[str, dict]:
    path = pathlib.Path(path or ROOT / "corpus.jsonl")
    with path.open(encoding="utf-8") as fh:
        return {d["doc_id"]: d for d in (json.loads(l) for l in fh if l.strip())}


def subject_pattern(cfg: dict) -> re.Pattern:
    """Anything that spells the subject out: names, name parts, handles, mail."""
    terms: set[str] = set()
    for n in cfg.get("known_names", []):
        terms.add(n)
        terms.update(p for p in n.replace(".", " ").split() if len(p) > 2)
    terms.update(cfg.get("aliases") or [])
    terms.update(cfg.get("addresses") or [])
    terms = {t for t in terms if len(t) > 2}
    return re.compile(r"(?<!\w)(" + "|".join(re.escape(t) for t in
                                             sorted(terms, key=len, reverse=True)) + r")",
                      re.I)


def _read(path: pathlib.Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def load_key(root: str | pathlib.Path | None = None,
             corpus: dict[str, dict] | None = None,
             subjects: list[str] | None = None) -> Key:
    """Read subjects.json plus the per-subject annotation and negative files."""
    root = pathlib.Path(root or ROOT)
    import sys
    sys.path.insert(0, str(root / "dsarbench"))
    from subjects_def import SUBJECTS  # noqa: E402

    docs = corpus if corpus is not None else load_corpus(root / "corpus.jsonl")
    sids = subjects or list(SUBJECTS)
    pos: list[Entry] = []
    neg: list[Entry] = []

    for sid in sids:
        rx = subject_pattern(SUBJECTS[sid])
        for kind, rows in (("pos", _read(root / f"annotations_{sid}.jsonl")),
                           ("neg", _read(root / f"negatives_{sid}.jsonl"))):
            for r in rows:
                if r.get("subject_id", sid) != sid or r["doc_id"] not in docs:
                    continue
                e = Entry(subject_id=sid, doc_id=r["doc_id"], block_id=r["block_id"],
                          span=(r["span"][0], r["span"][1]), text=r.get("text", ""),
                          tier=(r.get("tier") or "T?").upper(),
                          positive=kind == "pos",
                          rationale=r.get("rationale", ""),
                          gdpr_category=r.get("gdpr_category", ""))
                object.__setattr__(e, "_named", bool(rx.search(e.text)))
                (pos if kind == "pos" else neg).append(e)

    return Key(subjects={s: SUBJECTS[s] for s in sids}, positives=pos,
               negatives=neg, docs=docs)
