"""Turn a 10-K HTML file into plain text, tables flattened into rows."""
import re
import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# 10-K files are XHTML, the HTML parser reads them fine
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

BLOCKS = ["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br"]

# Lines that only exist because a 10-K is laid out in pages, matched as whole lines
NOISE = [
    r"Table of Contents(?: \| .+)?",   # link back to the contents, Alphabet adds its name
    r".+ \| \d{4} Form 10-K \| \d+",   # footer: "Apple Inc. | 2024 Form 10-K | 21"
    r"PART I{1,3}V?",                   # Part repeated on every page
    r"Item \d+[A-C]?",                  # Item repeated on every page, no dot unlike a heading
    r"\d{1,3}\.?",                      # page number
]


def _table_to_text(table) -> str:
    rows = []
    for tr in table.find_all("tr"):
        cells = []
        for td in tr.find_all(["td", "th"]):
            text = td.get_text(" ", strip=True)
            if not text:
                continue
            if cells and cells[-1] in ("$", "("):
                cells[-1] += text  # "$" and "391,035" sit in two cells, so may "(" and "259"
            elif cells and text in ("%", ")%", ")"):
                cells[-1] += text  # so do "(8" and ")%"
            else:
                cells.append(text)
        if cells:
            rows.append(cells)
    if not rows:
        return ""  # layout table with no text
    if len(rows) == 1:
        return "\n" + " | ".join(rows[0]) + "\n"  # a one-row table is layout, not data

    width = max(len(cells) for cells in rows)
    lines = []
    seen_full_row = False
    for cells in rows:
        if len(cells) == width:
            seen_full_row = True
        elif not seen_full_row and len(cells) == width - 1:
            cells = [""] + cells  # header row: its top-left cell is empty
        lines.append(" | ".join(cells))
    return "\n[TABLE]\n" + "\n".join(lines) + "\n[/TABLE]\n"


def html_to_text(html: str, noise: list[str] = NOISE) -> str:
    """Visible text of a 10-K, one block per line, page headers and footers removed."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["head", "ix:header"]):
        tag.decompose()
    for tag in soup.find_all(style=re.compile(r"display:\s*none")):
        tag.decompose()
    for table in soup.find_all("table"):
        table.replace_with(_table_to_text(table))
    for tag in soup.find_all(BLOCKS):
        tag.insert_after("\n")

    text = soup.get_text()
    text = re.sub(r"[ \t\xa0]+", " ", text)
    for pattern in noise:
        text = re.sub(rf"^ ?{pattern} ?$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[TABLE\]\s*\[/TABLE\]", "", text)  # tables that only held a page header
    text = re.sub(r"\(\s*([\d.,]+)\s*\)", r"(\1)", text)  # negative amounts: "( 259 )" -> "(259)"
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    # a page break split this sentence: no end punctuation before, a lowercase word after
    text = re.sub(r"(?<![.:;!?\s])\s*\n\n ?(?=[a-z][a-z])", " ", text)
    return text.strip()
