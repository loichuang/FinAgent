"""The tool-use loop of phase 2: the model answers a question, calling get_fact when it needs a figure.

The API keeps no memory between calls: the loop holds the conversation in `messages`, sends it
whole at every turn, and appends the model's turn and the tool results to it.

    user       question
    assistant  tool_use get_fact(...)       stop_reason = "tool_use"
    user       tool_result                  same id as the tool_use
    assistant  final answer (JSON)          stop_reason = "end_turn"

The final answer follows ANSWER_SCHEMA: free text for a person, and the figure as a number for
the benchmark (phase 2 measure, P2.6).
"""
import hashlib
import json
from pathlib import Path

import finagent.concepts
import finagent.facts
import finagent.ratios
from finagent.llm import EFFORT, MAX_TOKENS, MODEL, LLMRefusal, client
from finagent.facts import FACT_TOOL, get_fact
from finagent.ratios import RATIO_TOOL, get_ratio

# The tools the model may call: the cards it reads, and the function behind each name
TOOL_CARDS = [FACT_TOOL, RATIO_TOOL]
TOOLS = {"get_fact": get_fact, "get_ratio": get_ratio}

# What the model is told once, before the question. The RAG of phase 1 will join as a third
# tool for text questions (phase 3).
SYSTEM = """You answer questions about the annual reports (10-K filings) of Apple, Amazon, \
Alphabet, Microsoft and Nvidia.

FinAgent's data covers fiscal years more recent than your own knowledge, up to 2026: a fiscal \
year you do not know about may still be in the data.

Rules:
- Never conclude that a figure is unavailable without calling the tool first: only an error \
from the tool tells you it is missing.
- For any reported figure (revenue, net income, assets, cash flows and the other items of the \
get_fact tool), call get_fact. Never answer a figure from memory.
- For a ratio listed in the get_ratio tool, call get_ratio. Never compute a ratio yourself, \
even from figures you already have.
- Copy the period from the question into the tool call as it is written: a date goes into \
period_end, "fiscal N" goes into fiscal_year. Never turn one into the other.
- Pick the concept whose meaning matches the question, not only its words.
- If a call returns an error, read it: correct the arguments and call again if the error shows \
how, otherwise give up on that figure.
- In the final answer, copy the value exactly as the tool returned it. Do not round, rescale \
or compute it. Its unit is the one get_fact gives ("USD", "USD/shares", "shares"); for \
get_ratio, "days" for a cycle ratio and "ratio" otherwise, the value being the decimal \
(0.4663, not 46.6).
- If the tool result carries a note, pass it on in the answer.
- Always say which fiscal year the figure belongs to, and its end date.
- If you could not get the figure, set value, unit and fiscal_year to null, and say so in \
answer. A missing answer is better than a wrong one.
"""

# The final answer. "answer" is for a person (the demo), the other fields for the benchmark.
# Every field is required, but the figure may be null: value null is an abstention, never a 0.
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},                                         # for a person
        "value": {"anyOf": [{"type": "number"}, {"type": "null"}]},           # as get_fact gave it
        "unit": {"anyOf": [{"type": "string"}, {"type": "null"}]},            # "USD", "USD/shares"
        "fiscal_year": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
    },
    "required": ["answer", "value", "unit", "fiscal_year"],
    "additionalProperties": False,
}


def run_tool(block) -> dict:
    """Run one tool_use block and wrap its result as a tool_result block.

    The result carries the id of the tool_use it answers. Never raises: an unknown tool comes
    back as an error result, so the loop keeps running and the model reads what went wrong.
    """
    if block.name not in TOOLS:
        return {"type": "tool_result", "tool_use_id": block.id,
                "content": f"Unknown tool {block.name}. Available: {', '.join(TOOLS)}.",
                "is_error": True}
    result = TOOLS[block.name](**block.input)
    return {"type": "tool_result", "tool_use_id": block.id,
            "content": result["content"], "is_error": result["is_error"]}


# Every final answer is kept on disk, like the answers of llm.generate: running the benchmark
# twice costs nothing, and the test set can be reread without calling the model again.
CACHE = Path(__file__).resolve().parents[2] / "data" / "agent_cache.jsonl"


def cache_key(question: str, max_turns: int) -> str:
    """A hash of everything that shapes the answer: model, prompts, tool cards, and the code of
    the tools themselves, so that a change in a formula or a concept is a new key, never a stale
    hit."""
    tool_code = "".join(Path(m.__file__).read_text(encoding="utf-8")
                        for m in (finagent.concepts, finagent.facts, finagent.ratios))
    payload = json.dumps({"model": MODEL, "effort": EFFORT, "system": SYSTEM, "tools": TOOL_CARDS,
                          "schema": ANSWER_SCHEMA, "question": question, "max_turns": max_turns,
                          "tool_code": tool_code}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_cache(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return {(row := json.loads(line))["key"]: row for line in f if line.strip()}


def ask(question: str, max_turns: int = 5, cache: Path | None = None) -> dict:
    """Answer a free-text question, calling the tools as many times as the model asks.

    Returns the final answer as a dict that follows ANSWER_SCHEMA, plus "tool_calls": every
    call the model made, in order, with its arguments and whether it failed, and "_usage": the
    tokens of all the turns and whether the answer came from the cache. Raises when the answer
    is unusable (refusal, cut off, no final answer after max_turns): these are for the caller,
    the model can do nothing about them.
    """
    cache = cache or CACHE
    key = cache_key(question, max_turns)
    hit = _read_cache(cache).get(key)
    if hit is not None:
        return {**hit["answer"], "_usage": {**hit["usage"], "cached": True}}

    messages = [{"role": "user", "content": question}]
    tool_calls = []  # what the model asked for: shows whether a figure came from the tool
    usage = {"model": MODEL, "input_tokens": 0, "output_tokens": 0, "turns": 0}
    for _ in range(max_turns):
        response = client().messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            tools=TOOL_CARDS,
            messages=messages,
            output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": ANSWER_SCHEMA}}
        )
        # Every turn is paid: the whole conversation is read again at each call
        usage["input_tokens"] += response.usage.input_tokens
        usage["output_tokens"] += response.usage.output_tokens
        usage["turns"] += 1
        if response.stop_reason == "refusal":
            raise LLMRefusal(getattr(response.stop_details, "category", None))
        if response.stop_reason == "max_tokens":
            raise RuntimeError("answer cut off by max_tokens")
        if response.stop_reason == "end_turn":
            text = next(block.text for block in response.content if block.type == "text")
            answer = {**json.loads(text), "tool_calls": tool_calls}
            cache.parent.mkdir(parents=True, exist_ok=True)
            with cache.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "question": question, "answer": answer,
                                    "usage": usage}, ensure_ascii=False) + "\n")
            return {**answer, "_usage": {**usage, "cached": False}}

        # tool_use: the model's whole turn first, then every result in a single user turn
        messages.append({"role": "assistant", "content": response.content})
        blocks = [block for block in response.content if block.type == "tool_use"]
        results = [run_tool(block) for block in blocks]
        messages.append({"role": "user", "content": results})
        tool_calls += [{"name": b.name, "input": b.input, "is_error": r["is_error"]}
                       for b, r in zip(blocks, results)]

    # Only reached when no turn ended with a final answer
    raise RuntimeError(f"no final answer after {max_turns} turns")