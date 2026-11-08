"""Search over the passages, filtered by company and fiscal year: lexical (BM25), dense,
and their fusion (RRF)."""

import json
import re
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from finagent.embed import embed_query

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


def dense_search(
    question: str,
    passages: list[dict],
    embeddings: dict[str, np.ndarray],
    ticker: str | None = None,
    fiscal_year: int | None = None,
    k: int = 5,
) -> list[dict]:
    """The k passages whose embedding is closest to the question's, among those of this
    company and year.

    embeddings maps a passage id to its normalised vector (load_embeddings), so the
    cosine of the question and a passage is their dot product. The question is given
    raw, not cleaned: the model needs the whole sentence.
    """
    candidates = [
        p for p in passages
        if (ticker is None or p["ticker"] == ticker)
        and (fiscal_year is None or p["fiscal_year"] == fiscal_year)
    ]
    if len(candidates) == 0 : 
        return []
    embedding_question = embed_query(question)
    P = np.array([embeddings[c["id"]] for c in candidates])
    cos_candidate = P @ embedding_question
    best_candidates = cos_candidate.argsort()[-k:][::-1]
    return [candidates[i] for i in best_candidates]
        
    

def rrf(rankings: list[list[dict]], k: int = 5, k_rrf: int = 60) -> list[dict]:
    """The k best passages of the fusion of several rankings, by Reciprocal Rank Fusion.

    Each ranking lists passages from best to worst. A passage scores
    1 / (k_rrf + rank) in every ranking where it appears, rank starting at 1, and
    nothing in a ranking where it does not. Passages are identified by their "id".
    """
    scores = {} 
    passages = {}
    for classement in rankings : 
        for rank, passage in enumerate(classement, start=1):
            score = 1/(k_rrf + rank)
            if passage["id"] in scores :
                scores[passage["id"]] += score
            else : 
                scores[passage["id"]] = score
                passages[passage["id"]] = passage
    sorted_scores = sorted(scores, key=scores.get, reverse=True)
    return [passages[id] for id in sorted_scores[:k]]
    
        
