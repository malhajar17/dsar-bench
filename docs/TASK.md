# DSAR-Bench: the task

A person asks for a copy of their personal data under GDPR Article 15. The
archive is a public mailing list. Return every passage in it that is their
personal data, and nothing that is not.

The archive is given in full. That is not an invitation to read it in full.
An agent that opens every email can buy recall. The number this benchmark
exists to produce is the one you would trust at two million emails: did it
find the unnamed passages **without** becoming a full-archive scan.

## What a system is given

- `corpus.jsonl` — 615 emails, parsed into typed blocks. Each email carries its
  headers (`from_name`, `from_addr`, `date`, `subject`, `thread_id`,
  `in_reply_to`, `references`) and `body_blocks`, each block having a
  `block_id`, a `type` (`original`, `quoted`, `signature`, `pgp`, `forwarded`),
  a quote `depth`, and its `text`.
- `subjects.json` — for each data subject: display name, known names, aliases,
  mail addresses, any roles held with their dates, and a list of people they
  are confusable with.

There is no hidden split. The archive is public; the test is not memorisation.
Visibility of the files is not the same as permission to open every message.
Headers, indexes and targeted reads are in bounds. Opening all 615 bodies to
beat grep is how the greedy strategy wins the wrong exam.

## Getting the inputs

`dist/subjects.json` ships in the repository: the ten subjects with their names,
aliases, addresses, roles and dates, and the people they are confusable with.

The corpus is rebuilt rather than distributed, because it is 615 people's mail:

```
dsarbench/fetch_debian.py     pull debian-project from lists.debian.org
dsarbench/parse.py            decode into typed blocks
dsarbench/build_inputs.py --verify
```

`show_samples.py -n 20` prints parsed messages with their block types and quote
depths, which is the quickest way to see what the task is actually made of.

`doc_id` is `dp-{year}-{month}-{msgnum}-{sha1(message_id)[:8]}`, derived only from
the public archive, so an independent rebuild produces the same ids as the answer
key. `--verify` proves it: it fingerprints every document against
`dist/corpus_manifest.json` — headers plus each block's type, depth and text —
and fails on any document that is missing, extra or altered. Run it before
building a submission. A corpus that does not match the manifest will cite
`doc_id`s the key cannot resolve, and every passage scores as unlocatable.

Scoring runs on our side. The answer key is a closed human gold set. It is not
in this repository and it is not published.

## What a system returns

JSONL, one passage per line:

```json
{"subject_id": "S1", "doc_id": "dp-2024-01-00001-00000000", "text": "verbatim quote"}
```

`text` must be copied verbatim from the document. The harness locates it and
tolerates whitespace differences, since a passage that has been through a model
rarely survives with its spacing intact. If offsets are known, `block_id` and
`span: [start, end]` may be supplied instead and are trusted as given.

A returned passage that cannot be found in the document it cites is recorded as
unlocatable and counts against precision. Quoting text that is not there is a
failure mode worth surfacing, not one worth forgiving.

When we run the agent, we also record **budget**: unique emails whose bodies
were opened, characters read, and tool calls. A JSONL drop of passages alone
does not prove the agent was selective. Budget is measured on the run, not
inferred from how many `doc_id`s appear in the file.

## What counts as personal data here

This is the standard the key is annotated against — the same Nowak reading
used in the annotation prompt. It is stated here rather than left to
judgement because an answer key without a written rule cannot be checked by
anyone, including the people who built it.

### The test

A passage is the subject's personal data when he is **identifiable** from it or
from the document around it, **and** the passage *relates to* him in at least
one of three ways (any one is enough):

| | | |
|---|---|---|
| **Content** | the passage is *about* him: views, conduct, history, situation | twenty years of his work on the packaging tools |
| **Purpose** | it is used to evaluate, treat, address or influence him | a complaint written to get the chair to intervene |
| **Result** | its use is likely to affect his rights or interests | a recommendation that he lose a delegation |

This is the content/purpose/result test from WP29 Opinion 4/2007, which the
CJEU applied in *Nowak* (C-434/16). Apply it literally.

### What Nowak settles

- A person's **own written contribution** is their personal data — the whole
  contribution, not only the sentences containing "I" or "my". The Court held
  a candidate's entire written exam answers to be his personal data. A
  continuous run of his reasoning, opinion or history is one passage.
- **What someone else writes about them** is also their personal data,
  including assessments, criticism and opinions. The examiner's comments
  about the candidate were the **candidate's** data, not only the examiner's.
- **Material about the world and not about any person** is not personal data,
  even sitting in the middle of a passage that is. The Court held the exam
  *questions* were not the candidate's data. Statistics, package descriptions,
  protocol details, general claims about software or projects: not personal
  data unless they say something about a person.

  *"The number of downstream forks is an order of magnitude higher than last
  year"* is information about the project. That he said it is a fact about
  him; the content is not. Leave it out. Return the reflection on either side.

Pronouns are not the test. "I", "you" and "he" are hints. A paragraph that
describes twenty years of his work is his even with no first-person pronoun.
A sentence containing "I" that reports a fact about a package is not.

