"""From the retrieved passages to a checked answer.

The LLM reads, Python counts and checks (theorie/etape7_generation.md):
    1. ANSWER_SCHEMA   the answer contract, imposed on the model by the API
    2. build_user      the passages + question; SYSTEM holds the rules
    3. to_number       "383,285" in "millions" -> 383285000000.0
    4. check           the cited passage was given, and contains the cited number
    5. answer          prompt -> LLM -> check, the entry point of FinAgent

The checks catch an invented citation or an invented number. They do not catch a number
read from the wrong column of the right table: only the comparison with XBRL (step 8) does.
"""

from finagent.llm import generate
from finagent.relevance import contains_number

# ---------------------------------------------------------------------------
# 1. The answer contract 
# ---------------------------------------------------------------------------
SCALES = {"units": 1, "thousands": 1_000, "millions": 1_000_000, "billions": 1_000_000_000}

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "value": {"type": "string"},  # the number exactly as written: "383,285", "(1,234)"
        "scale": {"type": "string", "enum": list(SCALES)},
        "passage_id": {"type": "string"},
    },
    "required": ["found", "value", "scale", "passage_id"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# 2. The prompt 
# ---------------------------------------------------------------------------
SYSTEM = """You answer questions about companies' annual reports (10-K filings), using only \
the passages given in the user message. Never use your own knowledge.

Rules:
- Find the figure that answers the question, for the exact fiscal year asked. Tables often \
show several years side by side: pick the column of the year asked.
- Copy the number exactly as it is written in the passage (for example "383,285" or \
"(1,234)"). Do not convert, round or compute it.
- Give its scale, read from the table header or the text ("In millions" -> "millions"). If \
no scale is stated, use "units".
- Give the id of the passage you copied the number from.
- If no passage contains the answer, set found to false, value to "", scale to "units" and \
passage_id to "". A missing answer is better than a wrong one.
"""


def build_user(question: str, passages: list[dict]) -> str:
    """The passages, each wrapped in <passage id="...">...</passage>, then the question."""
    blocks = [f'<passage id="{p["id"]}">\n{p["text"]}\n</passage>' for p in passages]
    return "\n\n".join(blocks) + f"\n\nQuestion: {question}"


# ---------------------------------------------------------------------------
# 3. The conversion 
# ---------------------------------------------------------------------------
def _digits(value: str) -> str:
    """The number as a 10-K table prints it, without currency sign, brackets or spaces."""
    return value.replace("$", "").replace(" ", "").strip("()")


def to_number(value: str, scale: str) -> float:
    """'383,285' in 'millions' -> 383285000000.0; '(1,234)' is negative, as in a 10-K.

    The sign is read once the currency sign and spaces are gone: "$(11,683)", written so in
    226 passages, starts with "$" but is negative.
    """
    bare = value.replace("$", "").replace(" ", "")
    negative = bare.startswith("(") or bare.startswith("-")
    number = float(_digits(value).replace(",", "").lstrip("-")) * SCALES[scale]
    return -number if negative else number


# ---------------------------------------------------------------------------
# 4. The checks 
# ---------------------------------------------------------------------------
def check(reply: dict, passages: list[dict]) -> list[str]:
    """The problems found in the model's reply; an empty list means it passed.

    An abstention (found is false) has nothing to check.
    """
    if not reply["found"]:
        return []
    cited = next((p for p in passages if p["id"] == reply["passage_id"]), None)
    if cited is None:
        return ["cited passage not among those given"]
    if not contains_number(cited["text"], _digits(reply["value"])):
        return ["cited value not in the cited passage"]
    return []


# ---------------------------------------------------------------------------
# 5. The entry point 
# ---------------------------------------------------------------------------
def answer(question: dict, passages: list[dict]) -> dict:
    """Ask the model, check its reply and return the result.

    The passages are given by the caller (the retrieval of step 6). The number is None for
    an abstention or when a check failed: a figure that cannot be traced is not given.
    """
    reply = generate(SYSTEM, build_user(question["question"], passages), ANSWER_SCHEMA)
    problems = check(reply, passages)
    number = None
    if reply["found"] and not problems:
        try:
            number = to_number(reply["value"], reply["scale"])
        except ValueError:
            problems = ["value is not a number"]
    return {"found": reply["found"], "number": number, "value": reply["value"],
            "scale": reply["scale"], "passage_id": reply["passage_id"],
            "problems": problems, "_usage": reply["_usage"]}
