"""Answer the example questions of the online demo once, and keep the answers in data/demo_cache.jsonl.

Run locally, with the API key in .env, after any change to the prompts, the tools or the loop:
    .venv/bin/python scripts/demo_cache.py
The file is rewritten from scratch, so that it only holds the answers of the current code.
"""
from finagent.agent import ask
from finagent.demo import DEMO_CACHE, EXAMPLES

DEMO_CACHE.unlink(missing_ok=True)
for question in EXAMPLES:
    answer = ask(question, cache=DEMO_CACHE)
    calls = ", ".join(call["name"] for call in answer["tool_calls"])
    print(f"{question}\n  -> {answer['value']} {answer['unit']} ({calls})\n  {answer['answer']}\n")
