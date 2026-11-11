"""The call to the LLM, behind one function: generate(system, user, schema) -> dict.

Everything provider-specific lives here, so that another provider or a local model (phase 2
comparison) only replaces this module. The answer is constrained to a JSON schema by the API
itself (structured outputs), so the caller never parses free text.

Provider: Anthropic API, paid per token with a monthly spend limit set in the Console
(decided on 10 Nov. 2026). Default model Haiku 5.5 at low effort, the cheapest setting;
FINAGENT_MODEL and FINAGENT_EFFORT change them without touching the code.

Every answer is cached on disk, keyed by everything that shapes it (model, effort, prompts,
schema): running the evaluation twice costs nothing the second time, and a changed prompt
is a new key, never a stale hit.
"""

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MODEL = os.environ.get("FINAGENT_MODEL", "claude-haiku-5-5")
EFFORT = os.environ.get("FINAGENT_EFFORT", "low")  # low | medium | high | xhigh | max
MAX_TOKENS = 16000  # a ceiling, not a cost: only the tokens actually written are paid
CACHE = Path(__file__).resolve().parents[2] / "data" / "llm_cache.jsonl"


class LLMRefusal(Exception):
    """The model declined to answer."""


@lru_cache(maxsize=1)
def client():
    """The Anthropic client, built once from LLM_API_KEY in .env."""
    import anthropic
    key = os.environ.get("LLM_API_KEY")
    if not key:
        raise RuntimeError("LLM_API_KEY is empty: put your Anthropic key in .env")
    return anthropic.Anthropic(api_key=key)


def cache_key(system: str, user: str, schema: dict, model: str = MODEL, effort: str = EFFORT) -> str:
    """A hash of everything that shapes the answer."""
    payload = json.dumps({"model": model, "effort": effort, "system": system, "user": user,
                          "schema": schema}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_cache(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return {(row := json.loads(line))["key"]: row for line in f if line.strip()}


def generate(system: str, user: str, schema: dict, cache: Path = CACHE) -> dict:
    """The model's answer as a dict that follows `schema`, plus a "_usage" entry.

    "_usage" holds input and output tokens, the model that answered and whether the answer
    came from the cache (then no token was paid for).
    """
    key = cache_key(system, user, schema)
    hit = _read_cache(cache).get(key)
    if hit is not None:
        return {**hit["answer"], "_usage": {**hit["usage"], "cached": True}}

    response = client().messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": schema}},
    )
    if response.stop_reason == "refusal":
        raise LLMRefusal(getattr(response.stop_details, "category", None))
    if response.stop_reason == "max_tokens":
        raise RuntimeError("answer cut off by max_tokens")

    text = next(block.text for block in response.content if block.type == "text")
    answer = json.loads(text)
    usage = {"model": response.model, "input_tokens": response.usage.input_tokens,
             "output_tokens": response.usage.output_tokens}
    cache.parent.mkdir(parents=True, exist_ok=True)
    with cache.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, "answer": answer, "usage": usage}, ensure_ascii=False) + "\n")
    return {**answer, "_usage": {**usage, "cached": False}}
