import pytest

import finagent.tools as tools
from finagent.questions import CONCEPTS, names, period_ends
from finagent.tools import (FACT_TOOL, NOTES, RATIO_CONCEPTS, RATIO_TOOL, RATIOS, _component,
                            _opening, _resolve_period, _value, avg, get_fact, get_ratio)


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
    properties = FACT_TOOL["input_schema"]["properties"]
    assert set(properties["company"]["enum"]) == set(names)
    assert properties["concept"]["enum"] == list(CONCEPTS)


def test_every_label_has_a_value_for_every_company_and_year():
    # What the benchmark asks, the tool can answer
    for ticker, pairs in period_ends().items():
        for _, fiscal_year in pairs:
            for label in CONCEPTS:
                result = get_fact(ticker, label, fiscal_year=fiscal_year)
                assert result["is_error"] is False, result["content"]


# --- get_ratio: computed in Python from its components ---


def test_gross_margin_of_nvidia():
    # (130497 - 32639) / 130497: the labels must reach the formula in its argument order
    result = get_ratio("NVDA", "gross margin", fiscal_year=2025)
    assert result["is_error"] is False
    assert result["content"].startswith("Nvidia, gross margin, fiscal 2025 (ended 2025-01-26): "
                                         "0.7499 (75.0%).")
    assert "revenue 130497000000, cost of revenue 32639000000" in result["content"]


def test_fcf_margin_and_sbc_to_fcf_of_nvidia():
    fcf = 64089000000 - 3236000000
    assert f"{fcf / 130497000000:.4f}" in get_ratio("NVDA", "fcf margin", fiscal_year=2025)["content"]
    assert f"{4737000000 / fcf:.4f}" in get_ratio("NVDA", "sbc to fcf", fiscal_year=2025)["content"]


def test_operating_margin_of_alphabet():
    assert "0.3203 (32.0%)" in get_ratio("GOOGL", "operating margin", fiscal_year=2025)["content"]


def test_ratio_without_period_is_flagged_as_latest():
    assert "latest in FinAgent's data" in get_ratio("AAPL", "gross margin")["content"]


def test_note_comes_with_the_ratio():
    assert NOTES[("AMZN", "gross margin")] in get_ratio("AMZN", "gross margin", fiscal_year=2025)["content"]
    assert "Note:" not in get_ratio("GOOGL", "gross margin", fiscal_year=2025)["content"]


def test_unknown_period_is_an_error_result():
    result = get_ratio("NVDA", "fcf margin", fiscal_year=2022)
    assert result["is_error"] is True
    assert "Available:" in result["content"]


def test_missing_component_is_an_error_result(monkeypatch):
    monkeypatch.setattr(tools, "annual_values", lambda ticker, concept: {})
    result = get_ratio("NVDA", "gross margin", fiscal_year=2025)
    assert result["is_error"] is True
    assert "reports no revenue" in result["content"]


def test_sbc_to_fcf_refuses_a_negative_free_cash_flow():
    with pytest.raises(ValueError, match="not meaningful"):
        RATIOS["sbc to fcf"]["formula"](10, 5, 8)


# Ratios that must fail cleanly, never return a number, each checked in the 10-K.
# Nvidia 2026 reports 51,951 of current securities under a concept companyfacts leaves out.
# Alphabet holds no inventory: DIO and the cash conversion cycle do not apply to it.
KNOWN_GAPS = ({("NVDA", 2026, "roic")}
              | {("GOOGL", year, ratio) for year in (2023, 2024, 2025) for ratio in ("dio", "ccc")})


def test_every_ratio_works_for_every_company_and_year():
    for ticker, pairs in period_ends().items():
        for _, fiscal_year in pairs:
            for ratio in RATIOS:
                result = get_ratio(ticker, ratio, fiscal_year=fiscal_year)
                if (ticker, fiscal_year, ratio) in KNOWN_GAPS:
                    assert result["is_error"] is True, result["content"]
                else:
                    # A ratio to a negative free cash flow is the only accepted refusal
                    assert result["is_error"] is False or "not meaningful" in result["content"], \
                        result["content"]


def test_ratio_card_lists_every_ratio_and_shares_the_period_arguments():
    properties = RATIO_TOOL["input_schema"]["properties"]
    assert properties["ratio"]["enum"] == list(RATIOS)
    assert properties["fiscal_year"] == FACT_TOOL["input_schema"]["properties"]["fiscal_year"]


# --- Ratio plumbing: second concept table, absence rules, averages ---


def test_ratio_concepts_stay_out_of_the_benchmark():
    # A label in both tables would change the questions of the frozen benchmark
    assert not set(RATIO_CONCEPTS) & set(CONCEPTS)


def test_optional_label_absent_is_zero():
    # Microsoft 2026: no commercial paper outstanding; Amazon: no dividend
    assert _value("MSFT", "commercial paper", "2026-06-30", 2026) == (0.0, "USD")
    assert _value("AMZN", "dividends paid", "2025-12-31", 2025) == (0.0, "USD")
    # Amazon 2025: "no repurchases of our common stock in 2023, 2024, or 2025"
    assert _value("AMZN", "share repurchases", "2025-12-31", 2025) == (0.0, "USD")


