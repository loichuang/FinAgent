"""Turn a 10-K HTML file into plain text, tables flattened into rows."""
import re
import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# 10-K files are XHTML, the HTML parser reads them fine
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

BLOCKS = ["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br"]


def _table_to_text(table) -> str:
    rows = []
    for tr in table.find_all("tr"):
        cells = []
        for td in tr.find_all(["td", "th"]):
            text = td.get_text(" ", strip=True)
            if not text:
                continue
            if cells and cells[-1] == "$":
                cells[-1] += text  # "$" and "391,035" sit in two cells
            elif cells and text in ("%", ")%", ")"):
                cells[-1] += text  # so do "(8" and ")%"
            else:
                cells.append(text)
        if cells:
            rows.append(cells)
    if not rows:
        return ""  # layout table with no text

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


def html_to_text(html: str, footer: str | None = None) -> str:
    """Visible text of a 10-K, one block per line, footer lines removed."""
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
    if footer:
        text = re.sub(footer, "", text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()
