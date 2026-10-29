"""Split a cleaned 10-K into its Items."""
import re

ITEMS = ("1", "1A", "7", "8")

# A heading is a line of its own: "Item 7. Management's Discussion..."
# The table of contents holds the same words in a table row: "Item 7. | ... | 21"
HEADING = re.compile(r"^item\s+(\d+[a-c]?)\.(?!.*\|)", re.IGNORECASE | re.MULTILINE)


def split_items(text: str, wanted: tuple[str, ...] = ITEMS) -> dict[str, str]:
    """Text of each wanted Item, from its heading to the next one."""
    headings = [(m.group(1).upper(), m.start()) for m in HEADING.finditer(text)]
    ends = [start for _, start in headings[1:]] + [len(text)]
    sections = {}
    for (item, start), end in zip(headings, ends):
        if item in wanted and item in sections:
            raise ValueError(f"Item {item} has two headings")
        sections.setdefault(item, text[start:end].strip())

    missing = [item for item in wanted if item not in sections]
    if missing:
        raise ValueError(f"Items not found: {missing}")
    return {item: sections[item] for item in wanted}
