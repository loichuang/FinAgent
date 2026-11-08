"""Generate the numeric questions with their XBRL answers, in data/questions.jsonl."""
import json
from collections import Counter
from pathlib import Path

from finagent.questions import all_questions, assign_split, heldout_questions

DATA = Path(__file__).resolve().parent.parent / "data"
questions = all_questions()
assign_split(questions)
for q in questions:
    q["heldout"] = False

# Phrasing written by hand for the test set only, never printed here
heldout = DATA / "heldout_template.txt"
if heldout.exists():
    template = heldout.read_text(encoding="utf-8").strip()
    questions += heldout_questions(questions, template)

with open(DATA / "questions.jsonl", "w", encoding="utf-8") as f:
    for q in questions:
        f.write(json.dumps(q, ensure_ascii=False) + "\n")
print(len(questions), "questions", dict(Counter(
    (q["split"], "heldout" if q["heldout"] else "seen") for q in questions
)))
