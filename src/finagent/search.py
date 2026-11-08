"""Lexical search over the passages with BM25, filtered by company and fiscal year."""

import json
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

PASSAGES = Path(__file__).resolve().parents[2] / "data" / "passages.jsonl"


def load_passages(path: Path = PASSAGES) -> list[dict]:
    """All passage records, one per line of the JSONL file."""
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def tokenize(text: str) -> list[str]:
    """The words of a text as BM25 will compare them."""
    lower_text = text.lower()
    clean_text = re.sub("[^a-z0-9]"," ",lower_text)
    words = clean_text.split()
    return words
    


def search(
    query: str,
    passages: list[dict],
    ticker: str | None = None,
    fiscal_year: int | None = None,
    k: int = 5,
    k1: float = 1.2,  # Elasticsearch default; on the plateau of the grid (scripts/tune_bm25.py)
    b: float = 0.75,
) -> list[dict]:
    """The k passages that best match the query, among those of this company and year.

    A filter left to None does not restrict anything.
    """
    candidates = [
        p for p in passages
        if (ticker is None or p["ticker"] == ticker)
        and (fiscal_year is None or p["fiscal_year"] == fiscal_year)
    ]
    if len(candidates) == 0 : 
        return []
    candidates_tokenized = [tokenize(c["text"]) for c in candidates]
    bm25 = BM25Okapi(candidates_tokenized,k1=k1,b=b)
    scores = bm25.get_scores(tokenize(query)).argsort()[-k:][::-1]
    return [candidates[i] for i in scores]