"""Scoring harness for DSAR-Bench.

Separate from the annotation pipeline on purpose: everything under dsarbench/
outside this package exists to BUILD the answer key, and none of it should be
importable from a scoring run. A submission is scored against the key on disk
and nothing else -- no model calls, no network, deterministic.

  corpus      load the corpus, the subjects and the key
  submission  read a submission file and anchor each quoted passage to a block
  matching    overlap rule and one-to-one assignment between prediction and key
  metrics     recall, precision, decoy rate, and the breakdowns
  report      render a scorecard as text or JSON
"""

from .corpus import Key, load_corpus, load_key  # noqa: F401
from .matching import assign, overlap_frac  # noqa: F401
from .metrics import Scorecard, score  # noqa: F401
from .submission import Prediction, read_submission  # noqa: F401

__all__ = ["Key", "load_corpus", "load_key", "assign", "overlap_frac",
           "Scorecard", "score", "Prediction", "read_submission"]
