from finagent import edgar


class FakeResponse:
    def json(self):
        return {"filings": {"recent": {
            "form": ["10-K", "8-K", "10-K/A", "10-K", "10-K"],
            "accessionNumber": ["a5", "x", "a4", "a3", "a2"],
            "filingDate": ["2026-11-01", "2026-08-01", "2025-12-01", "2025-10-31", "2024-11-01"],
            "reportDate": ["2026-09-26", "", "2025-09-27", "2025-09-27", "2024-09-28"],
            "primaryDocument": ["d5", "x", "d4", "d3", "d2"],
        }}}


def test_list_10k_skips_amendments_and_late_filings(monkeypatch):
    monkeypatch.setattr(edgar, "_get", lambda url: FakeResponse())
    filings = edgar.list_10k(320193, n=3, filed_before="2026-10-29")
    assert [f["accession"] for f in filings] == ["a3", "a2"]
