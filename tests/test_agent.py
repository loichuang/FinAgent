"""The tool-use loop, against a fake client that plays a conversation written in advance: no API call."""

import copy
import json
from types import SimpleNamespace as Block

import pytest

import finagent.agent as agent
from finagent.agent import ask, run_tool
from finagent.llm import LLMRefusal

NVDA_2025 = {"company": "NVDA", "concept": "revenue", "fiscal_year": 2025}
FINAL = {"answer": "Nvidia's revenue for fiscal 2025 was 130497000000 USD.",
         "value": 130497000000, "unit": "USD", "fiscal_year": 2025}


def _tool_use(id, input, name="get_fact"):
    return Block(type="tool_use", id=id, name=name, input=input)


def _response(stop_reason, *content):
    return Block(stop_reason=stop_reason, content=list(content), stop_details=None)


def _final(reply=FINAL):
    return _response("end_turn", Block(type="text", text=json.dumps(reply)))


class FakeClient:
    """Answers each call with the next scripted response and keeps a copy of what it was sent."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.sent = []  # the messages of every call, copied: the loop appends to the same list
        self.messages = self

    def create(self, **kwargs):
        self.sent.append(copy.deepcopy(kwargs["messages"]))
        return self.responses.pop(0)


@pytest.fixture
def fake(monkeypatch):
    def install(*responses):
        client = FakeClient(*responses)
        monkeypatch.setattr(agent, "client", lambda: client)
        return client
    return install


# --- run_tool ---

def test_run_tool_answers_with_the_id_of_its_tool_use():
    result = run_tool(_tool_use("t1", NVDA_2025))
    assert result == {"type": "tool_result", "tool_use_id": "t1",
                      "content": "Nvidia, revenue, fiscal 2025 (ended 2025-01-26): 130497000000 USD",
                      "is_error": False}


def test_run_tool_passes_a_tool_error_on():
    result = run_tool(_tool_use("t2", {"company": "NVDA", "concept": "revenue", "fiscal_year": 2022}))
    assert result["is_error"] is True and result["tool_use_id"] == "t2"


def test_run_tool_never_raises_on_an_unknown_tool():
    result = run_tool(_tool_use("t3", {}, name="get_ratio"))
    assert result["is_error"] is True
    assert "Available: get_fact" in result["content"]


# --- ask ---

def test_direct_answer_makes_one_call(fake):
    client = fake(_final())
    assert ask("What was Nvidia's revenue for fiscal 2025?") == {**FINAL, "tool_calls": []}
    assert len(client.sent) == 1


def test_one_tool_round_then_answer(fake):
    client = fake(_response("tool_use", _tool_use("t1", NVDA_2025)), _final())
    reply = ask("What was Nvidia's revenue for fiscal 2025?")
    assert reply == {**FINAL, "tool_calls": [{"name": "get_fact", "input": NVDA_2025,
                                              "is_error": False}]}

    # The second call resends the question, the model's turn and the tool result
    question, assistant, user = client.sent[1]
    assert question == {"role": "user", "content": "What was Nvidia's revenue for fiscal 2025?"}
    assert assistant["role"] == "assistant" and assistant["content"][0].id == "t1"
    assert user["role"] == "user"
    assert user["content"][0]["tool_use_id"] == "t1"
    assert "130497000000 USD" in user["content"][0]["content"]


def test_parallel_calls_come_back_in_a_single_user_turn(fake):
    apple = {"company": "AAPL", "concept": "revenue", "fiscal_year": 2025}
    client = fake(_response("tool_use", Block(type="text", text="Looking up both."),
                            _tool_use("a", apple), _tool_use("b", NVDA_2025)),
                  _final())
    ask("Compare the revenue of Apple and Nvidia for fiscal 2025.")

    user = client.sent[1][-1]
    # One result per tool_use, in the same turn, each with its own id; the text block runs nothing
    assert [r["tool_use_id"] for r in user["content"]] == ["a", "b"]
    assert "416161000000" in user["content"][0]["content"]
    assert "130497000000" in user["content"][1]["content"]


def test_tool_calls_record_failed_attempts(fake):
    wrong = {"company": "NVDA", "concept": "revenue", "fiscal_year": 2022}
    fake(_response("tool_use", _tool_use("t1", wrong)),
         _response("tool_use", _tool_use("t2", NVDA_2025)),
         _final())
    calls = ask("What was Nvidia's revenue for fiscal 2025?")["tool_calls"]
    assert [(c["input"]["fiscal_year"], c["is_error"]) for c in calls] == [(2022, True), (2025, False)]


def test_abstention_comes_back_as_null(fake):
    empty = {"answer": "FinAgent has no fiscal 2022 data for Nvidia.",
             "value": None, "unit": None, "fiscal_year": None}
    fake(_final(empty))
    assert ask("What was Nvidia's revenue for fiscal 2022?")["value"] is None


def test_loop_stops_after_max_turns(fake):
    looping = [_response("tool_use", _tool_use(f"t{i}", NVDA_2025)) for i in range(3)]
    client = fake(*looping)
    with pytest.raises(RuntimeError, match="after 3 turns"):
        ask("?", max_turns=3)
    assert len(client.sent) == 3


def test_refusal_and_cut_off_raise(fake):
    fake(_response("refusal"))
    with pytest.raises(LLMRefusal):
        ask("?")
    fake(_response("max_tokens"))
    with pytest.raises(RuntimeError, match="max_tokens"):
        ask("?")
