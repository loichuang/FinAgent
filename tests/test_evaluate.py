import pytest

from finagent.evaluate import recall_at_k

# Three passages per company: with only two, a word found in one of them gets a zero
# weight in BM25 and both passages tie. Rankings below were checked on 07/11/2026.
passages = [
    # AAPL 2024: the relevant passage shares "total net sales" with the question, so it ranks first
    {"id": "AAPL_2024_8_1", "ticker": "AAPL", "fiscal_year": 2024,
     "text": "Total net sales were 391,035 in fiscal 2024."},
    {"id": "AAPL_2024_1_1", "ticker": "AAPL", "fiscal_year": 2024,
     "text": "The Company designs wearables and accessories."},
    {"id": "AAPL_2024_1A_1", "ticker": "AAPL", "fiscal_year": 2024,
     "text": "Supply chain disruptions in Asia are a risk."},
    # MSFT 2024: the relevant passage shares no word with the question, so a distractor ranks first
    {"id": "MSFT_2024_7_1", "ticker": "MSFT", "fiscal_year": 2024,
     "text": "Microsoft cloud services revenue grew, led by Azure."},
    {"id": "MSFT_2024_1_1", "ticker": "MSFT", "fiscal_year": 2024,
     "text": "The Company develops software and devices."},
    {"id": "MSFT_2024_8_1", "ticker": "MSFT", "fiscal_year": 2024,
     "text": "Total amount for the year 245,122."},
]

# Found at k=1: its relevant passage AAPL_2024_8_1 ranks first
found = {"question": "What were Apple's total net sales?", "ticker": "AAPL",
         "fiscal_year": 2024, "value": 391035000000, "unit": "USD"}

# Missed at k=1, found at k=3: its relevant passage MSFT_2024_8_1 is not first
missed = {"question": "How much revenue did Microsoft cloud services bring?", "ticker": "MSFT",
          "fiscal_year": 2024, "value": 245122000000, "unit": "USD"}

# No relevant passage at all: there is no NVDA passage
no_answer = {"question": "What was Nvidia's net income?", "ticker": "NVDA",
             "fiscal_year": 2024, "value": 29760000000, "unit": "USD"}


def test_questions_without_answer_are_left_out():
    # found, missed and no_answer together, k=1: expected 0.5
    assert recall_at_k([found,missed,no_answer],passages,k=1) == 0.5


def test_k_changes_the_result():
    # missed alone: expected 0.0 at k=1 and 1.0 at k=3
    assert recall_at_k([missed],passages,k=1) == 0.0
    assert recall_at_k([missed],passages,k=3) == 1


def test_no_measurable_question_raises():
    # no_answer alone: expected ValueError
    with pytest.raises(ValueError):
        recall_at_k([no_answer],passages)


# ---- verdict (step 8) --------------------------------------------------------
from finagent.evaluate import verdict


def _result(found=True, number=None):
    return {"found": found, "number": number}


def test_verdict_right_within_one_percent():
    assert verdict(_result(number=383_285e6), 383_285e6) == "right"
    assert verdict(_result(number=100.9), 100) == "right"


def test_verdict_wrong_beyond_one_percent():
    # the 2022 column instead of 2023: 394,328 against 383,285
    assert verdict(_result(number=394_328e6), 383_285e6) == "wrong"
    assert verdict(_result(number=101), 100) == "wrong"


def test_verdict_wrong_sign():
    assert verdict(_result(number=-11_683e6), 11_683e6) == "wrong"


def test_verdict_abstained_and_rejected():
    assert verdict(_result(found=False), 1.0) == "abstained"
    assert verdict(_result(found=True, number=None), 1.0) == "rejected"


def test_verdict_expected_zero():
    assert verdict(_result(number=0.0), 0) == "right"
    assert verdict(_result(number=5.0), 0) == "wrong"
