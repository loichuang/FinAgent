"""Numeric questions generated from XBRL, each with its exact answer."""

from finagent.search import load_passages
from finagent.xbrl import annual_values, unit
import random
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


# Phrasings of the same question. Fields: company, label, date (written out), year.
# "fiscal {year}" follows each company's own naming: Nvidia's fiscal 2025 ends in January 2025.
TEMPLATES = [
    "What was {company}'s {label} for the fiscal year ended {date}?",
    "How much {label} did {company} report for fiscal {year}?",
    "In its 10-K for fiscal {year}, what {label} did {company} report?",
]


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

            # One question per phrasing, the id ends with the template number
            for numero, gabarit in enumerate(TEMPLATES) : 
                questions.append({
                    "id": f"{ticker}_{period_end}_{concept}_{numero}",
                    "question": gabarit.format(company=names[ticker],label = label, date= _long_date(period_end),year= fiscal_year),
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


def all_questions() -> list[dict]:
    """The questions of every label in CONCEPTS."""
    return [q for label in CONCEPTS for q in concept_questions(label)]


def heldout_questions(questions: list[dict], template: str) -> list[dict]:
    """One extra question per test fact, written with a phrasing never seen in tuning.

    Call it after assign_split. The phrasing is written by hand and kept out of the
    tuning set, so the test measures whether the query cleaning works on a wording
    it was not designed on, not only on the three TEMPLATES.
    """
    label_of = {c: label for label, concepts in CONCEPTS.items() for c in concepts}
    extra = []
    seen = set()
    for q in questions:
        fact = (q["ticker"], q["period_end"], q["concept"])
        if q["split"] != "test" or fact in seen:
            continue
        seen.add(fact)
        extra.append({
            "id": f"{q['ticker']}_{q['period_end']}_{q['concept']}_heldout",
            "question": template.format(
                company=names[q["ticker"]],
                label=label_of[q["concept"]],
                date=_long_date(q["period_end"]),
                year=q["fiscal_year"],
            ),
            **{k: v for k, v in q.items() if k not in ("id", "question")},
            "heldout": True,
        })
    return extra


def assign_split(questions: list[dict], test_share: float = 0.5, seed: int = 0) -> None:
    """Add a "split" field, "tuning" or "test", to every question, in place.

    The split is drawn per fact (ticker, period end, concept), never per question:
    the phrasings of one fact all go to the same side, so the test set holds no
    answer already seen during tuning.
    """
    # Distinct facts, sorted so that the shuffle always starts from the same order
    facts = sorted({(q["ticker"], q["period_end"], q["concept"]) for q in questions})

    # Same seed, same shuffle
    rng = random.Random(seed)
    rng.shuffle(facts)

    # The first test_share of the shuffled facts go to test
    f = int(len(facts) * test_share)
    test_facts = set(facts[:f])

    for q in questions : 
        fact = (q["ticker"], q["period_end"], q["concept"])
        if fact in test_facts :  
            q["split"]  = "test"
        else : 
            q["split"] = "tuning"

