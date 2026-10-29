import pytest

from finagent.items import split_items

TEXT = """[TABLE]
Item 1. | Business | 1
Item 1A. | Risk Factors | 5
Item 7. | Management's Discussion and Analysis | 21
Item 7A. | Market Risk | 27
Item 8. | Financial Statements | 28
[/TABLE]

Item 1. Business
Apple designs smartphones.

ITEM 1A. RISK FACTORS
Supply chains may fail.

Item 7. Management's Discussion and Analysis
Net sales grew, see Part I, Item 1A. of this Form 10-K.

Item 7A. Quantitative and Qualitative Disclosures About Market Risk
Interest rates may rise.

Item 8. Financial Statements and Supplementary Data
Total net sales | 391,035

Item 9. Changes in and Disagreements with Accountants
None."""


def test_split_items():
    items = split_items(TEXT)
    assert list(items) == ["1", "1A", "7", "8"]
    assert items["1"] == "Item 1. Business\nApple designs smartphones."
    assert items["1A"].endswith("Supply chains may fail.")
    assert "Net sales grew" in items["7"]
    assert "Interest rates" not in items["7"]  # Item 7 stops where 7A starts
    assert "None." not in items["8"]


def test_missing_item_raises():
    with pytest.raises(ValueError, match="not found"):
        split_items("Item 1. Business\nText.")


def test_repeated_heading_raises():
    # a table of contents written as plain lines repeats every heading
    text = "Item 1. Business\nItem 1A. Risk Factors\n" + TEXT
    with pytest.raises(ValueError, match="two headings"):
        split_items(text)
