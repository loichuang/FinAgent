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
<p>Our ability to compete depends on what customers and partners will</p>
<p>8</p>
<table><tr><td>Table of Contents</td><td>Alphabet Inc.</td></tr></table>
<p>Item 7</p>
<p>not provided by our products.</p>
<p>iPhone</p>
<p>iPhone net sales were flat.</p>
</body></html>"""


def test_html_to_text():
    text = html_to_text(HTML)
    assert "Net sales grew." in text
    assert "| 2024 | 2023" in text
    assert "Total net sales | $391,035 | $383,285" in text
    for junk in ["aapl-20240928", "P1Y", "hidden fact", "Form 10-K", "Table of Contents", "Item 7"]:
        assert junk not in text
    assert text.count("[TABLE]") == 1  # the empty layout table is gone


def test_page_break_is_glued_back():
    text = html_to_text(HTML)
    assert "customers and partners will not provided by our products." in text
    assert "\n8\n" not in text
    # "iPhone" starts with a lowercase letter but is a heading, it stays on its own line
    assert "products.\n\niPhone\n\niPhone net sales were flat." in text


def test_one_row_table_and_negative_amount():
    html = """<table><tr><td>Item 1.</td><td>Business</td></tr></table>
<table>
<tr><td></td><td>2026</td><td>2025</td></tr>
<tr><td>Interest expense</td><td>(</td><td>259</td><td>)</td><td>(</td><td>247</td><td>)</td></tr>
</table>"""
    text = html_to_text(html)
    assert text.startswith("Item 1. | Business\n")  # a one-row table is plain text
    assert "Interest expense | (259) | (247)" in text
