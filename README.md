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

## Setup

```bash
cp .env.example .env   # then fill in your contact address
```

## License

MIT
