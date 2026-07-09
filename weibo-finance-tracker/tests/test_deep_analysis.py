"""深度分析与量化指标测试"""

from src.deep_analysis import DeepAnalyzer, _sentiment_label

deep = DeepAnalyzer()


def _mk(post_id, uid, sentiment, view, sectors="", tickers="", created="2026-01-05 10:00:00"):
    op = {"post_id": post_id, "blogger_uid": uid, "sentiment": sentiment,
          "keywords": "", "market_view": view, "sectors": sectors,
          "tickers": tickers, "confidence": abs(sentiment)}
    post = {"post_id": post_id, "blogger_uid": uid, "content": "x",
            "created_at": created, "reposts_count": 100,
            "comments_count": 50, "attitudes_count": 200, "topics": ""}
    return op, post


def test_sentiment_label_bounds():
    assert _sentiment_label(0.5) == "强烈看多"
    assert _sentiment_label(0.2) == "看多"
    assert _sentiment_label(0.0) == "中性"
    assert _sentiment_label(-0.2) == "看空"
    assert _sentiment_label(-0.5) == "强烈看空"


def test_market_trend_bullish():
    ops, posts = [], []
    for i in range(5):
        o, p = _mk(f"p{i}", "1", 0.5, "bullish")
        ops.append(o); posts.append(p)
    trend = deep.analyze_market_trend(ops, posts)
    assert trend["trend_direction"] == "上行"
    assert 0 <= trend["trend_strength"] <= 100
    assert 0 <= trend["heat_index"] <= 100
    assert len(trend["weekly_sentiment_trend"]) == 4


def test_market_trend_bearish():
    ops, posts = [], []
    for i in range(5):
        o, p = _mk(f"p{i}", "1", -0.5, "bearish")
        ops.append(o); posts.append(p)
    trend = deep.analyze_market_trend(ops, posts)
    assert trend["trend_direction"] == "下行"


def test_sector_aggregation_and_consensus():
    ops, posts = [], []
    # 三条一致看多半导体 → 高共识
    for i in range(3):
        o, p = _mk(f"p{i}", "1", 0.6, "bullish", sectors="半导体", tickers="688981")
        ops.append(o); posts.append(p)
    sectors = deep.analyze_sectors(ops, posts)
    semi = next(s for s in sectors if s["name"] == "半导体")
    assert semi["mention_count"] == 3
    assert semi["sentiment_score"] > 0
    assert semi["consensus_degree"] > 80          # 情绪一致 → 共识高
    assert "688981" in semi["related_tickers"]


def test_ticker_aggregation():
    ops, posts = [], []
    for i in range(2):
        o, p = _mk(f"p{i}", "1", 0.5, "bullish", tickers="600519")
        ops.append(o); posts.append(p)
    tickers = deep.analyze_tickers(ops, posts)
    t = next(x for x in tickers if x["name"] == "600519")
    assert t["mention_count"] == 2
    assert t["sentiment_label"] in ("看多", "强烈看多")


def test_quant_indicators_ranges():
    ops, posts = [], []
    for i in range(6):
        o, p = _mk(f"p{i}", "1", 0.4, "bullish", sectors="半导体")
        ops.append(o); posts.append(p)
    bloggers = [{"uid": "1", "followers_count": 100000}]
    q = deep.compute_quant_indicators(ops, posts, bloggers)
    assert -100 <= q["blogger_sentiment_index"] <= 100
    assert 0 <= q["market_heat_index"] <= 100
    assert 0 <= q["consensus_index"] <= 100
    assert 0 <= q["risk_appetite_index"] <= 100
    assert isinstance(q["signal_summary"], str) and q["signal_summary"]
    assert "gaining" in q["sector_rotation_signal"]
