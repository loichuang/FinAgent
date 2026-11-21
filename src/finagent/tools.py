"""The XBRL tool the model can call (phase 2, docs/phase2_design.md).

The model never reads XBRL. It reads TOOL, fills in its arguments, and the code runs the
lookup and sends the figure back.
"""

from finagent.questions import CONCEPTS, names, period_ends
from finagent.xbrl import annual_values, unit


# The tool card the model reads at every turn of the loop. The allowed values come from
# questions.py, so the tool and the benchmark always share the same companies and labels.
TOOL = {
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


def get_fact(company: str, concept: str, period_end: str = None, fiscal_year: int = None) -> dict :
    """Run the tool: the figure the model asked for, as {"content": str, "is_error": bool}.

    Never raises. An unknown period or a concept with no value comes back as an error
    result whose text says what exists, so the model can fix its arguments.
    """
    try : 
        period, year = _resolve_period(company, period_end, fiscal_year)
    except ValueError as nonexist : 
        return {"content" : str(nonexist) , "is_error" : True}
    # The first XBRL name that carries a value for this fiscal year: Apple reports revenue
    # under the first name, Nvidia under the second
    xbrl_name = None
    for c in CONCEPTS[concept] :
        if period in annual_values(company, c) :
            xbrl_name = c
            break
    if xbrl_name is None :
        return {"content" : f"{names[company]} reports no {concept} for fiscal {year} "
                            f"(ended {period}) in FinAgent's data.",
                "is_error" : True} 
    value = annual_values(company, xbrl_name)[period]
    unite = unit(company, xbrl_name)
    # No period in the question: say the figure is the latest we have, not the latest filed
    latest = " (latest in FinAgent's data)" if period_end is None and fiscal_year is None else ""
    return {"content" : f"{names[company]}, {concept}, fiscal {year} (ended {period}){latest}: "
                        f"{value} {unite}",
            "is_error" : False}