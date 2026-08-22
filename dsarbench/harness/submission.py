"""Reading a submission and anchoring each quoted passage to the corpus.

A submitting system quotes text; it does not count characters. So the harness
accepts verbatim text and finds it, tolerating whitespace differences, which
are unavoidable once a passage has been through a model. Offsets may be given
instead and are then trusted as-is.

An entry that cannot be located in the named document is not silently dropped:
it is kept as unlocatable and counts against precision. Returning text that is
not in the corpus is a hallucination, and hiding it would flatter the system.
"""

from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass

WS = re.compile(r"\s+")


@dataclass
class Prediction:
    subject_id: str
    doc_id: str
    text: str
    block_id: int | None = None
    span: tuple[int, int] | None = None
    unlocatable_reason: str = ""

    @property
    def located(self) -> bool:
        return self.block_id is not None and self.span is not None


def _normalise(text: str) -> tuple[str, list[int]]:
    """Collapse whitespace, keeping a map back to original offsets."""
    out: list[str] = []
    idx: list[int] = []
    prev_space = True  # strip leading space
    for i, ch in enumerate(text):
        if ch.isspace():
            if prev_space:
                continue
            out.append(" ")
            idx.append(i)
            prev_space = True
        else:
            out.append(ch)
            idx.append(i)
            prev_space = False
    return "".join(out), idx


def anchor(pred: Prediction, doc: dict) -> Prediction:
    """Locate pred.text inside doc, filling in block_id and span."""
    if pred.span is not None and pred.block_id is not None:
        return pred

    needle, _ = _normalise(pred.text)
    needle = needle.strip().lower()
    if not needle:
        pred.unlocatable_reason = "empty text"
        return pred

    best: tuple[int, tuple[int, int]] | None = None
    for b in doc["body_blocks"]:
        hay, idx = _normalise(b["text"])
        at = hay.lower().find(needle)
        if at < 0:
            continue
        start = idx[at]
        end = idx[min(at + len(needle) - 1, len(idx) - 1)] + 1
        # prefer the block where the match is a larger share of the block
        if best is None or (end - start) / max(1, len(b["text"])) > \
                (best[1][1] - best[1][0]) / max(1, len(doc["body_blocks"][best[0]]["text"])):
            best = (b["block_id"], (start, end))

    if best is None:
        pred.unlocatable_reason = "text not found in document"
        return pred
    pred.block_id, pred.span = best
    return pred


def read_submission(path: str | pathlib.Path, docs: dict[str, dict],
                    subjects: set[str] | None = None) -> tuple[list[Prediction], list[str]]:
    """Parse a JSONL submission. Returns predictions and a list of warnings.

    Each line: {"subject_id": "S5", "doc_id": "...", "text": "verbatim quote"}
    Optionally "block_id" and "span": [start, end] to bypass text anchoring.
    """
    preds: list[Prediction] = []
    warnings: list[str] = []
    seen: set[tuple] = set()

    with pathlib.Path(path).open(encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as e:
                warnings.append(f"line {n}: not valid JSON ({e.msg})")
                continue
            sid, did = r.get("subject_id"), r.get("doc_id")
            if not sid or not did:
                warnings.append(f"line {n}: missing subject_id or doc_id")
                continue
            if subjects and sid not in subjects:
                warnings.append(f"line {n}: unknown subject {sid}")
                continue
            if did not in docs:
                warnings.append(f"line {n}: unknown doc_id {did}")
                continue

            span = r.get("span")
            p = Prediction(subject_id=sid, doc_id=did, text=r.get("text", ""),
                           block_id=r.get("block_id"),
                           span=(span[0], span[1]) if span else None)
            p = anchor(p, docs[did])

            dedup = (sid, did, p.block_id, p.span, p.text[:80] if not p.located else "")
            if dedup in seen:
                warnings.append(f"line {n}: duplicate of an earlier prediction, dropped")
                continue
            seen.add(dedup)
            preds.append(p)

    return preds, warnings
