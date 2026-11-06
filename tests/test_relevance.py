from finagent.relevance import answer_strings, contains_number, is_relevant, relevant_ids


def question(value, unit="USD", ticker="AAPL", fiscal_year=2024):
    return {"ticker": ticker, "fiscal_year": fiscal_year, "value": value, "unit": unit}


def test_answer_strings_tries_each_scale():
    assert answer_strings(question(391035000000)) == ["391,035", "391,035,000", "391,035,000,000"]
    # Not a whole number of millions: only thousands and units remain
    assert answer_strings(question(15408095000, unit="shares")) == ["15,408,095", "15,408,095,000"]
    assert answer_strings(question(6.08, unit="USD/shares")) == ["6.08"]
    # A negative amount is written in brackets, so its sign is dropped
    assert answer_strings(question(-259000000)) == ["259", "259,000", "259,000,000"]


def test_contains_number_ignores_longer_numbers():
    assert contains_number("Total net sales $ 391,035 $ 383,285", "391,035")
    assert contains_number("Other income (259) net", "259")
    assert contains_number("Diluted earnings per share $ 6.08.", "6.08")
    assert not contains_number("Long-term debt 111,870", "11,870")
    assert not contains_number("Shares 11,870,000", "11,870")
    assert not contains_number("Up 16.08 percent", "6.08")
    assert not contains_number("A ratio of 6.085", "6.08")


def test_relevance_needs_the_right_report():
    q = question(391035000000)
    passages = [
        {"id": "AAPL_2024_8_3", "ticker": "AAPL", "fiscal_year": 2024, "text": "Total net sales 391,035"},
        {"id": "AAPL_2024_7_2", "ticker": "AAPL", "fiscal_year": 2024, "text": "Net sales grew 2%."},
        # Right number, wrong year or wrong company: not relevant
        {"id": "AAPL_2025_8_3", "ticker": "AAPL", "fiscal_year": 2025, "text": "Prior year 391,035"},
        {"id": "MSFT_2024_8_3", "ticker": "MSFT", "fiscal_year": 2024, "text": "Revenue 391,035"},
    ]
    assert is_relevant(q, passages[0])
    assert not is_relevant(q, passages[2])
    assert relevant_ids(q, passages) == {"AAPL_2024_8_3"}
    assert relevant_ids(question(1), passages) == set()
