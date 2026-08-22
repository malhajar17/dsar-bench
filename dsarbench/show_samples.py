"""Print messages with their block segmentation made visible.

OFFSET CONVENTION: character indices shown per block are Python string indices
into that block's decoded `text`.
"""

from __future__ import annotations

import argparse
import json
import pathlib


def render(doc: dict, maxchars: int) -> str:
    out = [
        "=" * 100,
        f"{doc['doc_id']}   thread={doc['thread_id']}",
        f"url     : {doc['source_url']}",
        f"date    : {doc['date']}",
        f"from    : {doc['from_name']} <{doc['from_addr']}>",
        f"subject : {doc['subject']}",
        f"msgid   : {doc['message_id']}",
        f"in-reply-to: {doc['in_reply_to']}  refs={len(doc['references'])}",
        f"blocks  : {len(doc['body_blocks'])}",
        "-" * 100,
    ]
    for b in doc["body_blocks"]:
        text = b["text"]
        shown = text if len(text) <= maxchars else text[:maxchars] + f"...[+{len(text)-maxchars} chars]"
        out.append(f"[block {b['block_id']:>2} | {b['type']:<10} | depth {b['depth']} | {len(text)} chars]")
        out.extend("    " + ln for ln in shown.split("\n"))
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="corpus.jsonl")
    ap.add_argument("-n", type=int, default=20)
    ap.add_argument("--maxchars", type=int, default=600)
    ap.add_argument("--doc", default=None)
    args = ap.parse_args()

    root = pathlib.Path(__file__).resolve().parents[1]
    docs = [json.loads(l) for l in (root / args.corpus).open(encoding="utf-8")]
    if args.doc:
        docs = [d for d in docs if d["doc_id"] == args.doc]
    for d in docs[: args.n]:
        print(render(d, args.maxchars))


if __name__ == "__main__":
    main()
