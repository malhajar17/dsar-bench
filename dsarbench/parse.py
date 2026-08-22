"""Parse cached MHonArc pages into corpus.jsonl / dropped.jsonl.

OFFSET CONVENTION: all `span` offsets used anywhere in this project are Python
character indices into the decoded `text` of a given `block_id`, never into
`body_raw`, never byte offsets.

lists.debian.org publishes no mbox, so each message is reconstructed as an
RFC 5322 document from the MHonArc header list plus the <pre> body and then
handed to the `email` stdlib parser -- header decoding, charset handling and
address parsing are done by the stdlib, not by regexes.
"""

from __future__ import annotations

import argparse
import email
import email.policy
import hashlib
import html
import json
import pathlib
import re
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser

from blocks import segment

# Conservative, explicit spam phrases. Every drop is logged in dropped.jsonl.
SPAM_PHRASES = [
    "viagra",
    "cialis",
    "make money fast",
    "work from home and earn",
    "nigerian prince",
    "lottery winner notification",
    "increase your penis",
    "buy cheap replica",
    "sex dating",
    "casino bonus",
]
MIN_BODY_CHARS = 20
BLOCK_TAGS = {"div", "p", "br", "tr", "li", "blockquote", "h1", "h2", "h3", "table"}


class MHonArcParser(HTMLParser):
    """Extract the header <ul> and the body of an MHonArc message page.

    MHonArc expresses quoting as nested <blockquote> for BOTH text/plain and
    text/html messages: a plain-text reply comes back as alternating <pre> and
    <blockquote><pre> rather than as '>' -prefixed lines. Quote depth is
    therefore tracked across the whole body region, inside <pre> as well as
    outside it, and re-emitted as '>' prefixes so that every message goes
    through one depth-segmentation path in blocks.segment.

    Body text is collected into a single ordered buffer. A plain-text message
    can still carry runs outside <pre> -- MHonArc renders flowed-format lines as
    <tt> -- and those are body text, not markup.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.region: str | None = None
        self.header_items: list[str] = []
        self._li: list[str] = []
        self._in_li = False
        self.body_parts: list[str] = []
        self.meta: dict[str, list[str]] = {}
        self.attachments: list[dict] = []
        self._in_pre = False
        self.saw_pre = False
        self._att_names: list[str] = []
        self._att_tail: list[str] = []
        self.html_body: str = ""
        self._bq = 0  # <blockquote> nesting = quote depth
        self._at_line_start = True
        self._in_att = False  # MHonArc's attachment stanza, which follows the body

    def handle_comment(self, data: str) -> None:
        d = data.strip()
        if d == "X-Head-of-Message":
            self.region = "head"
        elif d == "X-Head-of-Message-End":
            self.region = None
        elif d == "X-Body-of-Message":
            self.region = "body"
        elif d == "X-Body-of-Message-End":
            self.region = None
        elif d.startswith("X-"):
            k, _, v = d.partition(": ")
            self.meta.setdefault(k, []).append(html.unescape(v))

    def handle_starttag(self, tag: str, attrs) -> None:
        a = dict(attrs)
        if self.region == "head" and tag == "li":
            self._in_li = True
            self._li = []
        if self.region == "body":
            if tag == "pre":
                self._in_pre = True
                self.saw_pre = True
                self._newline()
            elif tag == "a" and not self._in_pre:
                # MHonArc renders detached attachments below the body.
                self._att_names.append(a.get("href", ""))
            elif tag == "blockquote":
                self._bq += 1
                self._newline()
            elif not self._in_pre and tag in BLOCK_TAGS:
                self._newline()

    def handle_endtag(self, tag: str) -> None:
        if tag == "li" and self._in_li:
            self._in_li = False
            self.header_items.append("".join(self._li))
        if tag == "pre":
            self._in_pre = False
            self._newline()
        elif self.region == "body":
            if tag == "blockquote":
                self._bq = max(0, self._bq - 1)
                self._newline()
            elif not self._in_pre and tag in BLOCK_TAGS:
                self._newline()

    def _newline(self) -> None:
        if self.region != "body":
            return
        self._sink().append("\n")
        self._at_line_start = True

    def _sink(self) -> list[str]:
        return self._att_tail if self._in_att else self.body_parts

    def _emit(self, data: str) -> None:
        """Append body text, prefixing each line with the current quote depth."""
        prefix = "> " * self._bq
        out = self._sink()
        for i, line in enumerate(data.split("\n")):
            if i:
                out.append("\n")
                self._at_line_start = True
            if not line:
                continue
            if self._at_line_start and prefix:
                out.append(prefix)
            out.append(line)
            self._at_line_start = False

    def handle_data(self, data: str) -> None:
        if self._in_li:
            self._li.append(data)
        elif self.region == "body":
            # Everything from the attachment stanza on is metadata, not body.
            if not self._in_pre and "Attachment:" in data:
                head, sep, tail = data.partition("Attachment:")
                self._emit(head)
                self._in_att = True
                self._att_tail.append(sep + tail)
                return
            self._emit(data)

    def finish(self) -> None:
        """Turn the MHonArc attachment stanza that follows the body into metadata."""
        tail = "".join(self._att_tail)
        descs = [d.split("\n")[0].strip() for d in tail.split("Description:")[1:]]
        for i, filename in enumerate(_att_filenames(tail)):
            self.attachments.append({
                "filename": filename,
                "stored_href": self._att_names[i] if i < len(self._att_names) else None,
                "content_type_hint": descs[i] if i < len(descs) else None,
            })

    @property
    def body(self) -> str:
        return "".join(self.body_parts)


def _att_filenames(tail: str) -> list[str]:
    """Filenames appear as the anchor text right after each 'Attachment:'."""
    out = []
    for chunk in tail.split("Attachment:")[1:]:
        name = chunk.strip().split("\n")[0].strip()
        if name:
            out.append(name)
    return out


# MHonArc injects a magnifier glyph link ("[U+1F50E]") before every message-id
# it turns into a msgid-search link. It is presentation, not header content.
GLYPH_RE = re.compile(r"\[\s*\U0001F50E\s*\]\s*|\U0001F50E")


def _headers_from_items(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for it in items:
        k, sep, v = it.partition(":")
        if not sep:
            continue
        out[k.strip().lower()] = GLYPH_RE.sub("", v).replace("\xa0", " ").strip()
    return out


def _mk_rfc822(hdrs: dict[str, str], meta: dict[str, list[str]], body: str) -> str:
    lines = []
    order = ["from", "to", "cc", "subject", "date", "message-id", "in-reply-to"]
    canon = {"message-id": "Message-ID", "in-reply-to": "In-Reply-To"}
    for k in order:
        if k in hdrs and hdrs[k]:
            v = hdrs[k].replace("\n", " ")
            if k in ("message-id", "in-reply-to") and not v.startswith("<"):
                v = f"<{v}>"
            lines.append(f"{canon.get(k, k.title())}: {v}")
    refs = hdrs.get("references") or " ".join(meta.get("X-Reference", []))
    if refs:
        toks = re.findall(r"<[^<>@\s]+@[^<>\s]+>", refs) or [
            f"<{r}>" for r in meta.get("X-Reference", [])
        ]
        if toks:
            lines.append("References: " + " ".join(toks))
    return "\r\n".join(lines) + "\r\n\r\n" + body


def parse_page(path: pathlib.Path, listname: str) -> dict:
    raw_bytes = path.read_bytes()
    decode_error = False
    try:
        raw = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        decode_error = True
        raw = raw_bytes.decode("latin-1")

    p = MHonArcParser()
    p.feed(raw)
    p.finish()
    hdrs = _headers_from_items(p.header_items)
    msg = email.message_from_string(
        _mk_rfc822(hdrs, p.meta, p.body), policy=email.policy.default
    )

    html_source = not p.saw_pre and bool(p.body.strip())
    body_raw = p.body

    def addrs(field: str) -> list[dict]:
        vals = msg.get_all(field, [])
        return [{"name": n, "addr": a} for n, a in getaddresses(vals) if a or n]

    from_list = addrs("from")
    mid = (msg.get("Message-ID") or "").strip().strip("<>")
    irt = (msg.get("In-Reply-To") or "").strip().strip("<>") or None
    refs = [r.strip("<>") for r in re.findall(r"<[^>]+>", msg.get("References", ""))]

    date_iso = None
    try:
        date_iso = parsedate_to_datetime(msg.get("Date", "")).isoformat()
    except Exception:
        date_iso = None

    rel = path.relative_to(path.parents[3])
    year, month = path.parents[1].name, path.parent.name
    url_file = path.with_suffix(".html.url")
    source_url = (
        url_file.read_text().strip() if url_file.exists()
        else f"https://lists.debian.org/{listname}/{year}/{month}/{path.name}"
    )
    short = hashlib.sha1(mid.encode()).hexdigest()[:8] if mid else path.stem
    doc_id = f"dp-{year}-{month}-{path.stem[3:]}-{short}"

    return {
        "doc_id": doc_id,
        "list": listname,
        "source": "lists.debian.org",
        "source_url": source_url,
        "cache_path": str(rel),
        "date": date_iso,
        "date_header": msg.get("Date"),
        "from_name": from_list[0]["name"] if from_list else "",
        "from_addr": from_list[0]["addr"] if from_list else "",
        "to": addrs("to"),
        "cc": addrs("cc"),
        "subject": msg.get("Subject", ""),
        "message_id": mid,
        "in_reply_to": irt,
        "references": refs,
        "thread_id": None,
        "html_source": html_source,
        "content_type": (p.meta.get("X-Content-Type") or [None])[0],
        "decode_error": decode_error,
        "attachments": p.attachments,
        "body_raw": body_raw,
        "body_blocks": segment(body_raw),
    }


def drop_reason(doc: dict) -> str | None:
    if not doc["message_id"]:
        return "no_message_id"
    body = doc["body_raw"].strip()
    if len(body) < MIN_BODY_CHARS:
        return "body_under_20_chars"
    low = body.lower() + " " + (doc["subject"] or "").lower()
    for phrase in SPAM_PHRASES:
        if phrase in low:
            return f"spam_phrase:{phrase}"
    return None


def assign_threads(docs: list[dict]) -> None:
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for d in docs:
        find(d["message_id"])
        for r in ([d["in_reply_to"]] if d["in_reply_to"] else []) + d["references"]:
            union(r, d["message_id"])
    for d in docs:
        d["thread_id"] = "t-" + hashlib.sha1(find(d["message_id"]).encode()).hexdigest()[:10]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", default="debian-project")
    ap.add_argument("--months", default=None, help="comma-separated YYYY-MM; default: all cached")
    ap.add_argument("--out", default="corpus.jsonl")
    ap.add_argument("--dropped", default="dropped.jsonl")
    args = ap.parse_args()

    root = pathlib.Path(__file__).resolve().parents[1]
    cache = root / "cache" / args.list
    months = None
    if args.months:
        months = {tuple(t.strip().split("-")) for t in args.months.split(",")}

    pages = []
    for d in sorted(cache.glob("*/*")):
        if months and (d.parent.name, d.name) not in months:
            continue
        pages.extend(sorted(d.glob("msg*.html")))

    kept: list[dict] = []
    dropped: list[dict] = []
    seen: dict[str, str] = {}
    for page in pages:
        doc = parse_page(page, args.list)
        reason = drop_reason(doc)
        if reason:
            dropped.append({"doc_id": doc["doc_id"], "source_url": doc["source_url"],
                            "message_id": doc["message_id"], "reason": reason,
                            "subject": doc["subject"]})
            continue
        if doc["message_id"] in seen:
            dropped.append({"doc_id": doc["doc_id"], "source_url": doc["source_url"],
                            "message_id": doc["message_id"],
                            "reason": f"duplicate_of:{seen[doc['message_id']]}",
                            "subject": doc["subject"]})
            continue
        seen[doc["message_id"]] = doc["doc_id"]
        kept.append(doc)

    assign_threads(kept)
    with (root / args.out).open("w", encoding="utf-8") as fh:
        for d in kept:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    with (root / args.dropped).open("w", encoding="utf-8") as fh:
        for d in dropped:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")

    print(f"parsed {len(pages)} pages -> kept {len(kept)}, dropped {len(dropped)}")


if __name__ == "__main__":
    main()
