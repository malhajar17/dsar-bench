# Provenance

## Source

| Field | Value |
|---|---|
| Archive | `debian-project` public mailing list |
| Entry point | `https://lists.debian.org/debian-project/<YYYY>/<MM>/msgNNNNN.html` |
| Access | Public web archive, no authentication, no login, no private list |
| Fetch date | 2026-08-14 (first month: 2024-01) |
| Fetch method | Sequential `msgNNNNN.html` GET, one request per message |
| Rate limit | >= 1.05 s between requests, single connection |
| User-Agent | `DSAR-Bench-corpus-builder/0.1 (GDPR Art.15 evaluation corpus research; public archives only; contact: https://github.com/malhajar17)` |
| robots.txt | Checked. Disallows `/bounces`, `/cgi-bin`, `/msgid-search` only; the archive paths used here are permitted. |
| Request budget | Hard cap of 2000 lifetime HTTP requests enforced in `dsarbench/fetch_debian.py`; counter persisted in `cache/request_count.json`. |

`lists.debian.org` publishes **no bulk mbox or git endpoint** for this list, so the
"prefer bulk endpoints" rule cannot be satisfied for the primary source. Each message
page is fetched once and cached on disk; a re-run of the parser costs zero requests.

## Fidelity class (important for offset claims)

MHonArc serves **rendered** bodies, not wire format. HTML entities are already
decoded, some whitespace may have been reflowed by the archiver, and MIME structure
has been flattened by the archive before we ever see it. Two fidelity classes exist
in this corpus and every document records which one it belongs to:

| Class | `html_source` | How the body is obtained | Fidelity |
|---|---|---|---|
| A: plain-text subset | `false` | Verbatim text of the MHonArc `<pre>` element | High. Quote markers are the author's own `>` characters. |
| B: html-only subset | `true` | HTML converted to text: block-level tags become newlines, nested `<blockquote>` is re-emitted as `>` prefixes so quote depth survives | Lower. Line breaks and quote markers are *reconstructed by us*, not authored. |

**Prefer class A spans for any headline claim that depends on exact offsets.**
Class B offsets are internally consistent (the validator checks that every span
slices to its stored text) but they index a body we reconstructed, not one the
author typed.

In the 2024-01 pilot, 7 of 33 messages (21%) were class B. Three of those seven
carried `<blockquote>` quoting that an earlier version of the converter flattened
to depth 0; `dsarbench/validate.py` now fails loudly if any class B document whose
source contains `<blockquote>` produces no block at depth > 0.

## Sampling design and its bias (declared)

The corpus is **not** a uniform sample of the list, and is not fully contiguous.
It is built as:

1. **A 12-month contiguous spine** — preserves realistic message density, thread
   structure and the long-range references that tier T5 depends on.
2. **4-6 targeted dispute windows** — additional months selected *because* their
   thread indexes score high on dispute-genre signals (forwarded material,
   resignation, appellate/Community Team action, disciplinary vocabulary).
   February 2026 is included as a confirmed target: it contains both a forwarded
   disciplinary warning (tier T4) and a deliberately de-identified quoted passage
   (tier T6), verified by hand.

Month selection was done from thread indexes only (one request per month) using the
keyword scoring in `dsarbench/probe_index.py`, which records the scores to
`data/index_scores.json`. That file lists 513 message subjects, so it stays local
under the same rule as the corpus; the chosen windows are listed below.

**This biases the corpus toward conflict.** The bias is deliberate and it is
defensible only because it is stated: real DSARs disproportionately arise from
disputes, so a corpus sampled uniformly would under-represent the genre the system
is built for. It does mean this corpus must not be used to estimate the base rate of
disputes on a mailing list.

Secondary source: GNOME `foundation-list` (`https://mail.gnome.org/archives/foundation-list/`),
fetched via its bulk monthly mbox (one request per month). It is included as a
*second organization with different list conventions and governance vocabulary*, so
that results cannot be explained by overfitting to one community's idioms.

## Excluded by policy

- `debian-private` and any other subscriber-only or moderated-private list: never fetched.
- Anything behind authentication: never fetched.
- Social media, forums, leaked corpora: never fetched.

## Licence / terms

Debian list archives are published by SPI and others under the terms stated at
<https://www.debian.org/license>. Individual messages remain the copyright of their
authors, who published them to a public archive knowing it is world-readable and
mirrored. This corpus is used for research evaluation of a data-subject-access-request
system, quoted in the minimum extent needed, and is redistributed only in pseudonymized
form.

## Consent posture per subject

To be completed at Layer 2, one row per data subject, recording: whether the person is a
public project office-holder at the time of the messages, whether the material is
adverse, and what is redacted in the published (pseudonymized) artifacts.

| subject_id | role at the time | adverse material present | publication posture |
|---|---|---|---|
| _pending Layer 2_ | | | |

## Publication rules enforced in this repo

- `mapping.json` (real name -> `PERSON_A`) is gitignored and never published.
- Only the pseudonymized corpus and pseudonymized annotations are publishable.
- No adverse allegation about an identifiable living person appears in any demo artifact.
