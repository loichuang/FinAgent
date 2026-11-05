from finagent.xbrl import annual_values, unit


def test_value_keyed_by_period_end_not_filing_year():
    # Apple's fiscal 2023 revenue is tagged fy 2025 in the file: the period end must win
    revenue = annual_values("AAPL", "RevenueFromContractWithCustomerExcludingAssessedTax")
    assert revenue["2023-09-30"] == 383_285_000_000
    assert revenue["2024-09-28"] == 391_035_000_000


def test_quarters_are_dropped():
    # Every kept flow covers a full year, so no two period ends are less than ~350 days apart
    ends = sorted(annual_values("AAPL", "NetIncomeLoss"))
    assert len(ends) == len(set(ends))
    assert "2018-03-31" not in annual_values("AAPL", "Revenues")


def test_instant_and_per_share_values():
    assert annual_values("NVDA", "Assets")["2025-01-26"] == 111_601_000_000
    assert annual_values("MSFT", "EarningsPerShareDiluted")["2025-06-30"] == 13.64
    assert unit("MSFT", "EarningsPerShareDiluted") == "USD/shares"


def test_unreported_concept_is_empty():
    assert annual_values("NVDA", "NotAConcept") == {}
