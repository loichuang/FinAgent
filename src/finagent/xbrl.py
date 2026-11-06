"""Read annual values from the SEC companyfacts files in data/xbrl/.

Traps handled here, so that question templates never see them:
- the `fy` field is the fiscal year of the filing, not of the value (Apple's 2023 revenue
  is tagged fy 2025 because the 2025 10-K repeats it), so values are keyed by period end;
- the same value is repeated by every later 10-K that compares against it, sometimes
  restated: after Nvidia's 10-for-1 split of June 2024, the fiscal 2025 10-K rewrites the
  fiscal 2024 diluted EPS from 11.93 to 1.19. The value of the 10-K that first reported the
  period is kept, since a question about that report must find its answer in it;
- some facts tagged fp "FY" cover a single quarter, so durations are checked;
- balance sheet items (Assets) are instants with no start date.
"""

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

XBRL_DIR = Path(__file__).resolve().parents[2] / "data" / "xbrl"

# A fiscal year lasts 52 or 53 weeks: 364 or 371 days, with some margin
MIN_DAYS, MAX_DAYS = 350, 380


@lru_cache(maxsize=None)
def _facts(ticker: str) -> dict:
    with open(XBRL_DIR / f"{ticker}.json", encoding="utf-8") as f:
        return json.load(f)["facts"]["us-gaap"]


def concepts(ticker: str) -> set[str]:
    """The us-gaap concepts this company reports."""
    return set(_facts(ticker))


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def annual_values(ticker: str, concept: str) -> dict[str, float]:
    """Value of a concept for each fiscal year, keyed by period end ("2024-09-28").

    Only 10-K facts are kept. A flow (revenue, net income) must cover a full fiscal year;
    a stock (assets) is read at the period end. When a later 10-K restated a value, the
    first filed one wins: it is the one written in the report of that fiscal year.
    An empty dict means the company does not report the concept.
    """
    if concept not in _facts(ticker):
        return {}
    units = _facts(ticker)[concept]["units"]
    unit = next(iter(units))  # USD, or USD/shares for earnings per share
    first = {}  # period end -> (filed, value)
    for fact in units[unit]:
        if fact.get("form") != "10-K":
            continue
        if "start" in fact and not MIN_DAYS <= _days(fact["start"], fact["end"]) <= MAX_DAYS:
            continue
        end = fact["end"]
        if end not in first or fact["filed"] < first[end][0]:
            first[end] = (fact["filed"], fact["val"])
    return {end: value for end, (_, value) in sorted(first.items())}


def unit(ticker: str, concept: str) -> str:
    """The unit of a concept: "USD" or "USD/shares"."""
    return next(iter(_facts(ticker)[concept]["units"]))
