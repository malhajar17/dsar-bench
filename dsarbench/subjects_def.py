"""Load subject definitions from subjects.json and build seed patterns.

Each subject is data, not code. The pipeline (scope → sweep → adjudicate →
reconcile) takes a subject_id and reads this file.

OFFSET CONVENTION: spans index block `text`.
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SUBJECTS_PATH = ROOT / "subjects.json"


def _escape(s: str) -> str:
    return re.escape(s)


def build_patterns(cfg: dict) -> dict[str, str]:
    """Seed patterns: names, aliases, addresses, plus any extra_patterns.

    First names that are common (Jonathan, Sean, Andreas) are only added when
    they appear in extra_patterns (e.g. Dear Andreas) or when the known_names
    list includes the bare first name on purpose (S2).
    """
    pats: dict[str, str] = {}
    for n in cfg.get("known_names") or []:
        pats[n] = r"\b" + _escape(n) + r"\b"
    for a in cfg.get("aliases") or []:
        pats[f"alias:{a}"] = r"\b" + _escape(a) + r"\b"
    for addr in cfg.get("addresses") or []:
        pats[addr] = _escape(addr)
    pats.update(cfg.get("extra_patterns") or {})
    return pats


def load_subjects(path: pathlib.Path = SUBJECTS_PATH) -> dict[str, dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for sid, cfg in raw.items():
        cfg = dict(cfg)
        cfg["patterns"] = build_patterns(cfg)
        out[sid] = cfg
    return out


SUBJECTS = load_subjects()


def get(subject_id: str) -> dict:
    if subject_id not in SUBJECTS:
        raise SystemExit(f"unknown subject {subject_id}; have {sorted(SUBJECTS)}")
    return SUBJECTS[subject_id]


def brief(cfg: dict) -> str:
    lines = [
        f"The data subject is {cfg['display']} (subject_id {cfg['subject_id']}).",
        "Known identifiers:",
        f"  - names: {', '.join(cfg.get('known_names') or [])}",
        f"  - aliases/handles: {', '.join(cfg.get('aliases') or []) or '(none)'}",
        f"  - addresses: {', '.join(cfg.get('addresses') or [])}",
    ]
    for r in cfg.get("roles") or []:
        lines.append(f"  - role: {r.get('role')} [{r.get('from')} .. {r.get('to')}]")
        if r.get("basis"):
            lines.append(f"    basis: {r['basis']}")
    if cfg.get("confusable"):
        lines.append("Known confusable people (must NOT be accepted as the subject):")
        for c in cfg["confusable"]:
            lines.append(f"  - {c}")
    return "\n".join(lines)
