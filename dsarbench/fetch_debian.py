"""Fetch debian-project archive months from lists.debian.org.

lists.debian.org exposes no bulk mbox endpoint; the archive is MHonArc HTML,
one page per message. We therefore walk msgNNNNN.html sequentially per month,
rate-limited to <= 1 request/sec with a descriptive User-Agent, and cache every
page on disk so a month is never fetched twice.

Pages are cached verbatim under cache/<list>/<yyyy>/<mm>/msgNNNNN.html.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import requests

BASE = "https://lists.debian.org"
UA = (
    "DSAR-Bench-corpus-builder/0.1 (GDPR Art.15 evaluation corpus research; "
    "public archives only; contact: https://github.com/malhajar17)"
)
MIN_INTERVAL = 1.05  # seconds between requests, robots.txt-friendly
MISS_RUN_END_OF_MONTH = 6  # consecutive 404s before a month is considered finished

REQUEST_LOG = pathlib.Path(__file__).resolve().parents[1] / "cache" / "requests.log"
MAX_REQUESTS = 2000


class Budget:
    """Append-only ledger of every HTTP request, so the 2000-request cap holds.

    A counter file rewritten at exit loses requests whenever two runs overlap
    (last writer wins). One line per request, appended before the request is
    issued, is correct under concurrency and survives a killed process.
    """

    def __init__(self, path: pathlib.Path = REQUEST_LOG):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.n = sum(1 for _ in path.open()) if path.exists() else 0

    def spend(self, url: str = "") -> None:
        self.n += 1
        with self.path.open("a") as fh:
            fh.write(f"{time.time():.0f}\t{url}\n")
        if self.n > MAX_REQUESTS:
            sys.exit(f"ABORT: HTTP request budget of {MAX_REQUESTS} exhausted (n={self.n}).")

    def flush(self) -> None:
        """Kept for call-site compatibility; the ledger is written as we go."""


class Fetcher:
    def __init__(self, budget: Budget):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.budget = budget
        self._last = 0.0

    def get(self, url: str) -> requests.Response:
        wait = MIN_INTERVAL - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self.budget.spend(url)
        r = self.s.get(url, timeout=30)
        self._last = time.monotonic()
        return r


def fetch_numbers(listname: str, month: str, numbers, cache_root: pathlib.Path,
                  fetcher: Fetcher) -> int:
    """Fetch an explicit set of message numbers of one month ('YYYY-MM').

    Preferred over probing: the monthly index already declares exactly which
    message numbers exist, so no request is wasted on 404s and no month can be
    truncated by a miss-run heuristic.
    """
    y, m = month.split("-")
    outdir = cache_root / listname / y / m
    outdir.mkdir(parents=True, exist_ok=True)
    n = 0
    for num in sorted(numbers):
        name = f"msg{num}.html"
        dest = outdir / name
        if dest.exists():
            n += 1
            continue
        url = f"{BASE}/{listname}/{y}/{m}/{name}"
        r = fetcher.get(url)
        if r.status_code != 200:
            print(f"  WARN {month}/{name}: HTTP {r.status_code}", flush=True)
            continue
        dest.write_bytes(r.content)
        (outdir / (name + ".url")).write_text(url)
        n += 1
    return n


def fetch_month(listname: str, year: int, month: int, cache_root: pathlib.Path,
                fetcher: Fetcher, limit: int = 5000) -> int:
    """Fetch all msgNNNNN.html of one month. Returns number of messages cached."""
    outdir = cache_root / listname / f"{year:04d}" / f"{month:02d}"
    outdir.mkdir(parents=True, exist_ok=True)
    n = 0
    misses = 0
    for i in range(limit):
        name = f"msg{i:05d}.html"
        dest = outdir / name
        if dest.exists():
            n += 1
            misses = 0
            continue
        url = f"{BASE}/{listname}/{year:04d}/{month:02d}/{name}"
        r = fetcher.get(url)
        if r.status_code == 404:
            # MHonArc numbering is usually dense but not guaranteed to be: a
            # short run of 404s can sit in the middle of a live month, so only
            # a long run is treated as the end. Stopping too early silently
            # truncates a month and the loss is invisible downstream.
            misses += 1
            if misses >= MISS_RUN_END_OF_MONTH:
                break
            continue
        r.raise_for_status()
        dest.write_bytes(r.content)
        (outdir / (name + ".url")).write_text(url)
        n += 1
        misses = 0
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", default="debian-project")
    ap.add_argument("--months", required=True,
                    help="comma-separated YYYY-MM, e.g. 2024-01,2024-02")
    args = ap.parse_args()

    root = pathlib.Path(__file__).resolve().parents[1]
    budget = Budget()
    f = Fetcher(budget)
    total = 0
    try:
        for tok in args.months.split(","):
            y, m = tok.strip().split("-")
            got = fetch_month(args.list, int(y), int(m), root / "cache", f)
            total += got
            print(f"{args.list} {tok}: {got} messages cached "
                  f"(requests used so far: {budget.n})", flush=True)
    finally:
        budget.flush()
    print(f"TOTAL cached messages: {total}; HTTP requests lifetime: {budget.n}")


if __name__ == "__main__":
    main()
