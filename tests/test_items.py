import pytest

from finagent.items import split_items

TEXT = """[TABLE]
Item 1. | Business | 1
Item 1A. | Risk Factors | 5
Item 7. | Management's Discussion and Analysis | 21
Item 7A. | Market Risk | 27
Item 8. | Financial Statements | 28
[/TABLE]

Item 1. | Business
Apple designs smartphones.

ITEM 1A. RISK FACTORS
Supply chains may fail.

Item 7. Management's Discussion and Analysis
Net sales grew, see Part I, Item 1A. of this Form 10-K.

Item 7A. Quantitative and Qualitative Disclosures About Market Risk
Interest rates may rise.

Item 8. Financial Statements and Supplementary Data
CONSOLIDATED BALANCE SHEETS
Total assets | 364,980
The consolidated balance sheets were audited.

Item 9. Changes in and Disagreements with Accountants
None."""


def test_split_items():
    items = split_items(TEXT)
    assert list(items) == ["1", "1A", "7", "8"]
    assert items["1"] == "Item 1. | Business\nApple designs smartphones."  # heading in a table row
    assert items["1A"].endswith("Supply chains may fail.")
    assert "Net sales grew" in items["7"]
    assert "Interest rates" not in items["7"]  # Item 7 stops where 7A starts
    assert "Total assets | 364,980" in items["8"]
    assert "None." not in items["8"]


def test_statements_printed_in_another_item():
    # Nvidia: Item 8 only refers to the statements, which sit in Item 15
    text = TEXT.replace(
        "CONSOLIDATED BALANCE SHEETS\nTotal assets | 364,980\nThe consolidated balance sheets were audited.",
        "The information required by this Item is set forth in our Consolidated Financial Statements.",
    ) + """

Item 15. Exhibits and Financial Statement Schedules
Consolidated Balance Sheets
Total assets | 111,601

Exhibit Index
10.1 | Credit Agreement

Item 16. Form 10-K Summary
None."""
    items = split_items(text)
    assert items["8"].startswith("Item 15.")
    assert "Total assets | 111,601" in items["8"]
    assert "Credit Agreement" not in items["8"]  # cut at the exhibit index


def test_missing_item_raises():
    with pytest.raises(ValueError, match="not found"):
        split_items("Item 1. Business\nText.")


def test_repeated_heading_raises():
    # a table of contents written as plain lines repeats every heading
    text = "Item 1. Business\nItem 1A. Risk Factors\n" + TEXT
    with pytest.raises(ValueError, match="two headings"):
        split_items(text)


def test_heading_without_expected_name_raises():
    text = TEXT.replace("ITEM 1A. RISK FACTORS", "ITEM 1A. SEE ABOVE")
    with pytest.raises(ValueError, match="risk factors"):
        split_items(text)


def test_missing_balance_sheet_raises():
    text = TEXT.replace("CONSOLIDATED BALANCE SHEETS\n", "")
    with pytest.raises(ValueError, match="0 balance sheet"):
        split_items(text)
