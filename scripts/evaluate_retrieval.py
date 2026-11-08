"""Recall at k of the BM25 search, with the raw question and with clean_query.

Measured on the tuning set by default. The test set is measured once, at the end:
    .venv/bin/python scripts/evaluate_retrieval.py            # tuning
    .venv/bin/python scripts/evaluate_retrieval.py --test     # test, held-out phrasing apart
"""
import argparse
import json
from pathlib import Path

from finagent.evaluate import recall_at_k
from finagent.query import clean_query
from finagent.questions import names
from finagent.search import load_passages

DATA = Path(__file__).resolve().parent.parent / "data"
KS = (1, 5, 10)

parser = argparse.ArgumentParser()
parser.add_argument("--test", action="store_true", help="measure the test set instead of tuning")
split = "test" if parser.parse_args().test else "tuning"

passages = load_passages()
with open(DATA / "questions.jsonl", encoding="utf-8") as f:
    questions = [json.loads(line) for line in f if line.strip()]
questions = [q for q in questions if q["split"] == split]


def cleaned(qs: list[dict]) -> list[dict]:
    """The same questions, their text replaced by clean_query."""
    return [dict(q, question=clean_query(q["question"], names[q["ticker"]])) for q in qs]


def row(name: str, qs: list[dict]) -> None:
    scores = "  ".join(f"R@{k} {recall_at_k(qs, passages, k):.3f}" for k in KS)
    print(f"{name:<36}{scores}   ({len(qs)} questions)")


# Groups: the three templates, then the held-out phrasing (test set only)
groups = {f"template {n}": [q for q in questions if q["id"].endswith(f"_{n}")] for n in "012"}
heldout = [q for q in questions if q.get("heldout")]
if heldout:
    groups["held-out phrasing"] = heldout

print(f"Split: {split}\n")
row("raw, all", [q for q in questions if not q.get("heldout")])
row("clean_query, all", cleaned([q for q in questions if not q.get("heldout")]))
print()
for name, qs in groups.items():
    row(f"clean_query, {name}", cleaned(qs))
