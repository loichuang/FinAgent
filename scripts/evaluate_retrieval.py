"""Recall at k of the three searches: BM25 (raw and cleaned query), dense, and their RRF fusion.

Measured on the tuning set by default. The test set is measured once, at the end:
    .venv/bin/python scripts/evaluate_retrieval.py            # tuning
    .venv/bin/python scripts/evaluate_retrieval.py --test     # test, held-out phrasing apart
"""
import argparse
import json
from pathlib import Path

from finagent.embed import load_embeddings
from finagent.evaluate import recall_at_k
from finagent.query import clean_query
from finagent.questions import names
from finagent.search import dense_search, load_passages, rrf, search

DATA = Path(__file__).resolve().parent.parent / "data"
KS = (1, 5, 10)
DEPTH = 50  # passages each method hands to the fusion before the k best are kept

parser = argparse.ArgumentParser()
parser.add_argument("--test", action="store_true", help="measure the test set instead of tuning")
split = "test" if parser.parse_args().test else "tuning"

passages = load_passages()
embeddings = load_embeddings()
with open(DATA / "questions.jsonl", encoding="utf-8") as f:
    questions = [json.loads(line) for line in f if line.strip()]
questions = [q for q in questions if q["split"] == split]


def bm25(q: dict, k: int) -> list[dict]:
    """BM25 on the cleaned question."""
    query = clean_query(q["question"], names[q["ticker"]])
    return search(query, passages, ticker=q["ticker"], fiscal_year=q["fiscal_year"], k=k)


def bm25_raw(q: dict, k: int) -> list[dict]:
    """BM25 on the question as written."""
    return search(q["question"], passages, ticker=q["ticker"], fiscal_year=q["fiscal_year"], k=k)


def dense(q: dict, k: int) -> list[dict]:
    """Dense search on the raw question: the model needs the whole sentence."""
    return dense_search(q["question"], passages, embeddings,
                        ticker=q["ticker"], fiscal_year=q["fiscal_year"], k=k)


def hybrid(q: dict, k: int) -> list[dict]:
    """RRF fusion of the DEPTH first results of BM25 (cleaned) and dense (raw)."""
    return rrf([bm25(q, DEPTH), dense(q, DEPTH)], k=k)


METHODS = {"BM25 raw": bm25_raw, "BM25 clean_query": bm25, "dense": dense, "RRF (BM25 + dense)": hybrid}


def row(name: str, qs: list[dict], retrieve) -> None:
    scores = "  ".join(f"R@{k} {recall_at_k(qs, passages, k, retrieve=retrieve):.3f}" for k in KS)
    print(f"{name:<36}{scores}   ({len(qs)} questions)")


seen = [q for q in questions if not q.get("heldout")]
heldout = [q for q in questions if q.get("heldout")]

print(f"Split: {split}\n")
for name, retrieve in METHODS.items():
    row(f"{name}, all", seen, retrieve)

print()
for n in "012":
    row(f"BM25 clean_query, template {n}", [q for q in seen if q["id"].endswith(f"_{n}")], bm25)

if heldout:
    print()
    for name, retrieve in METHODS.items():
        row(f"{name}, held-out", heldout, retrieve)
