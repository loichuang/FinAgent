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
    """The k passages given to the LLM for this question record.

    A passage that starts inside a table gets the header of that table in front of its text
    (step 8a-bis): copies are returned, the passages of the corpus are never modified.
    """
    ticker, year = question["ticker"], question["fiscal_year"]
    query = clean_query(question["question"], names[ticker])
    lexical = search(query, passages, ticker=ticker, fiscal_year=year, k=depth)
    dense = dense_search(question["question"], passages, embeddings,
                         ticker=ticker, fiscal_year=year, k=depth)
    by_id = {p["id"]: p for p in passages}
    return [with_table_header(p, by_id) for p in rrf([lexical, dense], k=k)]


# ---------------------------------------------------------------------------
# Table headers (step 8a-bis, diagnostic_8a.md)
# ---------------------------------------------------------------------------
# Chunking cuts tables: 369 passages out of 2 504 start inside a table whose title, scale
# ("In millions") and column row ("2023 | 2024") stayed in an earlier passage. Without
# them the model answers in units and guesses the column order (Alphabet puts the oldest
# year first). The header is found by walking back to the passage that opens the table.

OPEN, CLOSE = "[TABLE]", "[/TABLE]"
MAX_STEPS = 5  # measured: the header is 1 passage back in 361 cases, 2 back in 19, never more


def starts_inside_table(text: str) -> bool:
    """True if the passage starts inside a table opened in an earlier passage.

    Either a closing tag comes before any opening tag, or there is no tag at all but table
    rows (lines with "|"): a long table that runs through the whole passage.
    """
    opening, closing = text.find(OPEN), text.find(CLOSE)
    if closing != -1:
        return opening == -1 or closing < opening
    return opening == -1 and any("|" in line for line in text.splitlines())


def header_of(text: str) -> str:
    """The header of the last table opened in text: the two lines before the opening tag
    (title, scale) not belonging to a previous table, then the lines after it up to the first
    table row included (columns).
    "" if text opens no table.
    """
    at = text.rfind(OPEN)
    if at == -1:
        return ""
    # Lines before the opening tag, but never from the previous table (after its [/TABLE])
    preamble = text[:at].rsplit(CLOSE, 1)[-1]
    before = [line for line in preamble.splitlines() if line.strip()][-2:]
    after = []
    for line in text[at + len(OPEN):].splitlines():
        if not line.strip():
            continue
        after.append(line)
        if "|" in line:
            break
    return "\n".join(before + after)


def previous_id(passage_id: str) -> str:
    """'GOOGL_2024_8_7' -> 'GOOGL_2024_8_6': the passage before, in the same Item."""
    stem, count = passage_id.rsplit("_", 1)
    return f"{stem}_{int(count) - 1}"


def table_header(passage: dict, by_id: dict[str, dict]) -> str:
    """The header of the table the passage starts in, "" if it starts outside a table or
    if no opening tag is found within MAX_STEPS passages of the same Item."""
    if not starts_inside_table(passage["text"]):
        return ""
    current = passage
    for _ in range(MAX_STEPS):
        current = by_id.get(previous_id(current["id"]))
        if current is None:
            return ""
        if OPEN in current["text"]:
            return header_of(current["text"])
    return ""


def with_table_header(passage: dict, by_id: dict[str, dict]) -> dict:
    """A copy of the passage with its table header in front, or the passage itself."""
    header = table_header(passage, by_id)
    if not header:
        return passage
    return {**passage, "text": header + "\n" + passage["text"]}
