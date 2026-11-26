"""The example questions of the online demo must come from the committed cache, never the API."""
from finagent.agent import _read_cache, cache_key
from finagent.demo import DEMO_CACHE, EXAMPLES


def test_every_example_is_a_cache_hit():
    # A miss means the prompts or the tools changed: run scripts/demo_cache.py again
    cached = _read_cache(DEMO_CACHE)
    missing = [q for q in EXAMPLES if cache_key(q, 5) not in cached]
    assert not missing, f"not in data/demo_cache.jsonl, run scripts/demo_cache.py: {missing}"


def test_every_example_has_a_figure():
    # An example that abstains or fails would be a poor first impression of the demo
    cached = _read_cache(DEMO_CACHE)
    for question in EXAMPLES:
        assert cached[cache_key(question, 5)]["answer"]["value"] is not None, question
