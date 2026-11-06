"""Numeric questions generated from XBRL, each with its exact answer."""

from finagent.search import load_passages
from finagent.xbrl import annual_values, unit
from datetime import date

# Company names as a user would write them. If the corpus grows, read "entityName"
# from data/xbrl/ instead and strip "Inc." or "Corporation".
names = {
    "AAPL": "Apple",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "MSFT": "Microsoft",
    "NVDA": "Nvidia",
}


# Label in the question -> XBRL concepts that may carry it, in order of preference.
# For each company and year, the first concept with a value is used.
# Left out on purpose, because Amazon or Alphabet do not report them under this name:
# GrossProfit, Liabilities, ResearchAndDevelopmentExpense.
CONCEPTS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
    "net income": ["NetIncomeLoss"],
    "operating income": ["OperatingIncomeLoss"],
    "diluted earnings per share": ["EarningsPerShareDiluted"],
    "total assets": ["Assets"],
    "total stockholders' equity": ["StockholdersEquity"],
    "cash and cash equivalents": ["CashAndCashEquivalentsAtCarryingValue"],
    "long-term debt": ["LongTermDebtNoncurrent"],
    "net cash provided by operating activities": ["NetCashProvidedByUsedInOperatingActivities"],
    # Nvidia's concept also includes intangible assets: the answer is what each company reports
    "capital expenditures": ["PaymentsToAcquirePropertyPlantAndEquipment",
                             "PaymentsToAcquireProductiveAssets"],
    "cost of revenue": ["CostOfGoodsAndServicesSold", "CostOfRevenue"],
    "income tax expense": ["IncomeTaxExpenseBenefit"],
    "share-based compensation": ["ShareBasedCompensation"],
    "weighted average diluted shares outstanding": [
        "WeightedAverageNumberOfDilutedSharesOutstanding"],
    "total current assets": ["AssetsCurrent"],
    "total current liabilities": ["LiabilitiesCurrent"],
}


def period_ends() -> dict[str, list[tuple[str, int]]]:
    """For each ticker, its (period end, fiscal year) pairs, read from the corpus."""
    ends = {}
    for p in load_passages():
        ends.setdefault(p["ticker"], set()).add((p["period_end"], p["fiscal_year"]))
    return {ticker: sorted(pairs) for ticker, pairs in ends.items()}


def concept_questions(label: str) -> list[dict]:
    """One question per company and fiscal year of the corpus about this label.

    For each year, the first candidate concept with a value is used.
    A fiscal year for which no candidate has a value gets no question.
    """
    candidates = CONCEPTS[label]
    questions = []
    for ticker, pairs in period_ends().items():
        for period_end, fiscal_year in pairs:
            # The first candidate that has a value for this year
            concept = None
            for c in candidates : 
                if period_end in annual_values(ticker,c):
                    concept = c
                    break
            if concept is None:
                continue
            value = annual_values(ticker,concept)[period_end]

            questions.append({
                "id": f"{ticker}_{period_end}_{concept}",
                "question": f"What was {names[ticker]}'s {label} for the fiscal year "
                            f"ended {_long_date(period_end)}?",
                "ticker": ticker,
                "fiscal_year": fiscal_year,
                "period_end": period_end,
                "concept": concept,
                "value": value,
                "unit": unit(ticker, concept),
            })
    return questions


def _long_date(iso: str) -> str:
    """A YYYY-MM-DD date as a person writes it: "2024-09-28" gives "September 28, 2024"."""
    d = date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}, {d.year}"
