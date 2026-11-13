"""Step 8: the whole pipeline on the benchmark, graded against XBRL.

For each question: retrieval (RRF, 10 passages) -> Claude -> checks -> verdict.
Measured on the tuning set by default; the test set is measured once, at the end.

    .venv/bin/python scripts/evaluate_answers.py --dry-run      # free: retrieval + cost estimate
    .venv/bin/python scripts/evaluate_answers.py --limit 20     # the 20 first questions only
    .venv/bin/python scripts/evaluate_answers.py                # the 360 tuning questions
    .venv/bin/python scripts/evaluate_answers.py --test         # test set, held-out phrasing apart

Answers are cached (data/llm_cache.jsonl): a second run costs nothing. One line per question
is written to data/answers_<split>.jsonl, to read the errors one by one.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from finagent import llm
from finagent.embed import load_embeddings
from finagent.evaluate import VERDICTS, verdict
from finagent.generate import ANSWER_SCHEMA, SYSTEM, answer, build_user
from finagent.pipeline import retrieve
from finagent.relevance import relevant_ids
from finagent.search import load_passages

DATA = Path(__file__).resolve().parent.parent / "data"
# Haiku 5.5, dollars per million tokens (Anthropic price list cached on 6 Oct. 2026)
PRICE_IN, PRICE_OUT = 0.10, 0.50
CHARS_PER_TOKEN = 4  # rough, for the dry-run estimate only
OUT_TOKENS = 60      # a JSON answer is about this long

parser = argparse.ArgumentParser()
parser.add_argument("--test", action="store_true", help="measure the test set instead of tuning")
parser.add_argument("--limit", type=int, help="only the first N questions")
parser.add_argument("--dry-run", action="store_true", help="retrieve and estimate, do not call Claude")
args = parser.parse_args()
split = "test" if args.test else "tuning"

passages = load_passages()
embeddings = load_embeddings()
with open(DATA / "questions.jsonl", encoding="utf-8") as f:
    questions = [q for line in f if line.strip() and (q := json.loads(line))["split"] == split]
if args.limit:
    questions = questions[: args.limit]
print(f"Split: {split}, {len(questions)} questions, model {llm.MODEL}, effort {llm.EFFORT}\n")

# ---------------------------------------------------------------------------
# Dry run: what would be sent and what it would cost, without a call
# ---------------------------------------------------------------------------
if args.dry_run:
    cache = llm._read_cache(llm.CACHE)
    chars, cached = 0, 0
    for q in questions:
        user = build_user(q["question"], retrieve(q, passages, embeddings))
        if llm.cache_key(SYSTEM, user, ANSWER_SCHEMA) in cache:
            cached += 1
        else:
            chars += len(SYSTEM) + len(user)
    to_pay = len(questions) - cached
    tokens_in = chars / CHARS_PER_TOKEN
    cost = (tokens_in * PRICE_IN + to_pay * OUT_TOKENS * PRICE_OUT) / 1e6
    print(f"Already cached : {cached}")
    print(f"To call        : {to_pay}, about {tokens_in:,.0f} input tokens")
    print(f"Estimated cost : ~${cost:.2f}")
    print("\nDry run: Claude was not called, nothing was spent.")
    raise SystemExit

# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------
rows, cost, tokens_in, tokens_out = [], 0.0, 0, 0
for i, q in enumerate(questions, 1):
    retrieved = retrieve(q, passages, embeddings)
    hit = bool(relevant_ids(q, passages) & {p["id"] for p in retrieved})
    try:
        result = answer(q, retrieved)
        grade = verdict(result, q["value"])
        usage = result.pop("_usage")
        if not usage["cached"]:
            tokens_in += usage["input_tokens"]
            tokens_out += usage["output_tokens"]
            cost += (usage["input_tokens"] * PRICE_IN + usage["output_tokens"] * PRICE_OUT) / 1e6
    except Exception as error:  # a refusal or an API error must not stop 360 questions
        result, grade = {"error": f"{type(error).__name__}: {error}"}, "error"
    rows.append({"id": q["id"], "expected": q["value"], "verdict": grade,
                 "retrieval_hit": hit, **result})
    if i % 20 == 0 or i == len(questions):
        print(f"  {i}/{len(questions)}  spent so far ${cost:.4f}")

with open(DATA / f"answers_{split}.jsonl", "w", encoding="utf-8") as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------
def report(name: str, subset: list[dict]) -> None:
    n = len(subset)
    if n == 0:
        return
    counts = Counter(r["verdict"] for r in subset)
    answered = counts["right"] + counts["wrong"]
    cells = "  ".join(f"{v} {counts[v] / n:6.1%}" for v in (*VERDICTS, "error") if v != "error" or counts[v])
    precision = f"{counts['right'] / answered:.1%}" if answered else "n/a"
    print(f"{name:<34}{cells}   precision {precision}   ({n} q.)")


print()
report("all", rows)
report("passage retrieved", [r for r in rows if r["retrieval_hit"]])
report("passage missed by retrieval", [r for r in rows if not r["retrieval_hit"]])
if split == "test":
    # The held-out phrasing was never seen while tuning: a gap with the seen phrasings
    # would mean the pipeline fits the wording of the tuning questions
    print()
    report("phrasings seen while tuning", [r for r in rows if not r["id"].endswith("_heldout")])
    report("held-out phrasing", [r for r in rows if r["id"].endswith("_heldout")])
print("\nright = within 1 % of XBRL. precision = right / (right + wrong): how far a given number can be trusted.")
print(f"Spent : ${cost:.4f} ({tokens_in:,} tokens in, {tokens_out:,} out, cached answers free)")
print(f"Details: data/answers_{split}.jsonl")
