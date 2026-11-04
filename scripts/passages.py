"""Cut every Item into passages carrying their metadata, in data/passages.jsonl."""
import json
from pathlib import Path

from finagent.chunks import records

DATA = Path(__file__).resolve().parent.parent / "data"
with open(DATA / "passages.jsonl","w", encoding="utf-8") as f:
    for text_dir in sorted((DATA/"items").iterdir()):
        ticker = text_dir.name
        for date_dir in sorted(text_dir.iterdir()):
            period_end = date_dir.name
            for item_path in sorted(date_dir.glob("*.txt")):
                item = item_path.stem
                text = item_path.read_text(encoding="utf-8")
                item_records = records(ticker, period_end, item, text)
                for record in item_records:
                    f.write(json.dumps(record, ensure_ascii=False)+ "\n")

                    