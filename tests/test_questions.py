from collections import defaultdict

from finagent.questions import CONCEPTS, TEMPLATES, _long_date, all_questions, assign_split, heldout_questions
from finagent.xbrl import annual_values


def _questions():
    questions = all_questions()
    assign_split(questions)
    return questions


def test_every_question_is_generated_once():
    questions = _questions()
    ids = [q["id"] for q in questions]
    assert len(ids) == len(set(ids))
    # 16 labels, 5 companies x 3 fiscal years, 3 phrasings
    assert len(questions) == len(CONCEPTS) * 15 * len(TEMPLATES)


def test_phrasings_of_a_fact_share_the_split():
    sides = defaultdict(set)
    for q in _questions():
        sides[(q["ticker"], q["period_end"], q["concept"])].add(q["split"])
    assert all(len(s) == 1 for s in sides.values())
    assert {next(iter(s)) for s in sides.values()} == {"tuning", "test"}


def test_split_is_reproducible():
    assert [q["split"] for q in _questions()] == [q["split"] for q in _questions()]


def test_fallback_concept_and_answer():
    # Nvidia reports revenue as Revenues, not RevenueFromContract...
    q = next(q for q in _questions()
             if q["ticker"] == "NVDA" and q["period_end"] == "2025-01-26"
             and q["question"].startswith("What was Nvidia's revenue "))
    assert q["concept"] == "Revenues"
    assert q["value"] == annual_values("NVDA", "Revenues")["2025-01-26"]
    assert q["fiscal_year"] == 2025


def test_long_date():
    assert _long_date("2025-01-26") == "January 26, 2025"
    assert _long_date("2024-06-05") == "June 5, 2024"


def test_heldout_phrasing_goes_to_test_only_once_per_fact():
    questions = _questions()
    extra = heldout_questions(questions, "{company} {label} {year} {date}")
    test_facts = {(q["ticker"], q["period_end"], q["concept"]) for q in questions if q["split"] == "test"}
    assert len(extra) == len(test_facts)
    assert all(q["split"] == "test" and q["heldout"] for q in extra)
    assert len({q["id"] for q in extra}) == len(extra)
