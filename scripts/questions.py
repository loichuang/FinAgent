"""Generate the numeric questions with their XBRL answers, in data/questions.jsonl."""
import json
from collections import Counter
from pathlib import Path

from finagent.questions import all_questions, assign_split

DATA = Path(__file__).resolve().parent.parent / "data"
questions = all_questions()
assign_split(questions)
with open(DATA / "questions.jsonl", "w", encoding="utf-8") as f:
    for q in questions:
        f.write(json.dumps(q, ensure_ascii=False) + "\n")
print(len(questions), "questions", dict(Counter(q["split"] for q in questions)))
