"""The XBRL tools the model can call (phase 2, docs/phase2_design.md).

The model never reads XBRL. It reads the tool cards (FACT_TOOL, RATIO_TOOL), fills in their
arguments, and the code runs the lookup or the computation and sends the result back.
"""

from finagent.questions import CONCEPTS, names, period_ends
from finagent.xbrl import MAX_DAYS, MIN_DAYS, _days, annual_values, unit


# The tool card the model reads at every turn of the loop. The allowed values come from
# questions.py, so the tool and the benchmark always share the same companies and labels.
FACT_TOOL = {
    "name": "get_fact",
    "description": (
        "Get a figure that a company reported in its annual report (10-K) for one fiscal "
        "year: revenue, net income, total assets, cash flows and the other items listed in "
        "`concept`. Call it whenever the question asks for such a figure, instead of reading "
        "it from text or answering from memory. Give the period exactly as the question "
        "states it: if the question gives a date, fill `period_end` with that date; if it "
        "gives a fiscal year (\"fiscal 2025\"), fill `fiscal_year` with that number. Never "
        "convert one into the other: companies name their fiscal years differently. If the "
        "question gives no period, leave both empty: the latest fiscal year in the data is "
        "used, and the result names it. Always state the fiscal year in your answer."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "company": {
                "type": "string",
                "enum": sorted(names),
                "description": "Ticker of the company: "
                               + ", ".join(f"{t} ({n})" for t, n in sorted(names.items())) + ".",
            },
            "concept": {
                "type": "string",
                "enum": list(CONCEPTS),
                "description": "The item asked for, picked from this list.",
            },
            "period_end": {
                "type": "string",
                "description": "Last day of the fiscal year, YYYY-MM-DD, when the question "
                               "gives a date.",
            },
            "fiscal_year": {
                "type": "integer",
                "description": "Fiscal year as the company names it, when the question "
                               "gives one.",
            },
        },
        "required": ["company", "concept"],
        "additionalProperties": False,
    },
}

# Labels the ratios need beyond CONCEPTS. Kept apart on purpose: CONCEPTS also generates the
# benchmark (all_questions), and a new label there would add questions and reshuffle the frozen
# tuning/test split. "optional": the company may not report the item because it has none, so
# absent means 0. Otherwise absent is an error: a 0 would distort the ratio without a sound.
# Each optional rule was checked against the 10-K text.
RATIO_CONCEPTS = {
    # Debt: all financial debt, whatever its maturity. Cash: cash and current securities
    "long-term debt including current portion": {"xbrl": ["LongTermDebt"], "optional": False},
    # Microsoft and Nvidia 2026: no commercial paper outstanding, nothing tagged
    "commercial paper": {"xbrl": ["CommercialPaper"], "optional": True},
    # Amazon only, under 1 % of its debt
    "short-term borrowings": {"xbrl": ["ShortTermBorrowings"], "optional": True},
    # Nvidia 2026 tags it with its own concept, absent from companyfacts: an error, not a 0
    "current marketable securities": {"xbrl": ["MarketableSecuritiesCurrent",
                                               "ShortTermInvestments"], "optional": False},
    # Cycle
    "accounts receivable": {"xbrl": ["AccountsReceivableNetCurrent"], "optional": False},
    # Alphabet holds no inventory: DIO and CCC are not applicable to it, never 0
    "inventory": {"xbrl": ["InventoryNet"], "optional": False},
    "accounts payable": {"xbrl": ["AccountsPayableCurrent"], "optional": False},
    # Financing. Amazon pays no dividend: a true 0
    "dividends paid": {"xbrl": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
                       "optional": True},
    # TODO before the financing group: one Amazon year is missing, check the 10-K text
    "share repurchases": {"xbrl": ["PaymentsForRepurchaseOfCommonStock"], "optional": False},
}


def avg(label: str) -> tuple[str, str]:
    """Mark a balance sheet label to be averaged over the fiscal year (opening and closing),
    for ROE, ROIC and Du Pont: in RATIOS, write avg("total assets")."""
    return ("avg", label)


