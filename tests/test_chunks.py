from finagent.chunks import chunk, records

TEXT = """Item 7. Management's Discussion
Net sales grew in every region.
Apple released new iPhone models this year with better cameras and longer battery life overall.
[TABLE]
 | 2024 | 2023
Americas | 167,045 | 162,560
Europe | 101,328 | 94,294
[/TABLE]
Services revenue rose again."""

size = 10
overlap = 3 

def test_chunk():
    passages = chunk(TEXT, size=10, overlap=3)
    assert all(len(p.split()) <= size for p in passages)
    assert all(len(p.split()) != 0 for p in passages)
    words = set()
    for p in passages : 
        words.update(p.split())
    assert all( word in words for word in TEXT.split())
    
def test_records():
    text = "Net sales grew in every region.\n" * 100
    result = records("NVDA","2025-01-26","7",text)
    id_list = [r["id"] for r in result]
    assert id_list == [f"NVDA_2025_7_{n}" for n in range(1, len(result) + 1)]
    assert all(r["fiscal_year"] == 2025 for r in result)
    assert all(r["ticker"] == "NVDA" and r["period_end"]== "2025-01-26" and r["item"] == "7" for r in result)
    assert [r["text"] for r in result] == chunk(text)