### Authorship of a document about other people is not enough

When a subject writes an announcement, a summary or a notice whose **content**
is about other people, the body is those people's personal data, not the
author's. Only the parts that identify or describe the author — a sign-off
carrying their name and role, a first-person remark about themselves — are
the author's. Writing the questions does not make them yours.

The chair posts a welcome to new members A and B. The announcement is A's
and B's (it states their membership). It is not the chair's. His sign-off
*"-Maya, project chair"* is his.

Where a passage is his because he wrote it and his name is nowhere in it, he
is identified by the `From:` header or the attribution line of the quoted
block. That is the normal case for a person's own contribution to a
discussion, not a special first-person-feelings exception.

### One passage, several people

A passage is routinely more than one person's data at once. *"Dear Priya, I
wish to report a grievance against the review board"* is the writer's and
Priya's. Record it for every subject it belongs to. Do not pick a single
owner.

### Not his

- A different person who shares a name or first name (Maya Chen is not Maya
  Ortiz).
- A role title ("the chair") that on **this message's date** denotes someone
  else.
- A passage about a subject's package, employer or project that says nothing
  about the person.
- Second-person "you" addressed to someone who is not the subject.
- Someone is quoted, but the reply is not directed at them: the quote is not
  thereby their personal data.

Handing over the wrong person's data is itself a breach. The key records
passages that look like a match and are not, and scores returning them.

### Granularity

Return the complete thought, not the sentence fragment that happens to carry
a pronoun. Never return a bare "you", "he" or "the chair". Break a run only where
the material genuinely changes subject — for example where the author's
reflection is interrupted by a paragraph of pure statistics. In a signature
laid out in columns, return the contact detail itself, not the whole physical
line with a neighbouring column attached.

### Being someone's personal data is not a reason to delete it

Article 15 (access) is not Article 17 (erasure). Annotate what the data **is**.
A project's technical discussion does not become deletable because a
participant asked. What erasure needs is the same thing this benchmark
measures: knowing which words are whose.

## The date rule

Every judgement is made from what was knowable on the message date. "The
chair" in a message from March 2025 means whoever held that office in March
2025. Never resolve a reference using knowledge later than that message.

## Scoring

```
python3 dsarbench/score.py runs/my_agent.jsonl
```

Four numbers. None is sufficient alone.

| metric | meaning | how to cheat it |
|---|---|---|
| recall | share of closed-key YESes found | open everything; return everything |
| precision | share of returned passages that match a closed-key YES | return one certain named hit |
| decoy rate | share of closed-key NOs handed over | return nothing |
| budget | emails opened / characters read / tool calls | skip the hard slice and look cheap |

Greedy is high recall, fat budget, sloppy precision. The desired shape is
recall on the unnamed and role-dated slice, precision that holds, and a budget
that stays almost flat as the archive grows. Name search remains on the card
as the floor an agent has to beat *selectively*, not as the exam.

A passage matches a key entry when they overlap by at least half the shorter of
the two, in the same subject, document and block. Assignment is one-to-one, so
a single large span cannot claim several key entries at once. The rule is
overlap rather than equality because human and draft boundaries rarely coincide
exactly.

The scorecard also breaks recall down by whether the subject is named in the
passage at all. That cut is the one that separates grep from the task.

### What the closed key is, and is not

The scored set is human gold: every draft-key YES and every drafted trap that
entered the review queue has a mark, plus a smaller set of NOs. It is **not**
a claim that a human opened every email the draft left blank. A novel true
passage in an unreviewed email currently scores as unmatched (against
precision) until that email is reviewed. Absence from the key is not
"examined and rejected."

The key stays private because it is a curated dossier on named living people.
Publishing it would be the aggregation harm the benchmark exists to help
prevent.

## Reference floors

Name search is the keyword floor. The published percentages below were measured
against the earlier machine draft, not yet re-run against the closed key. The
shape is what matters: cautious is precise and thin; greedy buys a little
recall and starts handing over the wrong person who shares a first name.

```
                       recall   precision   decoy rate
name search, cautious   26.4%       98.2%         1.8%   (vs machine draft)
name search, greedy     32.0%       86.2%        13.2%   (vs machine draft)
```

Cautious searches full names, handles and addresses. Greedy also searches bare
first and last names, which is what a real implementation does — people sign
mail with a first name — and it immediately starts handing over the other
Maya's data instead.

Both score **0% on passages that do not contain the subject's name**, which is
definitional. Most unnamed personal data is reachable by other cheap means:
self-authored text where `From` gives it away, or a block that sits next to an
attribution line. The rest is quoted text whose attribution was stripped,
second-person criticism, and role references that resolve only through the
date. Those are the benchmark's real subject.

A name-search run that never opens a body is cheap and incomplete. An agent
that opens all 615 bodies to beat it has not done the task.

Regenerate with:

```
python3 baselines/name_search.py --mode greedy
python3 dsarbench/score.py runs/name_search_greedy.jsonl
```
