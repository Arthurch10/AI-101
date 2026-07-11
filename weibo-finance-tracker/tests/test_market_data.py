"""行情数据测试"""

from src.market_data import MarketData, normalize_symbol


def test_normalize_symbol_shanghai():
    assert normalize_symbol("600519") == "sh600519"
    assert normalize_symbol("688981") == "sh688981"


def test_normalize_symbol_shenzhen():
    assert normalize_symbol("000858") == "sz000858"
    assert normalize_symbol("300750") == "sz300750"


def test_normalize_symbol_invalid():
    assert normalize_symbol("宁德时代") is None
    assert normalize_symbol("12345") is None      # 非 6 位
    assert normalize_symbol("") is None


def test_demo_kline_deterministic():
    md1 = MarketData(demo=True)
    md2 = MarketData(demo=True)
    k1 = md1.get_kline("600519", datalen=30)
    k2 = md2.get_kline("600519", datalen=30)
    assert k1 == k2                # 可复现
    assert len(k1) == 30
    assert all(v > 0 for v in k1.values())


def test_demo_kline_differs_by_code():
    md = MarketData(demo=True)
    a = md.get_kline("600519", datalen=30)
    b = md.get_kline("000858", datalen=30)
    assert list(a.values()) != list(b.values())


def test_price_on_or_after():
    md = MarketData(demo=True)
    kline = {"2026-01-02": 10.0, "2026-01-05": 11.0, "2026-01-06": 12.0}
    # 精确匹配
    assert md.price_on_or_after(kline, "2026-01-05") == 11.0
    # 非交易日 → 取之后最近
    assert md.price_on_or_after(kline, "2026-01-03") == 11.0
    # 早于所有 → 取最早
    assert md.price_on_or_after(kline, "2026-01-01") == 10.0
    # 晚于所有 → None
    assert md.price_on_or_after(kline, "2026-02-01") is None
