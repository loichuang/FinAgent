"""P2.6: the agent of phase 2 on the benchmark of phase 1, graded the same way against XBRL.

For each question: agent.ask (the model, get_fact and get_ratio) -> verdict -> where it went off.
Measured on the tuning set by default; the test set is measured once, at the end.

    .venv/bin/python scripts/evaluate_agent.py --dry-run      # free: cost estimate, no call
    .venv/bin/python scripts/evaluate_agent.py --limit 20     # the 20 first questions only
    .venv/bin/python scripts/evaluate_agent.py                # the 360 tuning questions
    .venv/bin/python scripts/evaluate_agent.py --test         # test set, once

Answers are cached (data/agent_cache.jsonl): a second run costs nothing. One line per question
is written to data/agent_answers_<split>.jsonl. When the RAG of phase 1 has been run on the same
questions (scripts/evaluate_answers.py), the report puts both side by side.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from finagent import agent
from finagent.evaluate import agent_verdict, diagnose

DATA = Path(__file__).resolve().parent.parent / "data"
# Haiku 5.5, dollars per million tokens (Anthropic price list cached on 3 Nov. 2026)
PRICE_IN, PRICE_OUT = 0.10, 0.50
CHARS_PER_TOKEN = 3.5   # rough, for the dry-run estimate only (phase 1: 4 was too low)
TURNS, OUT_TOKENS = 2, 400   # one get_fact call then the answer; thinking is paid as output

parser = argparse.ArgumentParser()
parser.add_argument("--test", action="store_true", help="measure the test set instead of tuning")
parser.add_argument("--limit", type=int, help="only the first N questions")
parser.add_argument("--dry-run", action="store_true", help="estimate the cost, do not call the model")
args = parser.parse_args()
split = "test" if args.test else "tuning"

with open(DATA / "questions.jsonl", encoding="utf-8") as f:
    questions = [q for line in f if line.strip() and (q := json.loads(line))["split"] == split]
if args.limit:
    questions = questions[: args.limit]
print(f"Split: {split}, {len(questions)} questions, model {agent.MODEL}, effort {agent.EFFORT}\n")

# ---------------------------------------------------------------------------
# Dry run: how many questions would be paid for, and roughly how much
# ---------------------------------------------------------------------------
if args.dry_run:
    cache = agent._read_cache(agent.CACHE)
    to_pay = [q for q in questions if agent.cache_key(q["question"], 5) not in cache]
    # Every turn rereads the prompt, the two tool cards and the conversation so far
    fixed = len(agent.SYSTEM) + len(json.dumps(agent.TOOL_CARDS)) + len(json.dumps(agent.ANSWER_SCHEMA))
    tokens_in = sum(TURNS * (fixed + len(q["question"])) + 600 for q in to_pay) / CHARS_PER_TOKEN
    cost = (tokens_in * PRICE_IN + len(to_pay) * TURNS * OUT_TOKENS * PRICE_OUT) / 1e6
    print(f"Already cached : {len(questions) - len(to_pay)}")
    print(f"To call        : {len(to_pay)}, about {tokens_in:,.0f} input tokens")
    print(f"Estimated cost : ~${cost:.2f} (rough: run --limit 20 to measure the real cost)")
    print("\nDry run: the model was not called, nothing was spent.")
    raise SystemExit

# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------
rows, cost, tokens_in, tokens_out = [], 0.0, 0, 0
for i, q in enumerate(questions, 1):
    try:
        reply = agent.ask(q["question"])
        usage = reply.pop("_usage")
        grade = agent_verdict(reply, q["value"])
        where = None if grade == "right" else diagnose(reply, q)
        if not usage["cached"]:
            tokens_in += usage["input_tokens"]
            tokens_out += usage["output_tokens"]
            cost += (usage["input_tokens"] * PRICE_IN + usage["output_tokens"] * PRICE_OUT) / 1e6
    except Exception as error:  # a refusal or an API error must not stop 360 questions
        reply, grade, where = {"error": f"{type(error).__name__}: {error}"}, "error", "error"
    rows.append({"id": q["id"], "question": q["question"], "expected": q["value"],
                 "verdict": grade, "diagnosis": where, **reply})
    if i % 20 == 0 or i == len(questions):
        print(f"  {i}/{len(questions)}  spent so far ${cost:.4f}")

with open(DATA / f"agent_answers_{split}.jsonl", "w", encoding="utf-8") as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------
def line(name: str, subset: list[dict]) -> str:
    n = len(subset)
    if n == 0:
        return f"{name:<30}(none)"
    counts = Counter(r["verdict"] for r in subset)
    answered = counts["right"] + counts["wrong"]
    cells = "  ".join(f"{v} {counts[v] / n:6.1%}" for v in ("right", "wrong", "abstained"))
    errors = f"  error {counts['error'] / n:.1%}" if counts["error"] else ""
    precision = f"{counts['right'] / answered:.1%}" if answered else "n/a"
    return f"{name:<30}{cells}{errors}   precision {precision}   ({n} q.)"


seen = [r for r in rows if not r["id"].endswith("_heldout")]
heldout = [r for r in rows if r["id"].endswith("_heldout")]
print("\nAgent (phase 2)")
print(line("  all", rows))
if split == "test":
    print(line("  phrasings seen while tuning", seen))
    print(line("  held-out phrasing", heldout))

# Did the model use the tool? A right answer without a call comes from its memory
called = [r for r in rows if any(c["name"] == "get_fact" for c in r.get("tool_calls", []))]
print(f"\nget_fact called on {len(called) / len(rows):.1%} of the questions; "
      f"right without any call: {sum(r['verdict'] == 'right' and not r.get('tool_calls') for r in rows)}")

# Where the wrong and abstained answers went off
off = Counter(r["diagnosis"] for r in rows if r["verdict"] != "right")
if off:
    print("Not right, by cause: " + ", ".join(f"{cause} {n}" for cause, n in off.most_common()))

# The RAG of phase 1 on the same questions, when its answers are newer than the questions
rag_file = DATA / f"answers_{split}.jsonl"
if rag_file.exists() and rag_file.stat().st_mtime > (DATA / "questions.jsonl").stat().st_mtime:
    with open(rag_file, encoding="utf-8") as f:
        rag = {r["id"]: r for line_ in f if line_.strip() and (r := json.loads(line_))}
    same = [rag[r["id"]] for r in rows if r["id"] in rag]
    if len(same) == len(rows):
        print("\nRAG (phase 1), same questions")
        print(line("  all", same))
        if split == "test":
            print(line("  phrasings seen while tuning", [r for r in same if not r["id"].endswith("_heldout")]))
            print(line("  held-out phrasing", [r for r in same if r["id"].endswith("_heldout")]))
else:
    print(f"\n(no RAG answers on these questions yet: run scripts/evaluate_answers.py"
          f"{' --test' if split == 'test' else ''} to compare)")

print("\nright = within 1 % of XBRL. precision = right / (right + wrong).")
print(f"Spent : ${cost:.4f} ({tokens_in:,} tokens in, {tokens_out:,} out, cached answers free)")
print(f"Details: data/agent_answers_{split}.jsonl")
