from finagent.clean import html_to_text

HTML = """<html><head><title>aapl-20240928</title></head><body>
<ix:header><ix:hidden>P1Y</ix:hidden></ix:header>
<div style="display:none">hidden fact</div>
<p>Net sales grew.</p>
<table>
<tr><td></td><td>2024</td><td>2023</td></tr>
<tr><td>Total net sales</td><td>$</td><td>391,035</td><td>$</td><td>383,285</td></tr>
</table>
<table><tr><td> </td></tr></table>
<p>Apple Inc. | 2024 Form 10-K | 21</p>
</body></html>"""

FOOTER = r"Apple Inc\. \| \d{4} Form 10-K \| \d+"


def test_html_to_text():
    text = html_to_text(HTML, FOOTER)
    assert "Net sales grew." in text
    assert "| 2024 | 2023" in text
    assert "Total net sales | $391,035 | $383,285" in text
    for junk in ["aapl-20240928", "P1Y", "hidden fact", "Form 10-K"]:
        assert junk not in text
    assert text.count("[TABLE]") == 1  # the empty layout table is gone
