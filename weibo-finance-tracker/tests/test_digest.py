"""AI 观点流研判测试"""

from src.digest import generate_digest


def _item(view, sentiment, sectors=None, tickers=None):
    return {"market_view": view, "sentiment": sentiment,
            "sectors": sectors or [], "tickers": tickers or []}


def test_empty_feed():
    d = generate_digest([])
    assert d["bullish"] == 0 and d["bearish"] == 0
    assert "暂无" in d["text"]


def test_counts_and_tone_bullish():
    items = [_item("bullish", 0.5, ["半导体"], ["688981"]) for _ in range(4)]
    items += [_item("bearish", -0.3, ["地产"], ["000002"])]
    d = generate_digest(items)
    assert d["bullish"] == 4
    assert d["bearish"] == 1
    assert "偏多" in d["text"]
    assert "半导体" in d["top_sectors"]
    assert "688981" in d["bull_tickers"]


def test_tone_bearish():
    items = [_item("bearish", -0.5) for _ in range(4)] + [_item("bullish", 0.2)]
    d = generate_digest(items)
    assert "偏空" in d["text"]


def test_divergence_detection():
    # 半导体既被看多又被看空 → 分歧
    items = [
        _item("bullish", 0.5, ["半导体"]),
        _item("bearish", -0.5, ["半导体"]),
        _item("bullish", 0.4, ["新能源"]),
    ]
    d = generate_digest(items)
    assert "半导体" in d["divergence"]
    assert "新能源" not in d["divergence"]


def test_avg_sentiment_in_text():
    items = [_item("bullish", 0.6), _item("bullish", 0.4)]
    d = generate_digest(items)
    assert d["avg_sentiment"] == 0.5
    assert "平均情绪" in d["text"]
