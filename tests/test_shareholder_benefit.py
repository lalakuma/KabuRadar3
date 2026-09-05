from __future__ import annotations

from kaburadar3.market_data.shareholder_benefit import (
    _format_benefit,
    _format_summary,
    _parse_kabutan,
    _parse_minkabu,
    fetch_shareholder_benefit,
    fetch_shareholder_benefit_detail,
)


def test_parse_minkabu_meta_and_table() -> None:
    html = """
    <html><head>
    <meta name="description" content="ツルハホールディングス(3391)の株主優待は『株主ギフト券、または寄付』、優待利回りは2.15%、配当利回りは2.07%、権利確定月は2月！" />
    </head><body>
    優待発生株数 100 優待権利確定月 2月
    <h3>株主ギフト券</h3>
    <table>
      <tr><th>必要株数</th><th>優待内容</th><th>備考</th></tr>
      <tr><td>100株以上</td><td>5,000円相当</td><td>※寄付の選択も可能。</td></tr>
      <tr><td>500株以上</td><td>10,000円相当</td><td></td></tr>
    </table>
    </body></html>
    """
    parsed = _parse_minkabu(html)
    assert parsed["kind"] == "株主ギフト券、または寄付"
    assert parsed["month"] == "2"
    assert parsed["min_shares"] == 100
    assert len(parsed["programs"]) == 1
    assert parsed["programs"][0]["tiers"][0]["content"] == "5,000円相当"
    assert _format_summary(parsed) == "株主ギフト券、または寄付。100株以上。権利確定2月。"
    assert "・100株以上: 5,000円相当" in _format_benefit(parsed)


def test_parse_kabutan_meta() -> None:
    html = """
    <meta name="description" content="ツルハホールディングス（ツルハＨＤ）【3391】は株主優待に「株主ギフト券、または寄付」を実施しています。100株保有から優待がもらえます。権利確定月は2月です。" />
    """
    parsed = _parse_kabutan(html)
    assert parsed["kind"] == "株主ギフト券、または寄付"
    assert parsed["min_shares"] == 100
    assert parsed["month"] == "2"


def test_fetch_shareholder_benefit_no_program(monkeypatch) -> None:
    monkeypatch.setattr(
        "kaburadar3.market_data.shareholder_benefit._get_html",
        lambda url: '<meta name="description" content="エービーシー・マート(2670)の株主優待と優待利回り。" />',
    )
    assert fetch_shareholder_benefit("2670") == "なし"
    detail = fetch_shareholder_benefit_detail("2670")
    assert detail["summary"] == "なし"
