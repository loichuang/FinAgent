import pytest

from finagent.pipeline import (header_of, previous_id, starts_inside_table, table_header,
                               with_table_header)


@pytest.mark.parametrize("text, inside", [
    ("a | 1\n[/TABLE]\nb", True),                                 # end of a table, then text
    ("a | 1\n[/TABLE]\ntitle\n[TABLE]\nx | 2", True),             # end of one, start of another
    ("intro\n[TABLE]\nx | 1\n[/TABLE]", False),                   # a whole table
    ("plain text", False),                                       # no table
    ("a | 1\nb | 2", True),                                       # a table through the passage
])
def test_starts_inside_table(text, inside):
    assert starts_inside_table(text) is inside


def test_header_of_takes_title_scale_and_columns():
    text = ("Notes.\nCONSOLIDATED BALANCE SHEETS\n(in millions)\n[TABLE]\n"
            "As of December 31,\n | 2023 | 2024\nTotal assets | 402,392 | 450,256")
    assert header_of(text) == ("CONSOLIDATED BALANCE SHEETS\n(in millions)\n"
                               "As of December 31,\n | 2023 | 2024")


def test_header_of_scale_after_the_tag():
    # Microsoft writes the scale inside the table
    text = "CASH FLOWS STATEMENTS\n[TABLE]\n(In millions)\nYear Ended June 30, | 2024 | 2023\nx | 1 | 2"
    assert header_of(text) == "CASH FLOWS STATEMENTS\n(In millions)\nYear Ended June 30, | 2024 | 2023"


def test_header_of_ignores_the_previous_table():
    text = "x | 1\n[/TABLE]\n[TABLE]\nYear 2025\n | A | B"
    assert header_of(text) == "Year 2025\n | A | B"


def test_header_of_without_table():
    assert header_of("plain text") == ""


def test_previous_id():
    assert previous_id("GOOGL_2024_8_7") == "GOOGL_2024_8_6"
    assert previous_id("AAPL_2023_1A_12") == "AAPL_2023_1A_11"


by_id = {p["id"]: p for p in [
    {"id": "X_2024_8_1", "text": "BALANCE SHEETS\n(in millions)\n[TABLE]\n | 2023 | 2024\na | 1 | 2"},
    {"id": "X_2024_8_2", "text": "b | 3 | 4\nc | 5 | 6"},                  # no tag: long table
    {"id": "X_2024_8_3", "text": "d | 7 | 8\n[/TABLE]\nText after."},
    {"id": "X_2024_8_4", "text": "Plain text only."},
    {"id": "X_2024_1_1", "text": "e | 9\n[/TABLE]"},                       # first of its Item
]}
HEADER = "BALANCE SHEETS\n(in millions)\n | 2023 | 2024"


@pytest.mark.parametrize("pid, header", [
    ("X_2024_8_2", HEADER),   # one passage back
    ("X_2024_8_3", HEADER),   # two passages back, through a passage without tag
    ("X_2024_8_1", ""),       # opens its own table
    ("X_2024_8_4", ""),       # outside any table
    ("X_2024_1_1", ""),       # no passage before it
])
def test_table_header(pid, header):
    assert table_header(by_id[pid], by_id) == header


def test_with_table_header_copies_the_passage():
    passage = by_id["X_2024_8_3"]
    result = with_table_header(passage, by_id)
    assert result["text"] == HEADER + "\n" + passage["text"]
    assert result["id"] == passage["id"]
    assert passage["text"].startswith("d | 7")  # the corpus is not modified


def test_with_table_header_leaves_other_passages_alone():
    passage = by_id["X_2024_8_4"]
    assert with_table_header(passage, by_id) is passage
