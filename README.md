# FinAgent

**Work in progress.** No results yet.

FinAgent answers questions about US public companies from their annual reports (10-K), cites
its sources, and measures its own errors against the official XBRL financial data published by
the SEC.

## Plan

1. **Data**: download 10-K filings from EDGAR and the matching XBRL facts
2. **RAG on numeric questions**: retrieve passages from the 10-K text and extract figures, with
   XBRL used only as the answer key
3. **XBRL tool**: let the model query XBRL directly for figures and measure the gain
4. **Text questions and CI**: risk factors and strategy questions, evaluation run on every change

## Data pipeline

Corpus: the last three 10-K filings of Apple, Microsoft, Alphabet, Amazon and Nvidia, filed
before 29 October 2026, plus their XBRL facts. Each step rebuilds its folder from the previous one.

| Folder | Content | Built by |
|---|---|---|
| `data/raw/`, `data/xbrl/` | 10-K HTML and XBRL facts as served by EDGAR, never modified | `scripts/download.py` |
| `data/text/` | Visible text, tables flattened into `cell \| cell` rows | `scripts/clean.py` |
| `data/items/` | Items 1, 1A, 7 and 8, one file each | `scripts/split.py` |

The rules rely on what the 10-K format imposes, not on one company's habits:

- **Page layout is removed.** "Table of Contents" links, page numbers, repeated Part and Item
  headers and page footers are matched as whole lines; a sentence split by a page break is glued back
- **Tables keep their structure.** One row per line between `[TABLE]` markers; a one-row table is
  layout and becomes plain text; negative amounts are written `(259)`
- **An Item heading is a line that starts with "Item N." and names the Item.** Table of contents
  rows end with a page number and are skipped
- **The financial statements are found by content.** They sit in whichever Item holds the
  balance sheet title: Item 8 for most companies, Item 15 for Nvidia, whose Item 8 only refers to them
- **Anything unexpected stops the pipeline**: a missing or repeated Item, a heading that does not
  name its Item, zero or several balance sheet titles

## Setup

```bash
cp .env.example .env   # then fill in your contact address
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/python scripts/download.py   # 10-K filings to data/raw/, XBRL facts to data/xbrl/
.venv/bin/python scripts/clean.py
.venv/bin/python scripts/split.py
```

## License

MIT
