"""Grid search of BM25's k1 and b on the tuning set, with the cleaned queries.

Prints every score, not only the best, so the journal keeps the whole grid.
The test set is never read here.
"""
import json
from pathlib import Path

from finagent.evaluate import recall_at_k
from finagent.query import clean_query
from finagent.questions import names
from finagent.search import load_passages

K1_VALUES = [0.9, 1.2, 1.5, 2.0]
B_VALUES = [0.5, 0.75, 0.9]
K = 5

DATA = Path(__file__).resolve().parent.parent / "data"
passages = load_passages()
with open(DATA / "questions.jsonl", encoding="utf-8") as f:
    questions = [json.loads(line) for line in f if line.strip()]
questions = [q for q in questions if q["split"] == "tuning"]


def cleaned(qs: list[dict]) -> list[dict]:
    """The same questions, their text replaced by clean_query."""
    return [dict(q, question=clean_query(q["question"], names[q["ticker"]])) for q in qs]


questions = cleaned(questions)

scores = {}
for k1 in K1_VALUES:
    for b in B_VALUES:
        scores[(k1, b)] = recall_at_k(questions, passages, K, k1=k1, b=b)
        print(f"k1 {k1:<4}  b {b:<4}  R@{K} {scores[(k1, b)]:.3f}")

best = max(scores, key=scores.get)
print(f"\nBest: k1 {best[0]}, b {best[1]}, R@{K} {scores[best]:.3f}")
print(f"rank-bm25 default (k1 1.5, b 0.75): R@{K} {scores[(1.5, 0.75)]:.3f}")
