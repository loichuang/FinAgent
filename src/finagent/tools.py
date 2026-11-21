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
    # Amazon 2025 tags nothing: "no repurchases of our common stock in 2023, 2024, or 2025"
    "share repurchases": {"xbrl": ["PaymentsForRepurchaseOfCommonStock"], "optional": True},
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


# --- Profitability: return on the capital, with balance sheets averaged over the year ---

def _tax_rate(net_income: float, tax: float) -> float:
    """Effective tax rate: income tax over pre-tax income, rebuilt as net income + tax so that
    no second XBRL name of pre-tax income is needed."""
    return tax / (net_income + tax)


def _roic(ebit, tax, net_income, equity, long_term_debt, commercial_paper, short_term_borrowings,
          cash, securities) -> float:
    """Return on invested capital: what the business alone earns on the capital it ties up.

    NOPAT = EBIT (1 - effective tax rate): operating profit after tax, without interest.
    Invested capital = equity + financial debt - cash and current securities: the money the
    shareholders and the lenders put in, minus the part that sits idle. Every balance sheet
    input arrives already averaged over the year.
    """
    nopat = ebit * (1 - _tax_rate(net_income, tax))
    invested_capital = (equity + long_term_debt + commercial_paper + short_term_borrowings
                        - cash - securities)
    if invested_capital <= 0:
        raise ValueError(f"invested capital is {invested_capital:.0f} USD, not positive: ROIC is "
                         f"not meaningful.")
    return nopat / invested_capital


def _du_pont(net_income, revenue, assets, equity) -> tuple[float, str]:
    """ROE split into three factors: margin x turnover x leverage. The product is the ROE, so
    the split shows where a high ROE comes from: the business (margin, turnover) or the debt
    (leverage)."""
    margin, turnover, leverage = net_income / revenue, revenue / assets, assets / equity
    return (margin * turnover * leverage,
            f"net margin {margin:.4f} x asset turnover {turnover:.4f} x equity multiplier "
            f"{leverage:.4f}")


# --- Working capital cycle, in days of revenue or of cost of revenue, year-end balances ---

def _days_of(balance: float, flow: float) -> float:
    """How many days of the yearly flow the balance sheet item stands for."""
    return balance / flow * 365


def _ccc(receivables, revenue, inventory, payables, cost_of_revenue) -> tuple[float, str]:
    """Cash conversion cycle: days between paying suppliers and being paid by customers.
    DSO + DIO - DPO; a negative cycle means suppliers finance the business."""
    dso = _days_of(receivables, revenue)
    dio = _days_of(inventory, cost_of_revenue)
    dpo = _days_of(payables, cost_of_revenue)
    return dso + dio - dpo, f"DSO {dso:.1f} + DIO {dio:.1f} - DPO {dpo:.1f}"


# --- Financing ---

def _debt_to_equity(long_term_debt, commercial_paper, short_term_borrowings, equity) -> float:
    """Financial debt over equity, at year end: how much of the business the lenders fund
    next to the shareholders. Same debt as in ROIC; leases are not counted."""
    return (long_term_debt + commercial_paper + short_term_borrowings) / equity


def _payout(dividends, buybacks, net_income) -> float:
    """Share of net income handed back to shareholders as dividends and buybacks. Above 1,
    the company returns more than it earns. Meaningless on a loss, so refused."""
    if net_income <= 0:
        raise ValueError(f"net income is {net_income:.0f} USD, not positive: the payout ratio "
                         f"is not meaningful.")
    return (dividends + buybacks) / net_income


# Ratio name -> the labels it needs, in the order of the formula's arguments, and optionally
# the definition the result announces and its unit ("ratio" when not given). A formula
# returns the ratio, or (ratio, detail).
# Python computes every ratio: the model never does arithmetic.
CFO, CAPEX = "net cash provided by operating activities", "capital expenditures"
NI, EQUITY, ASSETS = "net income", "total stockholders' equity", "total assets"
RATIOS = {
    "gross margin": {"labels": ["revenue", "cost of revenue"],
                     "formula": lambda rev, cogs: (rev - cogs) / rev},
    "operating margin": {"labels": ["operating income", "revenue"],
                         "formula": lambda ebit, rev: ebit / rev},
    "fcf margin": {"labels": [CFO, CAPEX, "revenue"],
                   "formula": lambda cfo, capex, rev: (cfo - capex) / rev},
    "sbc to fcf": {"labels": ["share-based compensation", CFO, CAPEX],
                   "formula": _sbc_to_fcf},
    "roe": {"labels": [NI, avg(EQUITY)],
            "formula": lambda ni, equity: ni / equity,
            "definition": "net income / average equity"},
    "roic": {"labels": ["operating income", "income tax expense", NI, avg(EQUITY),
                        avg("long-term debt including current portion"), avg("commercial paper"),
                        avg("short-term borrowings"), avg("cash and cash equivalents"),
                        avg("current marketable securities")],
             "formula": _roic,
             "definition": "EBIT x (1 - tax / (net income + tax)) / average (equity + financial "
                           "debt - cash and current marketable securities); leases are not "
                           "counted as debt, non-current securities are not counted as cash"},
    "du pont": {"labels": [NI, "revenue", avg(ASSETS), avg(EQUITY)],
                "formula": _du_pont,
                "definition": "ROE = net income / revenue x revenue / average assets x average "
                              "assets / average equity"},
    "dso": {"labels": ["accounts receivable", "revenue"], "formula": _days_of, "unit": "days",
            "definition": "year-end accounts receivable / revenue x 365"},
    "dio": {"labels": ["inventory", "cost of revenue"], "formula": _days_of, "unit": "days",
            "definition": "year-end inventory / cost of revenue x 365"},
    "dpo": {"labels": ["accounts payable", "cost of revenue"], "formula": _days_of,
            "unit": "days", "definition": "year-end accounts payable / cost of revenue x 365"},
    "ccc": {"labels": ["accounts receivable", "revenue", "inventory", "accounts payable",
                       "cost of revenue"],
            "formula": _ccc, "unit": "days", "definition": "DSO + DIO - DPO"},
    "debt to equity": {"labels": ["long-term debt including current portion", "commercial paper",
                                  "short-term borrowings", EQUITY],
                       "formula": _debt_to_equity,
                       "definition": "year-end financial debt (long-term debt including its "
                                     "current portion, commercial paper, short-term borrowings) / "
                                     "year-end equity; leases are not counted as debt"},
    "payout ratio": {"labels": ["dividends paid", "share repurchases", NI],
                     "formula": _payout,
                     "definition": "(dividends paid + share repurchases) / net income"},
    "effective tax rate": {"labels": [NI, "income tax expense"],
                           "formula": lambda ni, tax: _tax_rate(ni, tax),
                           "definition": "income tax / (net income + income tax)"},
}

