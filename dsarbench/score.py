"""Score a submission against the DSAR-Bench answer key.

    python3 dsarbench/score.py runs/my_agent.jsonl
    python3 dsarbench/score.py runs/my_agent.jsonl --json out.json --subjects S5,S2

A submission is JSONL, one returned passage per line:

    {"subject_id": "S5", "doc_id": "dp-2025-07-00042-1a2b", "text": "verbatim quote"}

Deterministic and offline: no model is called, nothing is fetched.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from harness.corpus import load_corpus, load_key  # noqa: E402
from harness.metrics import score  # noqa: E402
from harness.report import render  # noqa: E402
from harness.submission import read_submission  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("submission", help="JSONL file of returned passages")
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--root", default=None, help="directory holding the key")
    ap.add_argument("--subjects", default="", help="comma list; default all")
    ap.add_argument("--json", dest="json_out", default="", help="also write JSON here")
    ap.add_argument("--examples", type=int, default=5,
                    help="how many failures to print per category (0 for none)")
    args = ap.parse_args(argv)

    docs = load_corpus(args.corpus)
    sids = [s.strip() for s in args.subjects.split(",") if s.strip()] or None
    key = load_key(args.root, corpus=docs, subjects=sids)

    preds, warnings = read_submission(args.submission, docs, set(key.subjects))
    card = score(preds, key, warnings)

    print(render(card, key, examples=args.examples))

    if args.json_out:
        pathlib.Path(args.json_out).write_text(
            json.dumps(card.as_dict(), indent=2), encoding="utf-8")
        print(f"machine-readable scorecard -> {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