def test_required_label_absent_is_an_error_never_zero():
    # Nvidia 2026 securities exist (51,951) but under a concept companyfacts leaves out
    with pytest.raises(ValueError, match="current marketable securities"):
        _value("NVDA", "current marketable securities", "2026-01-25", 2026)
    with pytest.raises(ValueError, match="inventory"):
        _value("GOOGL", "inventory", "2025-12-31", 2025)


def test_alias_in_ratio_concepts():
    # Microsoft reports its current securities as ShortTermInvestments
    assert _value("MSFT", "current marketable securities", "2025-06-30", 2025)[0] > 0


def test_opening_is_the_previous_fiscal_year_end():
    assert _opening("AAPL", "2025-09-27") == "2024-09-28"
    assert _opening("NVDA", "2024-01-28") == "2023-01-29"  # first year of the corpus


def test_average_is_the_mean_of_opening_and_closing():
    closing = _value("AAPL", "total stockholders' equity", "2025-09-27", 2025)[0]
    opening = _value("AAPL", "total stockholders' equity", "2024-09-28", 2024)[0]
    assert _component("AAPL", avg("total stockholders' equity"), "2025-09-27", 2025) == (closing + opening) / 2


# --- Profitability ---

def test_roic_of_apple_matches_the_hand_computation():
    # By hand: NOPAT 133.1 x (1 - 0.156) = 112.3, average invested capital (98.4 + 117.7) / 2
    # = 108.0, so about 104 %
    assert "1.0392 (103.9%)" in get_ratio("AAPL", "roic", fiscal_year=2025)["content"]


def test_roic_states_its_definition():
    assert "Definition: EBIT x (1 - tax" in get_ratio("AAPL", "roic", fiscal_year=2025)["content"]


def test_roe_is_net_income_over_average_equity():
    # 112,010 / ((73,733 + 56,950) / 2)
    assert "1.7142 (171.4%)" in get_ratio("AAPL", "roe", fiscal_year=2025)["content"]


def test_du_pont_factors_multiply_to_the_roe():
    for ticker in ("AAPL", "MSFT", "NVDA"):
        roe = get_ratio(ticker, "roe", fiscal_year=2025)["content"]
        du_pont = get_ratio(ticker, "du pont", fiscal_year=2025)["content"]
        # Same value, written the same way, and the three factors come with it
        assert roe.split(": ")[1].split(" ")[0] == du_pont.split(": ")[1].split(" ")[0]
        assert "net margin" in du_pont and "equity multiplier" in du_pont


def test_roic_of_nvidia_2026_fails_instead_of_returning_a_wrong_number():
    result = get_ratio("NVDA", "roic", fiscal_year=2026)
    assert result["is_error"] is True
    assert "current marketable securities" in result["content"]


def test_tax_rate_rebuilds_pre_tax_income():
    from finagent.tools import _tax_rate
    assert _tax_rate(80, 20) == 0.2


# --- Working capital cycle ---

def test_cycle_in_days_for_apple():
    # Receivables 39,777 / revenue 416,161 x 365; payables 69,860 / cost of revenue 220,960 x 365
    assert "34.9 days" in get_ratio("AAPL", "dso", fiscal_year=2025)["content"]
    assert "115.4 days" in get_ratio("AAPL", "dpo", fiscal_year=2025)["content"]


def test_ccc_is_dso_plus_dio_minus_dpo():
    content = get_ratio("AAPL", "ccc", fiscal_year=2025)["content"]
    # Negative: Apple's suppliers finance it
    assert "-71.1 days = DSO 34.9 + DIO 9.4 - DPO 115.4" in content


def test_alphabet_has_no_inventory_cycle():
    result = get_ratio("GOOGL", "dio", fiscal_year=2025)
    assert result["is_error"] is True and "no inventory" in result["content"]


def test_amazon_cycle_carries_its_cost_of_revenue_caveat():
    assert "fulfillment" in get_ratio("AMZN", "dpo", fiscal_year=2025)["content"]


def test_every_ratio_is_described_on_the_card():
    from finagent.tools import ABOUT
    assert set(ABOUT) == set(RATIOS)
    card = RATIO_TOOL["input_schema"]["properties"]["ratio"]["description"]
    assert all(name in card for name in RATIOS)


# --- Financing and tax ---

def test_debt_to_equity_of_apple_matches_the_hand_computation():
    # Commercial paper 7.98 + current debt 12.35 + non-current debt 78.33 = 98.7, over 73.7
    assert "1.3380 (133.8%)" in get_ratio("AAPL", "debt to equity", fiscal_year=2025)["content"]


def test_payout_counts_dividends_and_buybacks():
    # Apple: (15,421 + 90,711) / 112,010
    assert "0.9475 (94.8%)" in get_ratio("AAPL", "payout ratio", fiscal_year=2025)["content"]
    # Amazon pays no dividend and bought back nothing in 2025: a true 0, not an error
    amazon = get_ratio("AMZN", "payout ratio", fiscal_year=2025)
    assert amazon["is_error"] is False and "0.0000 (0.0%)" in amazon["content"]


def test_payout_on_a_loss_is_refused():
    with pytest.raises(ValueError, match="not meaningful"):
        RATIOS["payout ratio"]["formula"](10, 10, -5)


def test_effective_tax_rate_of_apple():
    # 20,719 / (112,010 + 20,719): the rate inside Apple's ROIC
    assert "0.1561 (15.6%)" in get_ratio("AAPL", "effective tax rate", fiscal_year=2025)["content"]
