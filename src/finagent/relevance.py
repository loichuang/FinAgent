"""The answer key of the benchmark: which passages contain the answer to a question.

A question built from XBRL carries the exact value (383285000000 USD) but no passage.
A passage is relevant if it belongs to the right report (same company, same fiscal year)
and contains that value written as a 10-K writes it.

The scale of a 10-K table ("In millions") is stated once in its header, often in another
passage, so it is not read here. Every plausible scale is tried instead: a run of five or
six digits that matches by chance in the right report is rare.

This module only serves the evaluation. The search itself never sees the values.
"""

import re

# Scales a 10-K uses for amounts and share counts, from the most to the least common.
SCALES = (1_000_000, 1_000, 1)


def answer_strings(question: dict) -> list[str]:
    """The ways the value of a question can be written in a 10-K.

    Amounts and share counts: the value divided by each scale that leaves a whole number,
    with thousands separators ("383,285" for 383285000000 in millions). Per-share values:
    two decimals ("6.13"). The sign is dropped, since a 10-K writes negatives in brackets.
    """
    value = abs(question["value"])
    if question["unit"] == "USD/shares":
        return [f"{value:.2f}"]
    strings = []
    for scale in SCALES:
        if value % scale == 0:
            strings.append(f"{int(value // scale):,}")
    return strings


def contains_number(text: str, number: str) -> bool:
    """True if the number appears in the text as a whole number, not inside a longer one.

    "11,870" is not found in "111,870" nor in "11,870,000", "6.13" not in "16.13" nor in "6.135".
    """
    pattern = r"(?<![\d.,])" + re.escape(number) + r"(?![\d]|[.,]\d)"
    return re.search(pattern, text) is not None


def is_relevant(question: dict, passage: dict) -> bool:
    """True if the passage comes from the report the question is about and holds its value."""
    if passage["ticker"] != question["ticker"] or passage["fiscal_year"] != question["fiscal_year"]:
        return False
    return any(contains_number(passage["text"], s) for s in answer_strings(question))


def relevant_ids(question: dict, passages: list[dict]) -> set[str]:
    """The identifiers of every passage that answers the question. Empty if none does."""
    return {p["id"] for p in passages if is_relevant(question, p)}
