"""Numeric questions generated from XBRL, each with its exact answer."""

from finagent.search import load_passages
from finagent.xbrl import annual_values, unit

# Company names as a user would write them. If the corpus grows, read "entityName"
# from data/xbrl/ instead and strip "Inc." or "Corporation".
names = {
    "AAPL": "Apple",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "MSFT": "Microsoft",
    "NVDA": "Nvidia",
}


def period_ends() -> dict[str, list[tuple[str, int]]]:
    """For each ticker, its (period end, fiscal year) pairs, read from the corpus."""
    ends = {}
    for p in load_passages():
        ends.setdefault(p["ticker"], set()).add((p["period_end"], p["fiscal_year"]))
    return {ticker: sorted(pairs) for ticker, pairs in ends.items()}


def concept_questions(concept: str, label: str) -> list[dict]:
    """One question per company and fiscal year of the corpus about this concept.

    A fiscal year for which XBRL has no value gets no question.
    """
    questions = []
    for ticker, pairs in period_ends().items():
        values = annual_values(ticker, concept)
        for period_end, fiscal_year in pairs:
            if period_end not in values:
                continue
            questions.append({
                "id": f"{ticker}_{period_end}_{concept}",
                "question": f"What was {names[ticker]}'s {label} for the fiscal year "
                            f"ended {period_end}?",
                "ticker": ticker,
                "fiscal_year": fiscal_year,
                "period_end": period_end,
                "concept": concept,
                "value": values[period_end],
                "unit": unit(ticker, concept),
            })
    return questions
