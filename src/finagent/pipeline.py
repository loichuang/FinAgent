"""The retrieval of step 6, as one function shared by ask.py and the evaluation of step 8.

RRF fusion of BM25 (on the cleaned question) and dense search (on the raw question), both
filtered on the company and fiscal year of the question. The DEPTH first results of each
method are fused, and the K best are handed to the LLM (K = 10, decided at step 6).
"""

import numpy as np

from finagent.query import clean_query
from finagent.questions import names
from finagent.search import dense_search, rrf, search

K, DEPTH = 10, 50


def retrieve(question: dict, passages: list[dict], embeddings: dict[str, np.ndarray],
             k: int = K, depth: int = DEPTH) -> list[dict]:
    """The k passages given to the LLM for this question record."""
    ticker, year = question["ticker"], question["fiscal_year"]
    query = clean_query(question["question"], names[ticker])
    lexical = search(query, passages, ticker=ticker, fiscal_year=year, k=depth)
    dense = dense_search(question["question"], passages, embeddings,
                         ticker=ticker, fiscal_year=year, k=depth)
    return rrf([lexical, dense], k=k)
