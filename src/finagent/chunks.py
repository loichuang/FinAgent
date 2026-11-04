"""Split an Item into overlapping passages for retrieval."""


def _pieces(words: list[str], size: int, overlap: int) -> list[str]:
    """A too long line cut into windows of size word sharing overlap word."""
    step = size - overlap
    pieces = []
    for start in range(0, len(words), step):
        pieces.append(" ".join(words[start:start+size]))
        if start + size >= len(words):
            break
        
    return pieces
        

def chunk (text: str, size: int = 300, overlap: int = 50) -> list[str]:
    """Passages of at most size words """
    # Lines ready to accumulate : no empty line none longer than size
    lines = []
    for line in text.splitlines():
        words = line.split()
        if not words : 
            continue 
        if len(words) > size : 
            lines.extend(_pieces(words,size,overlap))
        else : 
            lines.append(line)
    # Accumulate whole lines into passages
    passages = []
    current = []  # lines of the passage being built
    count = 0     # its number of words
    for line in lines:
        n = len(line.split())
        if count + n > size:
            passages.append("\n".join(current))
            # Start the next passage with the last lines, at most `overlap` words
            kept, total = [], 0
            for prev in reversed(current):
                m = len(prev.split())
                if total + m > overlap:
                    break
                kept.insert(0, prev)
                total += m
            if total + n > size:  # the overlap would push the new line over size
                kept, total = [], 0
            current, count = kept, total
        current.append(line)
        count += n
    if current:
        passages.append("\n".join(current))
    return passages

def records(ticker: str, period_end: str, item: str, text: str) -> list[dict] :
    """The passages of one Item , each with its metadata"""
    records = []
    year = int(period_end[:4])
    passages = chunk(text)
    for count, passage in enumerate(passages, start=1):
        record = {
            "id" : f"{ticker}_{year}_{item}_{count}",
            "ticker" : ticker,
            "fiscal_year": year,
            "period_end": period_end,
            "item": item,
            "text" : passage
        }
        records.append(record)
    return records

    
    