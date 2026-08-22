# Related work, and what is new here

Surveyed August 2026. The claim is scoped deliberately: one contribution that is
unclaimed, and a clear account of which components are prior art. Reviewers will
reach for the Text Anonymization Benchmark first, so it is addressed directly
below.

## The gap that is real

There is no benchmark for Article 15 fulfilment as a retrieval task. The
privacy-agent literature measures **over**-disclosure — whether an agent leaks
data it should have withheld. This measures **under**-disclosure — whether a
system fails to return data the subject is legally entitled to receive. That
inversion is the contribution, and it should be the first sentence of any
description of this project.

What exists in the DSAR space is not comparable:

- [DSAR Packages dataset](https://zenodo.org/records/11634938) (APF 2024,
  [paper](https://arxiv.org/pdf/2407.04470)) — real export packages from Amazon,
  Apple, Facebook, Google and LinkedIn, for two people. A format-exploration
  resource with no passage-level annotation.
- [TU Delft SAR-dataset](https://github.com/hadiasghari/SAR-dataset) — encoded
  subject access *responses* for policy research, no NLP ground truth.
- [PrivaCI-Bench](https://arxiv.org/abs/2502.17041) (ACL 2025) — 140k multiple
  choice items on whether a data flow is compliant. Judgement, not retrieval.
- [ACCESS DENIED INC](https://aclanthology.org/2025.findings-acl.684.pdf)
  (Findings ACL 2025) — synthetic corporate environment testing whether a model
  honours access-control rules. Access control, not access requests.

Commercial DSAR discovery tools all claim contextual, nickname-aware search over
email, and none publish an evaluation set. That absence is an argument for this
benchmark rather than against it.

## The closest neighbour: TAB

[The Text Anonymization Benchmark](https://aclanthology.org/2022.cl-4.19/)
(Computational Linguistics, 2022) is the work to compare against. It is larger
and human-annotated; it runs in the opposite direction.

|  | TAB | this |
|---|---|---|
| corpus | 1,268 real ECHR judgments | 615 real mailing-list emails |
| task unit | per target person | per target person |
| annotators | trained law students, double-annotated, IAA reported | two Gemini models, reconciled |
| negatives | yes, `NO_MASK` spans | yes, 280 explicit |
| indirect reference | yes — coreference chains and quasi-identifiers | yes |
| temporal | no | yes, date-frozen |
| direction | which spans must be **hidden** | which passages must be **disclosed** |

The two tasks are close to duals, and the distinction rests on two things. The
direction changes the error economics: a missed span in TAB is a privacy breach,
a missed passage here is an incomplete legal response, and the systems that fix
one do not fix the other. And ECHR judgments are single-narrator prose, where
email carries quoting, nesting and multi-party attribution — which is where this
key's hard cases live.

## Prior art covering individual components

These are established elsewhere and are not claimed here.

**Typed email block parsing.** The [Webis Gmane Email Corpus
2019](https://zenodo.org/records/3766985) ([ACL
2020](https://aclanthology.org/2020.acl-main.108/)) segments 153M emails from
14,699 public mailing lists into 15 classes at 96% accuracy — including
`quotation`, `quotation_marker`, `personal_signature`, `mua_signature` and
`technical` — the same job as `blocks.py`, on a corpus 250,000 times larger, with
published accuracy. `blocks.py` is therefore plumbing rather than a contribution,
and is described as such.

It stays in place, for one reason: it is full-fidelity. Webis labels spans and so
preserves them, but the mainstream email libraries discard quoted text and
attribution lines by design, and substituting one measurably destroys 51.4% of
this key. Scoring `blocks.py` against Webis for
segmentation accuracy remains a fair comparison to run.

**Explicit negatives.** [PII-Bench](https://arxiv.org/html/2502.18545v1) ships a
`PII-distract` split; TAB ships `NO_MASK`;
[GAP](https://github.com/google-research-datasets/gap-coreference) (TACL 2018)
is built entirely from ambiguous pronoun–name pairs where one candidate is
wrong — 8,908 of them, decoys of the shared-first-name kind. What remains defensible is framing the decoy rate as a *legal* failure
mode: disclosing the wrong person's data is itself a GDPR breach, not merely a
precision error.

**Indirect reference.** TAB, [SPIA](https://aclanthology.org/2026.acl-long.778/)
(ACL 2026) and [RAT-Bench](https://arxiv.org/abs/2602.12806) all handle
reference beyond literal names, and RAT-Bench shows indirect identifiers
dominate residual re-identification risk.

**Coreference in email.** [CEREC](https://arxiv.org/abs/2105.10606) (COLING
2020): 6,001 Enron threads, 36,448 messages, 38,996 coreference chains — though
weakly labelled by SpanBERT rather than humans, with a best baseline of 54.1 F1.
Its human-annotated seed ([Dakle et al., LREC
2020](https://aclanthology.org/2020.lrec-1.8.pdf)) is 46 threads.

**Difficulty tiers.** Standard practice.

**Temporal role resolution.** [TempEL](https://github.com/klimzaporojets/TempEL)
(NeurIPS 2022) and [TDBench](https://arxiv.org/abs/2508.02045) (2025) both do
this; TDBench's worked example is literally `country, role →ᵀ name`. What is not
established is temporal resolution as a *disclosure correctness* condition.

## Where the neighbours set the bar

**Annotation provenance.** Two models from the same family reconciling each other
is a silver standard: it establishes consistency, not correctness. TAB used
trained law students with reported agreement; the [i2b2/n2c2 2014
challenge](https://portal.dbmi.hms.harvard.edu/projects/n2c2-2014/) used double
annotation plus arbitration and reported annotator F1 of 0.927 against gold.
CEREC took the model-labelled route and the follow-up literature treats that as
its limiting factor. The scored set here is a closed human key, not published. Numbers quoted
against a machine draft are not the exam.

**Subject count.** Ten subjects across seven tiers is thin next to TAB's 1,268
target-person tasks; several per-tier cells are empty and the rest carry wide
intervals. Resolved by broadening the subject list or collapsing the tiers.

**Reporting unit.** SPIA argues span-level metrics are the wrong unit and moves to
per-subject protection rates. Results here are reported per subject and per tier
for that reason; the micro-average is never quoted alone.

**Ethics.** TAB used judgments published with applicant consent; i2b2
substituted surrogate identifiers. Debian archives are public, but assembling
per-person dossiers indexed by name is a different act from the archive being
readable. See PROVENANCE.md (same directory); the key files are gitignored for this reason, and
pseudonymization via mapping.json should precede any release.
