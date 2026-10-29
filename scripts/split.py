"""Split every cleaned 10-K into one file per Item, in data/items/."""
from pathlib import Path

from finagent.items import split_items

DATA = Path(__file__).resolve().parent.parent / "data"

for text_dir in sorted((DATA / "text").iterdir()):
    ticker = text_dir.name
    for path in sorted(text_dir.glob("*.txt")):
        items = split_items(path.read_text(encoding="utf-8"))
        out = DATA / "items" / ticker / path.stem
        out.mkdir(parents=True, exist_ok=True)
        for item, section in items.items():
            (out / f"{item}.txt").write_text(section, encoding="utf-8")
        sizes = ", ".join(f"{item} {len(section):,}" for item, section in items.items())
        print(f"{ticker} {path.stem}: {sizes}")
