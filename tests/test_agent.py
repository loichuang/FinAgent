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
    return Block(stop_reason=stop_reason, content=list(content), stop_details=None,
                 usage=Block(input_tokens=1000, output_tokens=50))


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
def fake(monkeypatch, tmp_path):
    # A fresh cache per test: a scripted answer must never land in the real cache
    monkeypatch.setattr(agent, "CACHE", tmp_path / "agent_cache.jsonl")

    def install(*responses):
        client = FakeClient(*responses)
        monkeypatch.setattr(agent, "client", lambda: client)
        return client
    return install


def _strip(reply):
    """The answer without its usage, which the tests about the loop do not look at."""
    return {k: v for k, v in reply.items() if k != "_usage"}


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
    result = run_tool(_tool_use("t3", {}, name="search_reports"))
    assert result["is_error"] is True
    assert "Available: get_fact, get_ratio" in result["content"]


# --- ask ---

def test_direct_answer_makes_one_call(fake):
    client = fake(_final())
    assert _strip(ask("What was Nvidia's revenue for fiscal 2025?")) == {**FINAL, "tool_calls": []}
    assert len(client.sent) == 1


def test_one_tool_round_then_answer(fake):
    client = fake(_response("tool_use", _tool_use("t1", NVDA_2025)), _final())
    reply = _strip(ask("What was Nvidia's revenue for fiscal 2025?"))
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
    # Without a tool call it is first sent back once; the second null is accepted
    fake(_final(empty), _final(empty))
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


def test_ratio_call_runs_get_ratio(fake):
    gross = {"company": "NVDA", "ratio": "gross margin", "fiscal_year": 2025}
    client = fake(_response("tool_use", _tool_use("r1", gross, name="get_ratio")),
                  _final({"answer": "75.0%", "value": 0.7499, "unit": "ratio", "fiscal_year": 2025}))
    reply = ask("What was Nvidia's gross margin in fiscal 2025?")
    assert reply["tool_calls"] == [{"name": "get_ratio", "input": gross, "is_error": False}]
    assert "0.7499 (75.0%)" in client.sent[1][-1]["content"][0]["content"]


def test_usage_adds_up_every_turn(fake):
    fake(_response("tool_use", _tool_use("t1", NVDA_2025)), _final())
    usage = ask("What was Nvidia's revenue for fiscal 2025?")["_usage"]
    assert usage["turns"] == 2
    assert usage["input_tokens"] == 2000 and usage["output_tokens"] == 100
    assert usage["cached"] is False


def test_second_ask_comes_from_the_cache_without_a_call(fake):
    client = fake(_response("tool_use", _tool_use("t1", NVDA_2025)), _final())
    first = ask("What was Nvidia's revenue for fiscal 2025?")
    second = ask("What was Nvidia's revenue for fiscal 2025?")
    assert len(client.sent) == 2  # the two turns of the first ask, none for the second
    assert second["_usage"]["cached"] is True
    assert _strip(second) == _strip(first)


def test_a_change_in_the_tools_is_a_new_cache_key(monkeypatch):
    before = agent.cache_key("q", 5)
    monkeypatch.setattr(agent, "SYSTEM", agent.SYSTEM + " ")
    assert agent.cache_key("q", 5) != before


# --- The false start: a "pending" answer before any tool call ---

PENDING = {"answer": "pending", "value": None, "unit": None, "fiscal_year": None}


def test_false_start_is_sent_back_once_then_the_tool_is_called(fake):
    client = fake(_final(PENDING),
                  _response("tool_use", _tool_use("t1", NVDA_2025)),
                  _final())
    reply = ask("How much revenue did Nvidia report for fiscal 2025?")
    assert _strip(reply) == {**FINAL, "tool_calls": [{"name": "get_fact", "input": NVDA_2025,
                                                      "is_error": False}]}
    # The second call carries the false start and the nudge
    assert client.sent[1][-1] == {"role": "user", "content": agent.NUDGE}
    assert reply["_usage"]["turns"] == 3


def test_abstention_after_a_tool_call_is_accepted_without_nudge(fake):
    missing = {"company": "NVDA", "concept": "revenue", "fiscal_year": 2022}
    client = fake(_response("tool_use", _tool_use("t1", missing)), _final(PENDING))
    reply = ask("How much revenue did Nvidia report for fiscal 2022?")
    assert reply["value"] is None and reply["tool_calls"][0]["is_error"] is True
    assert len(client.sent) == 2  # no third call


def test_second_false_start_is_accepted_and_the_loop_stops(fake):
    client = fake(_final(PENDING), _final(PENDING))
    reply = ask("What is the weather in Espoo?")
    assert reply["value"] is None and reply["tool_calls"] == []
    assert len(client.sent) == 2


def test_a_figure_without_a_tool_call_is_not_nudged(fake):
    # A number from memory is graded as it is, and diagnose reports it as "no call"
    client = fake(_final())
    ask("What was Nvidia's revenue for fiscal 2025?")
    assert len(client.sent) == 1


def test_a_change_in_the_loop_is_a_new_cache_key(monkeypatch):
    before = agent.cache_key("q", 5)
    monkeypatch.setattr(agent.inspect, "getsource", lambda f: "changed loop")
    assert agent.cache_key("q", 5) != before
