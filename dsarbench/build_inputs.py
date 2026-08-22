"""Emit the publishable task inputs, and verify a rebuilt corpus against ours.

A system being scored needs two things: the archive, and the list of people to
find. Neither ships as data. The archive does not need to -- `doc_id` is
`dp-{year}-{month}-{msgnum}-{sha1(message_id)[:8]}`, derived entirely from the
public archive, so an independent rebuild lands on identical ids and submissions
line up without us distributing anyone's mail. What ships instead is a manifest
of hashes that proves a rebuild matches.

`subjects.json` does need to ship, and is split here rather than published whole:

  task-facing   names, aliases, addresses, roles with dates, confusable people.
                Identity facts already public in the archive, and required to
                attempt the task at all.

  internal      `adverse` and `one_liner` -- our editorial read of each person's
                position in the disputes. Characterisation rather than record,
                no bearing on the task, so it stays out of dist/.

Usage:
    build_inputs.py                     write dist/
    build_inputs.py --verify            check local corpus against dist/ manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

# Everything a system needs to attempt the task, and nothing that is our opinion.
PUBLIC_SUBJECT_FIELDS = (
    "subject_id",
    "display",
    "known_names",
    "aliases",
    "addresses",
    "roles",
    "extra_patterns",
    "confusable",
)
INTERNAL_SUBJECT_FIELDS = ("adverse", "one_liner")

# Fields whose value defines the task. Hashed per document so a rebuild can be
# checked without us shipping any message text.
FINGERPRINT_FIELDS = ("doc_id", "message_id", "date", "subject", "from_addr", "thread_id")


def doc_fingerprint(doc: dict) -> str:
    h = hashlib.sha256()
    for field in FINGERPRINT_FIELDS:
        h.update(f"{field}={doc.get(field) or ''}\n".encode())
    for blk in doc.get("body_blocks", []):
        h.update(f"{blk['block_id']}|{blk['type']}|{blk['depth']}|".encode())
        h.update(hashlib.sha256((blk.get("text") or "").encode()).hexdigest().encode())
        h.update(b"\n")
    return h.hexdigest()[:16]


def load_corpus() -> list[dict]:
    path = ROOT / "corpus.jsonl"
    if not path.exists():
        raise SystemExit(f"{path.name} not found -- fetch and parse the archive first")
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def build() -> None:
    subjects = json.load(open(ROOT / "subjects.json"))
    corpus = load_corpus()
    DIST.mkdir(exist_ok=True)

    public = {}
    for sid, cfg in subjects.items():
        public[sid] = {k: cfg[k] for k in PUBLIC_SUBJECT_FIELDS if k in cfg}
    (DIST / "subjects.json").write_text(json.dumps(public, indent=1, sort_keys=True) + "\n")

    dates = sorted(d["date"] for d in corpus if d.get("date"))
    manifest = {
        "list": "debian-project",
        "source": "lists.debian.org",
        "messages": len(corpus),
        "threads": len({d.get("thread_id") for d in corpus}),
        "date_range": [dates[0][:10], dates[-1][:10]] if dates else None,
        "blocks": sum(len(d.get("body_blocks", [])) for d in corpus),
        "fingerprint_fields": list(FINGERPRINT_FIELDS),
        "documents": {d["doc_id"]: doc_fingerprint(d) for d in sorted(corpus, key=lambda x: x["doc_id"])},
    }
    (DIST / "corpus_manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")

    withheld = [f for f in INTERNAL_SUBJECT_FIELDS if any(f in c for c in subjects.values())]
    print(f"dist/subjects.json        {len(public)} subjects, fields: {', '.join(PUBLIC_SUBJECT_FIELDS)}")
    print(f"                          withheld: {', '.join(withheld) or 'none'}")
    print(f"dist/corpus_manifest.json {manifest['messages']} documents, {manifest['blocks']} blocks, "
          f"{manifest['date_range'][0]} to {manifest['date_range'][1]}")


def verify() -> None:
    manifest_path = DIST / "corpus_manifest.json"
    if not manifest_path.exists():
        raise SystemExit("no dist/corpus_manifest.json -- run without --verify first")
    manifest = json.load(open(manifest_path))
    expected: dict[str, str] = manifest["documents"]
    actual = {d["doc_id"]: doc_fingerprint(d) for d in load_corpus()}

    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    differing = sorted(k for k in set(expected) & set(actual) if expected[k] != actual[k])

    print(f"expected {len(expected)} documents, found {len(actual)}")
    print(f"  identical  {len(set(expected) & set(actual)) - len(differing)}")
    print(f"  differing  {len(differing)}")
    print(f"  missing    {len(missing)}")
    print(f"  unexpected {len(extra)}")

    for label, ids in (("missing", missing), ("unexpected", extra), ("differing", differing)):
        if ids:
            print(f"\nfirst {label}:")
            for doc_id in ids[:10]:
                print(f"  {doc_id}")
            if len(ids) > 10:
                print(f"  ... and {len(ids) - 10} more")

    if missing or extra or differing:
        raise SystemExit("\nThis corpus does not match the manifest. Submissions built against it "
                         "will cite doc_ids the key cannot resolve.")
    print("\nCorpus matches the manifest. Submissions against it will score correctly.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true",
                    help="check the local corpus against dist/corpus_manifest.json")
    args = ap.parse_args()
    verify() if args.verify else build()


if __name__ == "__main__":
    main()