def _sbc_to_fcf(sbc: float, cfo: float, capex: float) -> float:
    """Share of free cash flow paid out as stock. A ratio to a negative or zero FCF means
    nothing (a larger SBC would look smaller), so it is refused rather than computed."""
    fcf = cfo - capex
    if fcf <= 0:
        raise ValueError(f"free cash flow is {fcf:.0f} USD, not positive: SBC to FCF is not "
                         f"meaningful.")
    return sbc / fcf


# Ratio name -> the labels it needs, in the order of the formula's arguments.
# Python computes every ratio: the model never does arithmetic.
CFO, CAPEX = "net cash provided by operating activities", "capital expenditures"
RATIOS = {
    "gross margin": {"labels": ["revenue", "cost of revenue"],
                     "formula": lambda rev, cogs: (rev - cogs) / rev},
    "operating margin": {"labels": ["operating income", "revenue"],
                         "formula": lambda ebit, rev: ebit / rev},
    "fcf margin": {"labels": [CFO, CAPEX, "revenue"],
                   "formula": lambda cfo, capex, rev: (cfo - capex) / rev},
    "sbc to fcf": {"labels": ["share-based compensation", CFO, CAPEX],
                   "formula": _sbc_to_fcf},
}

# Caveats the model must pass on with the figure: the ratio is computed right, but read alone
# it would lead to a wrong conclusion. Each one checked against the 10-K text.
_NVDA_CAPEX = ("Nvidia's capital expenditures include intangible assets (its 10-K line is "
               "\"purchases related to property and equipment and intangible assets\"), so its "
               "free cash flow is computed on a wider base than the other companies'.")
_AMZN_FCF = ("Free cash flow here is operating cash flow minus gross purchases of property and "
             "equipment. Amazon's own free cash flow subtracts them net of proceeds from sales "
             "and incentives, so it differs from the figure Amazon publishes.")
NOTES = {
    ("AMZN", "gross margin"): "Amazon books fulfillment outside cost of revenue, so its gross "
                              "margin is not comparable with the other companies'.",
    ("AMZN", "fcf margin"): _AMZN_FCF,
    ("AMZN", "sbc to fcf"): _AMZN_FCF,
    ("NVDA", "fcf margin"): _NVDA_CAPEX,
    ("NVDA", "sbc to fcf"): _NVDA_CAPEX,
}

# The card of the second tool. Same company and period arguments as FACT_TOOL, so the model fills
# both tools the same way; only the ratio list differs.
RATIO_TOOL = {
    "name": "get_ratio",
    "description": (
        "Get a financial ratio of a company for one fiscal year, computed from the figures of "
        "its annual report (10-K): gross margin, operating margin, free cash flow margin "
        "(fcf margin) and stock-based compensation as a share of free cash flow (sbc to fcf). "
        "Call it whenever the question asks for one of these ratios, instead of fetching the "
        "figures with get_fact and computing the ratio yourself: never do the arithmetic. "
        "The result gives the ratio, the figures it was computed from and any caveat; pass "
        "the caveat on. Fill the period exactly as for get_fact: period_end when the question "
        "gives a date, fiscal_year when it gives a fiscal year, neither when it gives none."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "company": FACT_TOOL["input_schema"]["properties"]["company"],
            "ratio": {
                "type": "string",
                "enum": list(RATIOS),
                "description": "The ratio asked for, picked from this list.",
            },
            "period_end": FACT_TOOL["input_schema"]["properties"]["period_end"],
            "fiscal_year": FACT_TOOL["input_schema"]["properties"]["fiscal_year"],
        },
        "required": ["company", "ratio"],
        "additionalProperties": False,
    },
}


def _resolve_period(ticker: str, period_end: str, fiscal_year: int) -> tuple[str, int] : 
    """Give the period and fiscal_year of a ticker if exists"""
    candidates = period_ends()[ticker]
    kept = []
    for period, year in candidates: 
        if (period_end is None or period == period_end) and (fiscal_year is None or fiscal_year == year) : 
            kept.append((period,year))
    if len(kept) == 0 :
        available = ", ".join(f"fiscal {y} (ended {p})" for p, y in candidates)
        raise ValueError(f"{ticker}: no fiscal year matches period_end={period_end}, "
                         f"fiscal_year={fiscal_year}. Available: {available}.")
    else : 
        return kept[-1]


