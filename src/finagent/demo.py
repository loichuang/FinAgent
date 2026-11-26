"""What the online demo needs besides the agent: the example questions and the visitor limits.

The example questions are answered once, locally, by scripts/demo_cache.py, and their answers
are committed in data/demo_cache.jsonl: a visitor who clicks one costs nothing. The cache key
covers the prompts and the code of the tools (agent.cache_key), so a change there makes the
committed answers stale; tests/test_demo.py fails until the script is run again.

The limits protect the API credit: a monthly spend limit is set in the Anthropic Console, and
the app adds two of its own, so that one visitor cannot use up the month in an evening.
"""
from pathlib import Path

DEMO_CACHE = Path(__file__).resolve().parents[2] / "data" / "demo_cache.jsonl"

# One figure, one ratio, and Nvidia's fiscal year, which ends in January
EXAMPLES = [
    "What was Apple's revenue in fiscal 2025?",
    "What was Microsoft's return on invested capital in fiscal 2026?",
    "What was Nvidia's operating margin for the fiscal year ended January 2026?",
]

QUESTIONS_PER_VISITOR = 5   # free-text questions, per browser session
QUESTIONS_PER_DAY = 100     # free-text questions, all visitors together
