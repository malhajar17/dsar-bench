"""Reference submissions: what plain text search gets you.

Two floors, both with no model and no memory. They exist so that a score has
something to mean: a system that does not beat these is not reading anything.

  cautious  searches full names, handles and mail addresses only. What a
            careful implementer writes. High precision, poor recall, and it
            never meets a first-name collision because it never searches one.

  greedy    also searches bare first and last names. What a rushed implementer
            writes, and defensible on its face -- people sign mail with a
            first name, so full-name-only misses them. It buys recall and pays
            for it in precision and decoys, which is the trade the benchmark
            exists to measure.

Emits a submission file, so the baselines go through exactly the same scorer as
any other system:

    python3 baselines/name_search.py --mode greedy --out runs/name_search_greedy.jsonl
    python3 dsarbench/score.py runs/name_search_greedy.jsonl

Practice set (Sallow cards, not the official subjects):

    python3 baselines/name_search.py --mode cautious \
        --corpus dist/sallow/corpus.jsonl \
        --subjects-file dist/sallow/subjects.json \
        --out runs/sallow_name_search_cautious.jsonl
    python3 dsarbench/score.py runs/sallow_name_search_cautious.jsonl --dev dist/sallow
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dsarbench"))

from subjects_def import SUBJECTS  # noqa: E402

SENT_END = re.compile(r"(?<=[.!?])\s+|\n\s*\n")


def terms_for(cfg: dict, mode: str) -> list[str]:
    terms: set[str] = set(cfg.get("known_names") or [])
    terms.update(cfg.get("aliases") or [])
    terms.update(cfg.get("addresses") or [])
    if mode == "greedy":
        for n in cfg.get("known_names") or []:
            terms.update(p for p in n.replace(".", " ").split() if len(p) > 2)
    return sorted({t for t in terms if len(t) > 2}, key=len, reverse=True)


def sentence_around(text: str, start: int, end: int) -> tuple[int, int]:
    """Widen a hit to its sentence, which is roughly the unit the key uses."""
    lo = 0
    for m in SENT_END.finditer(text, 0, start):
        lo = m.end()
    m = SENT_END.search(text, end)
    return lo, m.start() if m else len(text)


def tag(doc: dict, terms: list[str]) -> list[tuple[int, int, int]]:
    rx = re.compile(r"(?<!\w)(" + "|".join(re.escape(t) for t in terms) + r")", re.I)
    out: list[tuple[int, int, int]] = []
    for b in doc["body_blocks"]:
        spans: list[list[int]] = []
        for m in rx.finditer(b["text"]):
            s, e = sentence_around(b["text"], m.start(), m.end())
            if spans and s <= spans[-1][1]:
                spans[-1][1] = max(spans[-1][1], e)
            else:
                spans.append([s, e])
        out += [(b["block_id"], s, e) for s, e in spans]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=("cautious", "greedy"), default="cautious")
    ap.add_argument("--corpus", default=str(ROOT / "corpus.jsonl"))
    ap.add_argument("--subjects", default="")
    ap.add_argument("--subjects-file", default="",
                    help="JSON subject cards (e.g. dist/sallow/subjects.json)")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    with open(args.corpus, encoding="utf-8") as fh:
        docs = [json.loads(l) for l in fh if l.strip()]
    if args.subjects_file:
        cards = json.loads(pathlib.Path(args.subjects_file).read_text())
    else:
        cards = SUBJECTS
    sids = [s.strip() for s in args.subjects.split(",") if s.strip()] or list(cards)

    out_path = pathlib.Path(args.out or ROOT / "runs" / f"name_search_{args.mode}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for sid in sids:
            terms = terms_for(cards[sid], args.mode)
            for doc in docs:
                for block_id, s, e in tag(doc, terms):
                    fh.write(json.dumps({
                        "subject_id": sid, "doc_id": doc["doc_id"],
                        "block_id": block_id, "span": [s, e],
                        "text": doc["body_blocks"][block_id]["text"][s:e],
                    }, ensure_ascii=False) + "\n")
                    n += 1

    print(f"{args.mode}: {n} passages -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