def _value(company: str, label: str, period: str, year: int) -> tuple[float, str]:
    """The value and unit of a label for fiscal `year`, which ends at `period`.

    The label comes from CONCEPTS or RATIO_CONCEPTS. The first XBRL name that carries a value
    for this date wins: Apple reports revenue under the first name, Nvidia under the second.
    When none does, an optional label is 0 and any other raises ValueError.
    Shared by get_fact and get_ratio, so both tools read a figure the same way.
    """
    if label in CONCEPTS:
        xbrl_names, optional = CONCEPTS[label], False
    else:
        xbrl_names, optional = RATIO_CONCEPTS[label]["xbrl"], RATIO_CONCEPTS[label]["optional"]
    for xbrl_name in xbrl_names:
        values = annual_values(company, xbrl_name)
        if period in values:
            return values[period], unit(company, xbrl_name)
    if optional:
        return 0.0, "USD"
    raise ValueError(f"{names[company]} reports no {label} for fiscal {year} (ended {period}) "
                     f"in FinAgent's data.")


def _opening(company: str, period: str) -> str:
    """The end of the fiscal year before the one ending at `period`: its balance sheet is the
    opening one. Read from the company's total assets, reported at every year end, and checked
    to be one fiscal year earlier (52 or 53 weeks)."""
    earlier = [end for end in annual_values(company, "Assets") if end < period]
    if not earlier or not MIN_DAYS <= _days(earlier[-1], period) <= MAX_DAYS:
        raise ValueError(f"{names[company]}: no balance sheet one year before {period} "
                         f"in FinAgent's data.")
    return earlier[-1]


def _component(company: str, label, period: str, year: int) -> float:
    """One input of a ratio: the value at `period`, or for avg(label) the mean of the opening
    and closing balance sheets."""
    if isinstance(label, tuple):
        _, name = label
        opening = _opening(company, period)
        return (_value(company, name, period, year)[0] + _value(company, name, opening, year - 1)[0]) / 2
    return _value(company, label, period, year)[0]


def get_fact(company: str, concept: str, period_end: str = None, fiscal_year: int = None) -> dict :
    """Run the tool: the figure the model asked for, as {"content": str, "is_error": bool}.

    Never raises. An unknown period or a concept with no value comes back as an error
    result whose text says what exists, so the model can fix its arguments.
    """
    try :
        period, year = _resolve_period(company, period_end, fiscal_year)
        value, unite = _value(company, concept, period, year)
    except ValueError as error :
        return {"content" : str(error) , "is_error" : True}
    # No period in the question: say the figure is the latest we have, not the latest filed
    latest = " (latest in FinAgent's data)" if period_end is None and fiscal_year is None else ""
    return {"content" : f"{names[company]}, {concept}, fiscal {year} (ended {period}){latest}: "
                        f"{value} {unite}",
            "is_error" : False}


def _name(label) -> str:
    """How a ratio input is written in the result: "average total assets" for avg(...)."""
    return f"average {label[1]}" if isinstance(label, tuple) else label


def get_ratio(company: str, ratio: str, period_end: str = None, fiscal_year: int = None) -> dict:
    """Run the ratio tool: the ratio computed in Python from its XBRL components.

    Same period rules and same result shape as get_fact. The components come back with the
    ratio, so the model can say where the figure comes from. Never raises.
    """
    spec = RATIOS[ratio]
    try:
        period, year = _resolve_period(company, period_end, fiscal_year)
        # One _value per label, in the order of the formula's arguments
        components = [_component(company, label, period, year) for label in spec["labels"]]
        value = spec["formula"](*components)
    except ValueError as error:
        return {"content": f"{names[company]}, {ratio}: {error}",
                "is_error": True}

    latest = " (latest in FinAgent's data)" if period_end is None and fiscal_year is None else ""
    parts = ", ".join(f"{_name(label)} {v:.0f}" for label, v in zip(spec["labels"], components))
    note = f" Note: {NOTES[(company, ratio)]}" if (company, ratio) in NOTES else ""
    return {"content": f"{names[company]}, {ratio}, fiscal {year} (ended {period}){latest}: "
                       f"{value:.4f} ({value:.1%}). Components in USD: {parts}.{note}",
            "is_error": False}
