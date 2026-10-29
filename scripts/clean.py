"""Turn every downloaded 10-K into plain text, in data/text/."""
from pathlib import Path

from finagent.clean import html_to_text

DATA = Path(__file__).resolve().parent.parent / "data"
FOOTERS = {"AAPL": r"Apple Inc\. \| \d{4} Form 10-K \| \d+"}

for raw in sorted((DATA / "raw").iterdir()):
    ticker = raw.name
    out = DATA / "text" / ticker
    out.mkdir(parents=True, exist_ok=True)
    for path in sorted(raw.glob("*.htm")):
        text = html_to_text(path.read_text(encoding="utf-8"), FOOTERS.get(ticker))
        (out / f"{path.stem}.txt").write_text(text, encoding="utf-8")
        print(f"{ticker} {path.stem}: {len(text):,} characters")
