"""Body segmentation into typed blocks.

OFFSET CONVENTION (applies to every annotation tool in this repo):
    All `span` offsets are Python character indices into the decoded `text` of
    the referenced `block_id`. They are never indices into `body_raw`, and they
    are never byte offsets.

A block's `text` is the quote-marker-stripped content: for a block at depth 2,
the leading "> > " of each line has been removed. `raw_text` keeps the original
lines including markers, for provenance only. Nothing else is normalised: no
whitespace collapsing, no typo fixing, no de-duplication of quoted material.
"""

from __future__ import annotations

import re
from typing import Iterator

QUOTE_RE = re.compile(r"^((?:\s{0,3}>)+)\s?")

FORWARD_MARKERS = (
    "-----Original Message-----",
    "---------- Forwarded message",
    "-------- Forwarded Message",
    "Begin forwarded message:",
    "----- Forwarded message from",
)
PGP_STARTS = (
    "-----BEGIN PGP SIGNED MESSAGE-----",
    "-----BEGIN PGP SIGNATURE-----",
    "-----BEGIN PGP MESSAGE-----",
    "-----BEGIN PGP PUBLIC KEY BLOCK-----",
)
PGP_ENDS = (
    "-----END PGP SIGNATURE-----",
    "-----END PGP MESSAGE-----",
    "-----END PGP PUBLIC KEY BLOCK-----",
)
SIG_SEPS = ("-- ", "--", "___", "regards,")


def _depth(line: str) -> tuple[int, str]:
    """Return (quote depth, line with that many quote markers removed)."""
    d = 0
    cur = line
    while True:
        m = QUOTE_RE.match(cur)
        if not m:
            break
        d += m.group(1).count(">")
        cur = cur[m.end():]
    return d, cur


def _rejoin_soft_wraps(body: str) -> str:
    """Give a wrapped continuation line back the quote prefix it lost.

    Some mail clients hard-wrap a quoted line and put the leftover words on the
    next line WITHOUT repeating the '>' markers, so the archive contains:

        > > ...the team that develops it, I am
        curious
        > > to know what would cause you...

    Read literally, 'curious' is unquoted top-level text, and everything
    downstream then treats one sentence as three blocks -- with the orphan typed
    as the sender's own writing at depth 0. That misattributes quoted words to
    whoever forwarded them, which is the one thing this corpus must not do.

    The repair is deliberately narrow. The decisive signal is that the previous
    line was cut MID-SENTENCE: a quoted line that ends with a trailing space and
    no sentence-ending punctuation is unfinished, so an unquoted short fragment
    on the next line is its tail rather than a new top-level remark. Requiring
    the following line to be at the same depth was too strict -- it missed the
    orphan at the end of a quoted run, where the depth drops immediately after.
    """
    lines = body.split("\n")
    out: list[str] = []
    for i, line in enumerate(lines):
        d, _ = _depth(line)
        prev = lines[i - 1] if i else ""
        pd, pstripped = _depth(prev)
        # A trailing space is not reliable -- some clients trim it. What holds in
        # every observed case is that the quoted line stops without terminal
        # punctuation and the fragment below it starts lowercase, i.e. mid
        # sentence. A genuine short reply ("Yes.", "Agreed.") starts capitalised,
        # which is what keeps this from swallowing real replies.
        _, tail_text = _depth(line)
        cut_mid_sentence = (
            pstripped.strip()
            and pstripped.rstrip()[-1] not in ".!?:;\"'"
            and tail_text.strip()[:1].islower()
        )
        # The tail may come back unquoted (depth 0) or under-quoted -- one '>'
        # where the line above had three. Both are the same wrap damage, so the
        # test is "shallower than the line it continues", not "unquoted".
        orphan = (
            d < pd
            and line.strip()
            and len(line.strip()) <= 40
            and pd > 0
            and cut_mid_sentence
        )
        if orphan and out:
            # Append the orphan's CONTENT. Using the raw line would paste its own
            # '>' markers into the middle of the sentence as literal text.
            _, tail = _depth(line)
            out[-1] = out[-1].rstrip() + " " + tail.strip()
            continue
        out.append(line)
    return "\n".join(out)


def _depth_segments(body: str) -> Iterator[tuple[int, list[str], list[str]]]:
    """Group consecutive lines of equal quote depth."""
    cur_depth: int | None = None
    raw: list[str] = []
    stripped: list[str] = []
    for line in body.split("\n"):
        d, s = _depth(line)
        if line.strip() == "" and cur_depth is not None:
            # A blank line belongs to the block it interrupts, not a new one.
            raw.append(line)
            stripped.append(s)
            continue
        if d != cur_depth:
            if cur_depth is not None:
                yield cur_depth, raw, stripped
            cur_depth, raw, stripped = d, [], []
        raw.append(line)
        stripped.append(s)
    if cur_depth is not None:
        yield cur_depth, raw, stripped


def _classify_segment(depth: int, lines: list[str]) -> list[tuple[str, list[int]]]:
    """Split one depth-segment into (type, line indices) runs.

    Recognised types inside a segment: forwarded, pgp, signature, and the
    residual original/quoted body.
    """
    runs: list[tuple[str, list[int]]] = []
    base = "original" if depth == 0 else "quoted"
    cur_type = base
    cur: list[int] = []
    in_pgp = False
    in_sig = False

    def flush() -> None:
        nonlocal cur, cur_type
        if cur:
            runs.append((cur_type, cur))
        cur = []

    for i, ln in enumerate(lines):
        t = ln.strip()
        if in_pgp:
            cur.append(i)
            if any(t.startswith(e) for e in PGP_ENDS):
                in_pgp = False
                flush()
                cur_type = base if not in_sig else "signature"
            continue
        if any(t.startswith(p) for p in PGP_STARTS):
            flush()
            cur_type = "pgp"
            in_pgp = True
            cur.append(i)
            continue
        if any(t.startswith(f) for f in FORWARD_MARKERS):
            flush()
            cur_type = "forwarded"
            cur.append(i)
            continue
        if not in_sig and ln.rstrip("\r") in ("-- ", "--") and i > 0:
            flush()
            cur_type = "signature"
            in_sig = True
            cur.append(i)
            continue
        cur.append(i)
    flush()
    return runs


def segment(body: str) -> list[dict]:
    """Return the ordered list of typed blocks for a decoded message body."""
    blocks: list[dict] = []
    bid = 0
    body = _rejoin_soft_wraps(body)
    for depth, raw_lines, stripped_lines in _depth_segments(body):
        for btype, idxs in _classify_segment(depth, stripped_lines):
            text = "\n".join(stripped_lines[i] for i in idxs)
            raw_text = "\n".join(raw_lines[i] for i in idxs)
            if text.strip() == "" and btype in ("original", "quoted"):
                continue
            blocks.append({
                "block_id": bid,
                "type": btype,
                "depth": depth,
                "text": text,
                "raw_text": raw_text,
            })
            bid += 1
    return blocks
