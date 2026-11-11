"""The LLM plumbing, with a fake Anthropic client: no key, no network, no cost."""

from types import SimpleNamespace

import pytest

from finagent import llm

SCHEMA = {"type": "object", "properties": {"found": {"type": "boolean"}},
          "required": ["found"], "additionalProperties": False}


class FakeMessages:
    """Imitates client().messages: records each request, answers with a fixed text."""

    def __init__(self, text, stop_reason="end_turn"):
        self.text, self.stop_reason, self.calls = text, stop_reason, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            stop_reason=self.stop_reason, stop_details=None, model="fake-model",
            content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=self.text)],
            usage=SimpleNamespace(input_tokens=100, output_tokens=7),
        )


def fake(monkeypatch, text, stop_reason="end_turn"):
    messages = FakeMessages(text, stop_reason)
    monkeypatch.setattr(llm, "client", lambda: SimpleNamespace(messages=messages))
    return messages


def test_generate_parses_the_json_and_reports_usage(monkeypatch, tmp_path):
    fake(monkeypatch, '{"found": true}')
    answer = llm.generate("sys", "user", SCHEMA, cache=tmp_path / "c.jsonl")
    assert answer["found"] is True
    assert answer["_usage"] == {"model": "fake-model", "input_tokens": 100, "output_tokens": 7,
                                "cached": False}


def test_second_identical_call_comes_from_the_cache(monkeypatch, tmp_path):
    messages = fake(monkeypatch, '{"found": false}')
    cache = tmp_path / "c.jsonl"
    llm.generate("sys", "user", SCHEMA, cache=cache)
    again = llm.generate("sys", "user", SCHEMA, cache=cache)
    assert len(messages.calls) == 1
    assert again["_usage"]["cached"] is True and again["found"] is False


def test_a_changed_prompt_is_a_new_key(monkeypatch, tmp_path):
    messages = fake(monkeypatch, '{"found": false}')
    cache = tmp_path / "c.jsonl"
    llm.generate("sys", "user", SCHEMA, cache=cache)
    llm.generate("sys v2", "user", SCHEMA, cache=cache)
    assert len(messages.calls) == 2


def test_the_schema_and_effort_are_sent(monkeypatch, tmp_path):
    messages = fake(monkeypatch, '{"found": true}')
    llm.generate("sys", "user", SCHEMA, cache=tmp_path / "c.jsonl")
    sent = messages.calls[0]["output_config"]
    assert sent["format"] == {"type": "json_schema", "schema": SCHEMA}
    assert sent["effort"] == llm.EFFORT


def test_a_refusal_raises_and_is_not_cached(monkeypatch, tmp_path):
    fake(monkeypatch, "", stop_reason="refusal")
    cache = tmp_path / "c.jsonl"
    with pytest.raises(llm.LLMRefusal):
        llm.generate("sys", "user", SCHEMA, cache=cache)
    assert not cache.exists()
