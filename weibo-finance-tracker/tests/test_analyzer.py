"""观点分析 NLP 测试"""

from src.analyzer import OpinionAnalyzer


an = OpinionAnalyzer()


def test_sentiment_range():
    s = an.analyze_sentiment("今天大涨，非常看好后市！")
    assert -1.0 <= s <= 1.0


def test_market_view_bullish():
    text = "看多后市，建议加仓，利好突破放量"
    assert an.detect_market_view(text) == "bullish"


def test_market_view_bearish():
    text = "看空短期，建议减仓清仓，利空跌停"
    assert an.detect_market_view(text) == "bearish"


def test_market_view_neutral():
    text = "今天天气不错，随便聊聊生活"
    assert an.detect_market_view(text) == "neutral"


def test_extract_tickers_codes():
    text = "关注宁德时代（300750）和茅台(600519)"
    tickers = an.extract_tickers(text)
    assert "300750" in tickers
    assert "600519" in tickers


def test_extract_tickers_dollar():
    text = "$宁德时代$ 值得关注"
    tickers = an.extract_tickers(text)
    assert "宁德时代" in tickers


def test_extract_sectors():
    text = "半导体和新能源板块今天领涨，医药走弱"
    sectors = an.extract_sectors(text)
    assert "半导体" in sectors
    assert "新能源" in sectors
    assert "医药" in sectors


def test_analyze_post_basic_structure():
    post = {"post_id": "p1", "blogger_uid": "1",
            "content": "看多半导体，加仓中芯国际（688981）"}
    op = an.analyze_post_basic(post)
    assert op["post_id"] == "p1"
    assert op["market_view"] == "bullish"
    assert "688981" in op["tickers"]
    assert 0.0 <= op["confidence"] <= 1.0