# Each ratio in words, for the tool card: the model maps the wording of a question to a name
ABOUT = {
    "gross margin": "gross profit as a share of revenue",
    "operating margin": "operating income as a share of revenue",
    "fcf margin": "free cash flow as a share of revenue",
    "sbc to fcf": "stock-based compensation as a share of free cash flow",
    "roe": "return on equity",
    "roic": "return on invested capital",
    "du pont": "return on equity split into net margin, asset turnover and equity multiplier",
    "dso": "days sales outstanding: how long customers take to pay",
    "dio": "days inventory outstanding: how long inventory sits before it is sold",
    "dpo": "days payables outstanding: how long the company takes to pay its suppliers",
    "ccc": "cash conversion cycle, DSO + DIO - DPO",
    "debt to equity": "financial debt over shareholders' equity",
    "payout ratio": "share of net income returned through dividends and share buybacks",
    "effective tax rate": "income tax as a share of pre-tax income",
}

# Caveats the model must pass on with the figure: the ratio is computed right, but read alone
# it would lead to a wrong conclusion. Each one checked against the 10-K text.
_NVDA_CAPEX = ("Nvidia's capital expenditures include intangible assets (its 10-K line is "
               "\"purchases related to property and equipment and intangible assets\"), so its "
               "free cash flow is computed on a wider base than the other companies'.")
_AMZN_COGS = ("Amazon books fulfillment outside cost of revenue, so days computed on its cost "
              "of revenue are not comparable with the other companies'.")
_AMZN_FCF = ("Free cash flow here is operating cash flow minus gross purchases of property and "
             "equipment. Amazon's own free cash flow subtracts them net of proceeds from sales "
             "and incentives, so it differs from the figure Amazon publishes.")
NOTES = {
    ("AMZN", "gross margin"): "Amazon books fulfillment outside cost of revenue, so its gross "
                              "margin is not comparable with the other companies'.",
    ("AMZN", "dio"): _AMZN_COGS,
    ("AMZN", "dpo"): _AMZN_COGS,
    ("AMZN", "ccc"): _AMZN_COGS,
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
        "its annual report (10-K). The ratios available are listed in `ratio`. Call it "
        "whenever the question asks for one of them, instead of fetching the figures with "
        "get_fact and computing the ratio yourself: never do the arithmetic. The result gives "
        "the ratio, its definition, the figures it was computed from and any caveat; pass the "
        "caveat on. Ratios come as decimals (0.4663 for 46.6 %), cycle ratios in days. Fill "
        "the period exactly as for get_fact: period_end when the question gives a date, "
        "fiscal_year when it gives a fiscal year, neither when it gives none."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "company": FACT_TOOL["input_schema"]["properties"]["company"],
            "ratio": {
                "type": "string",
                "enum": list(RATIOS),
                "description": "The ratio asked for: "
                               + "; ".join(f"{name} ({ABOUT[name]})" for name in RATIOS) + ".",
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
        result = spec["formula"](*components)
    except ValueError as error:
        return {"content": f"{names[company]}, {ratio}: {error}",
                "is_error": True}

    latest = " (latest in FinAgent's data)" if period_end is None and fiscal_year is None else ""
    parts = ", ".join(f"{_name(label)} {v:.0f}" for label, v in zip(spec["labels"], components))
    note = f" Note: {NOTES[(company, ratio)]}" if (company, ratio) in NOTES else ""
    # A formula may return the ratio alone, or the ratio and a detail (the Du Pont factors)
    value, detail = result if isinstance(result, tuple) else (result, None)
    detail = f" = {detail}" if detail else ""
    definition = f" Definition: {spec['definition']}." if "definition" in spec else ""
    shown = f"{value:.1f} days" if spec.get("unit") == "days" else f"{value:.4f} ({value:.1%})"
    return {"content": f"{names[company]}, {ratio}, fiscal {year} (ended {period}){latest}: "
                       f"{shown}{detail}. Components in USD: {parts}."
                       f"{definition}{note}",
            "is_error": False}
