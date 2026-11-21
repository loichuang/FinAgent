import pytest

import finagent.tools as tools
from finagent.questions import CONCEPTS, names, period_ends
from finagent.tools import TOOL, _resolve_period, get_fact


# Nvidia names its fiscal years after the January in which they end
NVDA = [("2024-01-28", 2024), ("2025-01-26", 2025), ("2026-01-25", 2026)]


# --- _resolve_period: the four cases of the period ---

def test_fiscal_year_alone_gives_its_date():
    assert _resolve_period("NVDA", None, 2025) == ("2025-01-26", 2025)


def test_date_alone_gives_its_fiscal_year():
    assert _resolve_period("AAPL", "2024-09-28", None) == ("2024-09-28", 2024)


def test_date_and_fiscal_year_that_agree():
    assert _resolve_period("NVDA", "2025-01-26", 2025) == ("2025-01-26", 2025)


def test_no_period_gives_the_latest_fiscal_year():
    assert _resolve_period("NVDA", None, None) == NVDA[-1]


def test_date_and_fiscal_year_that_disagree_raise():
    with pytest.raises(ValueError, match="no fiscal year matches"):
        _resolve_period("NVDA", "2025-01-26", 2024)


def test_unknown_fiscal_year_raises_and_lists_what_exists():
    with pytest.raises(ValueError) as error:
        _resolve_period("NVDA", None, 2022)
    message = str(error.value)
    assert message.startswith("NVDA")
    for period_end, fiscal_year in NVDA:
        assert f"fiscal {fiscal_year} (ended {period_end})" in message


# --- get_fact: what the model reads back ---

def test_figure_comes_back_with_its_period_and_unit():
    result = get_fact("NVDA", "revenue", fiscal_year=2025)
    assert result["is_error"] is False
    assert result["content"] == "Nvidia, revenue, fiscal 2025 (ended 2025-01-26): 130497000000 USD"


def test_alias_is_resolved_per_company():
    # Same label, two XBRL names: Apple uses RevenueFromContract..., Nvidia uses Revenues
    apple = get_fact("AAPL", "revenue", fiscal_year=2025)
    nvidia = get_fact("NVDA", "revenue", fiscal_year=2025)
    assert "416161000000 USD" in apple["content"]
    assert "130497000000 USD" in nvidia["content"]


def test_no_period_is_flagged_as_latest():
    assert "latest in FinAgent's data" in get_fact("AAPL", "revenue")["content"]
    assert "latest" not in get_fact("AAPL", "revenue", fiscal_year=2025)["content"]


def test_per_share_unit():
    result = get_fact("MSFT", "diluted earnings per share", period_end="2025-06-30")
    assert result["content"].endswith("13.64 USD/shares")


def test_unknown_period_is_an_error_result_not_an_exception():
    result = get_fact("NVDA", "revenue", fiscal_year=2022)
    assert result["is_error"] is True
    assert "Available:" in result["content"]


def test_concept_without_value_is_an_error_result(monkeypatch):
    # No company in the corpus lacks a label for a year, so the data is emptied
    monkeypatch.setattr(tools, "annual_values", lambda ticker, concept: {})
    result = get_fact("NVDA", "revenue", fiscal_year=2025)
    assert result == {"content": "Nvidia reports no revenue for fiscal 2025 (ended 2025-01-26) "
                                 "in FinAgent's data.",
                      "is_error": True}


def test_missing_optional_keys_are_accepted():
    # The model leaves out the keys it does not fill: get_fact(**input) must still work
    assert get_fact(**{"company": "AAPL", "concept": "net income"})["is_error"] is False


# --- The tool card and the code share the same values ---

def test_tool_card_lists_every_company_and_label():
    properties = TOOL["input_schema"]["properties"]
    assert set(properties["company"]["enum"]) == set(names)
    assert properties["concept"]["enum"] == list(CONCEPTS)


def test_every_label_has_a_value_for_every_company_and_year():
    # What the benchmark asks, the tool can answer
    for ticker, pairs in period_ends().items():
        for _, fiscal_year in pairs:
            for label in CONCEPTS:
                result = get_fact(ticker, label, fiscal_year=fiscal_year)
                assert result["is_error"] is False, result["content"]
