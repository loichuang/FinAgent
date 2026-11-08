import numpy as np

import finagent.search as search_module
from finagent.search import dense_search, rrf


def _ids(passages):
    return [p["id"] for p in passages]


def test_rrf_example_of_the_theory():
    A, C, E, B, F = ({"id": x} for x in "ACEBF")
    # A: 1/61 + 1/62, C: 1/63 + 1/61, E: 1/62 + 1/64, F: 1/63, B: 1/64
    assert _ids(rrf([[A, E, C, B], [C, A, F, E]], k=5)) == ["A", "C", "E", "F", "B"]


def test_rrf_any_number_of_rankings_and_empty():
    A, C, E = ({"id": x} for x in "ACE")
    assert _ids(rrf([[A, E, C]], k=2)) == ["A", "E"]
    assert _ids(rrf([[A], [C, A], [E, A]], k=3))[0] == "A"
    assert rrf([[], []]) == []


def test_dense_search_ranks_by_dot_product_and_filters(monkeypatch):
    # A fake question vector replaces the model: no download, no randomness
    monkeypatch.setattr(search_module, "embed_query", lambda q: np.array([1.0, 0.0]))
    passages = [
        {"id": "a", "ticker": "AAPL", "fiscal_year": 2024},
        {"id": "b", "ticker": "AAPL", "fiscal_year": 2024},
        {"id": "c", "ticker": "AAPL", "fiscal_year": 2023},
        {"id": "d", "ticker": "MSFT", "fiscal_year": 2024},
    ]
    embeddings = {
        "a": np.array([0.6, 0.8]),  # cosine 0.6
        "b": np.array([1.0, 0.0]),  # cosine 1.0
        "c": np.array([1.0, 0.0]),  # best, but wrong year
        "d": np.array([1.0, 0.0]),  # best, but wrong company
    }
    found = dense_search("q", passages, embeddings, ticker="AAPL", fiscal_year=2024, k=5)
    assert _ids(found) == ["b", "a"]
    assert dense_search("q", passages, embeddings, ticker="XXX") == []
