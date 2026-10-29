"""Split a cleaned 10-K into its Items."""
import re

# Each kept Item, with a word its heading must contain
ITEMS = {
    "1": "business",
    "1A": "risk factors",
    "7": "management",
    "8": "financial statements",
}

# A heading starts its line: "Item 7. Management's Discussion..."
# A table of contents row ends with its page number: "Item 7. | ... | 21"
HEADING = re.compile(
    r"^item\s+(\d+[a-c]?)\.(?!.*\|\s*\d+\s*$)(.*)$", re.IGNORECASE | re.MULTILINE
)
# Every 10-K holds one balance sheet, its title is a line of its own
BALANCE_SHEET = re.compile(
    r"^(consolidated )?(balance sheets?|statements? of financial (position|condition))\s*$",
    re.IGNORECASE | re.MULTILINE,
)
EXHIBIT_INDEX = re.compile(r"^exhibit index\s*$", re.IGNORECASE | re.MULTILINE)


def _sections(text: str) -> dict[str, tuple[int, int, str]]:
    """Every Item of the 10-K: number -> (start, end, heading title)."""
    matches = list(HEADING.finditer(text))
    ends = [m.start() for m in matches[1:]] + [len(text)]
    sections = {}
    for m, end in zip(matches, ends):
        item = m.group(1).upper()
        if item in sections:
            if item in ITEMS:
                raise ValueError(f"Item {item} has two headings")
            continue
        sections[item] = (m.start(), end, m.group(2))
    return sections


def split_items(text: str) -> dict[str, str]:
    """Text of each kept Item, from its heading to the next one."""
    sections = _sections(text)
    missing = [item for item in ITEMS if item not in sections]
    if missing:
        raise ValueError(f"Items not found: {missing}")
    for item, word in ITEMS.items():
        title = sections[item][2]
        if word not in title.lower():
            raise ValueError(f"Item {item} heading lacks {word!r}: {title.strip()!r}")
    items = {item: text[start:end].strip() for item, (start, end, _) in sections.items()
             if item in ITEMS}

    # Item 8 may only refer to statements printed elsewhere, as Nvidia does in Item 15:
    # the statements are in whichever Item holds the balance sheet
    sheets = [m.start() for m in BALANCE_SHEET.finditer(text)]
    if len(sheets) != 1:
        raise ValueError(f"{len(sheets)} balance sheet titles, expected 1")
    holder = [item for item, (start, end, _) in sections.items() if start <= sheets[0] < end]
    if not holder:
        raise ValueError("The balance sheet is outside every Item")
    if holder[0] != "8":
        start, end, _ = sections[holder[0]]
        items["8"] = EXHIBIT_INDEX.split(text[start:end])[0].strip()
    return items
