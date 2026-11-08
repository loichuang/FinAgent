from finagent.query import clean_query


def test_removes_stop_words_company_and_date():
    question = "What was Apple's revenue for the fiscal year ended September 28, 2024?"
    assert clean_query(question, "Apple").split() == ["revenue"]


def test_removes_a_company_name_of_several_words():
    question = "How much net income did Bank of America report for fiscal 2024?"
    assert clean_query(question, "Bank of America").split() == ["net", "income"]


def test_keeps_the_label_whatever_the_case():
    question = "TOTAL CURRENT ASSETS of Nvidia, May 5, 2024"
    assert clean_query(question, "Nvidia").split() == ["total", "current", "assets"]


def test_removes_every_number_and_report_word():
    question = "In its 10-K for fiscal 2025, what capital expenditures did Nvidia report?"
    assert clean_query(question, "Nvidia").split() == ["capital", "expenditures"]
