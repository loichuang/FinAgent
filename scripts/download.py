"""Download the corpus: three 10-K filings and the XBRL facts per company."""
import json
from pathlib import Path

from finagent import edgar

DATA = Path(__file__).resolve().parent.parent / "data"
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
FILED_BEFORE = "2026-10-29"  # freezes the corpus, new 10-Ks are filed every year

for ticker in TICKERS:
    cik = edgar.get_cik(ticker)
    raw = DATA / "raw" / ticker
    raw.mkdir(parents=True, exist_ok=True)
    (DATA / "xbrl").mkdir(parents=True, exist_ok=True)

    filings = edgar.list_10k(cik, n=3, filed_before=FILED_BEFORE)
    for filing in filings:
        path = edgar.download_10k(cik, filing, raw)
        print(f"{ticker} fiscal year ending {filing['report_date']} -> {path.name}")
    (raw / "filings.json").write_text(json.dumps(filings, indent=2))
    edgar.download_company_facts(cik, DATA / "xbrl" / f"{ticker}.json")
