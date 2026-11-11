"""Ask one question of the benchmark: retrieval (RRF, 10 passages) -> Claude -> checks.

    .venv/bin/python scripts/ask.py                 # the running example (Apple, revenue, 2023)
    .venv/bin/python scripts/ask.py --dry-run       # same, but stops before calling Claude: free
    .venv/bin/python scripts/ask.py --id <question id>

Only the call to Claude costs money, once: the answer is then cached in data/llm_cache.jsonl.
"""
import argparse
import json
from pathlib import Path

from finagent import llm
from finagent.embed import load_embeddings
from finagent.generate import answer, build_user
from finagent.pipeline import retrieve
from finagent.search import load_passages

DATA = Path(__file__).resolve().parent.parent / "data"
DEFAULT_ID = "AAPL_2023-09-30_RevenueFromContractWithCustomerExcludingAssessedTax_0"
# Haiku 5.5, dollars per million tokens (Anthropic price list cached on 6 Oct. 2026)
PRICE_IN, PRICE_OUT = 0.10, 0.50

parser = argparse.ArgumentParser()
parser.add_argument("--id", default=DEFAULT_ID, help="question id in data/questions.jsonl")
parser.add_argument("--dry-run", action="store_true", help="show the prompt, do not call Claude")
args = parser.parse_args()

with open(DATA / "questions.jsonl", encoding="utf-8") as f:
    question = next(q for line in f if (q := json.loads(line))["id"] == args.id)
passages = load_passages()
embeddings = load_embeddings()

# Step 6: RRF of BM25 (cleaned question) and dense (raw question), filtered on company and year
retrieved = retrieve(question, passages, embeddings)

print(f"Question : {question['question']}")
print(f"Expected : {question['value']:,.0f} {question['unit']} (XBRL)\n")
print("Passages retrieved:", ", ".join(p["id"] for p in retrieved))

if args.dry_run:
    user = build_user(question["question"], retrieved)
    print(f"\n--- message that would be sent ({len(user):,} characters) ---\n{user[:1500]}\n[...]")
    print("\nDry run: Claude was not called, nothing was spent.")
    raise SystemExit

result = answer(question, retrieved)
usage = result["_usage"]
cost = 0 if usage["cached"] else (usage["input_tokens"] * PRICE_IN + usage["output_tokens"] * PRICE_OUT) / 1e6

print(f"\nModel    : {usage['model']}{' (from cache, free)' if usage['cached'] else ''}")
print(f"Reply    : found={result['found']}  value={result['value']!r}  scale={result['scale']}  "
      f"passage={result['passage_id']}")
print(f"Problems : {result['problems'] or 'none'}")
print(f"Number   : {result['number']}")
if result["number"] is not None:
    gap = abs(result["number"] - question["value"]) / abs(question["value"])
    print(f"Verdict  : {'RIGHT' if gap < 0.01 else 'WRONG'} (gap {gap:.2%} from XBRL)")
print(f"Tokens   : {usage['input_tokens']:,} in, {usage['output_tokens']:,} out  ->  ~${cost:.4f}")
print(f"(model {llm.MODEL}, effort {llm.EFFORT})")
