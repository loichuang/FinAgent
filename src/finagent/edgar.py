"""Download 10-K filings and XBRL facts from SEC EDGAR."""
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"

PAUSE = 0.2  # seconds between requests: 5 per second at most, the SEC allows 10


def _get(url: str) -> requests.Response:
    user_agent = os.environ.get("SEC_USER_AGENT")
    if not user_agent:
        raise RuntimeError("SEC_USER_AGENT is missing, copy .env.example to .env")
    time.sleep(PAUSE)
    response = requests.get(url, headers={"User-Agent": user_agent}, timeout=30)
    response.raise_for_status()
    return response


def get_cik(ticker: str) -> int:
    """SEC identifier of a company, e.g. 320193 for AAPL."""
    for company in _get(TICKERS_URL).json().values():
        if company["ticker"] == ticker.upper():
            return company["cik_str"]
    raise ValueError(f"Unknown ticker: {ticker}")


def list_10k(cik: int, n: int = 3, filed_before: str | None = None) -> list[dict]:
    """The n most recent 10-K filings, newest first, amendments (10-K/A) excluded."""
    recent = _get(SUBMISSIONS_URL.format(cik=cik)).json()["filings"]["recent"]
    filings = []
    for i, form in enumerate(recent["form"]):
        if form != "10-K":
            continue
        if filed_before and recent["filingDate"][i] >= filed_before:
            continue
        filings.append({
            "accession": recent["accessionNumber"][i],
            "filing_date": recent["filingDate"][i],
            "report_date": recent["reportDate"][i],
            "document": recent["primaryDocument"][i],
        })
    return filings[:n]


def download_10k(cik: int, filing: dict, out_dir: Path) -> Path:
    """Save the 10-K HTML once, named after the fiscal year end."""
    path = out_dir / f"{filing['report_date']}.htm"
    if not path.exists():
        url = ARCHIVE_URL.format(
            cik=cik,
            accession=filing["accession"].replace("-", ""),
            document=filing["document"],
        )
        path.write_bytes(_get(url).content)
    return path


def download_company_facts(cik: int, path: Path) -> Path:
    """Save every XBRL fact the company ever reported, in one JSON file."""
    if not path.exists():
        path.write_bytes(_get(FACTS_URL.format(cik=cik)).content)
    return path
