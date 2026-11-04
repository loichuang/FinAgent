"""Cut every Item into passages carrying their metadata, in data/passages.jsonl."""
import json
from pathlib import Path

from finagent.chunks import chunk

DATA = Path(__file__).resolve().parent.parent / "data"
with open(DATA / "passages.jsonl","w", encoding="utf-8") as f:
    for text_dir in sorted((DATA/"items").iterdir()):
        ticker = text_dir.name
        for date_dir in sorted(text_dir.iterdir()):
            year = int(date_dir.name[:4])
            for item_path in sorted(date_dir.glob("*.txt")):
                item = item_path.stem
                passages = chunk(item_path.read_text(encoding="utf-8"))
                for count, passage in enumerate(passages, start=1):
                    record = {
                        "id" : f"{ticker}_{year}_{item}_{count}",
                        "ticker" : ticker,
                        "fiscal_year":year,
                        "period_end": date_dir.name,
                        "item" : item,
                        "text": passage
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    