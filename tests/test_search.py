from finagent.search import search

passages = [
    # AAPL 2024: four passages, only one about iPhone net sales
    {"id": "AAPL_2024_7_1", "ticker": "AAPL", "fiscal_year": 2024,
     "text": "iPhone net sales increased due to higher net sales of iPhone Pro models."},
    {"id": "AAPL_2024_1A_1", "ticker": "AAPL", "fiscal_year": 2024,
     "text": "The Company faces risks from supply chain disruptions in Asia."},
    {"id": "AAPL_2024_8_1", "ticker": "AAPL", "fiscal_year": 2024,
     "text": "Operating expenses include research and development costs."},
    {"id": "AAPL_2024_1_1", "ticker": "AAPL", "fiscal_year": 2024,
     "text": "The Company designs wearables and accessories."},
    # Same company, other year: must be excluded by the year filter
    {"id": "AAPL_2023_7_1", "ticker": "AAPL", "fiscal_year": 2023,
     "text": "iPhone net sales decreased compared to the prior year."},
    # Other company, same year: must be excluded by the ticker filter
    {"id": "MSFT_2024_7_1", "ticker": "MSFT", "fiscal_year": 2024,
     "text": "Net sales of cloud services grew, led by Azure."},
]

k = 3
query = " Iphone net sales in 2024"
def test_search():
    candidates = search(query,passages, ticker="AAPL", fiscal_year=2024, k=k)
    assert all(c["ticker"] == "AAPL" and c["fiscal_year"]== 2024 for c in candidates)
    assert len(candidates) == k
    assert candidates[0]["id"] == "AAPL_2024_7_1"
    no_correspondance = search("Micron", passages,ticker = "SKH",fiscal_year = 2026,k=k)
    assert no_correspondance == [] 
    