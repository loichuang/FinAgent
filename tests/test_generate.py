"""Step 7 without any API call: generate() is replaced by a fake that returns a chosen reply."""

import pytest

from finagent import generate as g

PASSAGES = [
    {"id": "AAPL_2023_8_1", "text": "(In millions) | September 30, 2023 | September 24, 2022 | "
                                    "Total net sales | 383,285 | 394,328 | 365,817"},
    {"id": "AAPL_2023_1_1", "text": "Item 1. Business. The Company designs smartphones."},
]
QUESTION = {"question": "What was Apple's revenue for the fiscal year ended September 30, 2023?"}


def reply(found=True, value="383,285", scale="millions", passage_id="AAPL_2023_8_1"):
    return {"found": found, "value": value, "scale": scale, "passage_id": passage_id,
            "_usage": {"cached": False}}


def fake_llm(monkeypatch, r):
    sent = {}
    def fake_generate(system, user, schema):
        sent.update(system=system, user=user, schema=schema)
        return r
    monkeypatch.setattr(g, "generate", fake_generate)
    return sent


def test_schema_has_the_four_required_fields():
    assert set(g.ANSWER_SCHEMA["properties"]) == set(g.ANSWER_SCHEMA["required"]) == \
        {"found", "value", "scale", "passage_id"}
    assert g.ANSWER_SCHEMA["properties"]["scale"]["enum"] == ["units", "thousands", "millions", "billions"]


def test_build_user_tags_every_passage_and_ends_with_the_question():
    user = g.build_user("Q?", PASSAGES)
    assert '<passage id="AAPL_2023_8_1">' in user and '<passage id="AAPL_2023_1_1">' in user
    assert user.endswith("Question: Q?")


@pytest.mark.parametrize("value, scale, expected", [
    ("383,285", "millions", 383_285_000_000),
    ("$383,285", "millions", 383_285_000_000),
    ("(1,234)", "thousands", -1_234_000),
    ("$(11,683)", "millions", -11_683_000_000),
    ("$ 0.00001", "units", 0.00001),
    ("6.13", "units", 6.13),
])
def test_to_number(value, scale, expected):
    assert g.to_number(value, scale) == pytest.approx(expected)


def test_a_right_answer_passes_and_is_converted(monkeypatch):
    fake_llm(monkeypatch, reply())
    result = g.answer(QUESTION, PASSAGES)
    assert result["problems"] == [] and result["number"] == 383_285_000_000


def test_an_invented_passage_is_caught(monkeypatch):
    fake_llm(monkeypatch, reply(passage_id="AAPL_2023_8_99"))
    result = g.answer(QUESTION, PASSAGES)
    assert result["problems"] == ["cited passage not among those given"] and result["number"] is None


def test_an_invented_number_is_caught(monkeypatch):
    fake_llm(monkeypatch, reply(value="391,035"))
    assert g.answer(QUESTION, PASSAGES)["problems"] == ["cited value not in the cited passage"]


def test_the_wrong_column_is_not_caught_here(monkeypatch):
    """394,328 is the 2022 column of the right table: only XBRL (step 8) can tell."""
    fake_llm(monkeypatch, reply(value="394,328"))
    result = g.answer(QUESTION, PASSAGES)
    assert result["problems"] == [] and result["number"] == 394_328_000_000


def test_an_abstention_has_no_number_and_no_problem(monkeypatch):
    fake_llm(monkeypatch, reply(found=False, value="", scale="units", passage_id=""))
    result = g.answer(QUESTION, PASSAGES)
    assert result["found"] is False and result["number"] is None and result["problems"] == []


def test_the_question_and_schema_reach_the_model(monkeypatch):
    sent = fake_llm(monkeypatch, reply())
    g.answer(QUESTION, PASSAGES)
    assert sent["user"].endswith(QUESTION["question"]) and sent["schema"] is g.ANSWER_SCHEMA
