"""观点回测测试 - 用受控行情验证判定逻辑"""

from src import database as db
from src.backtest import Backtester


def _setup_opinion(view, ticker="600519", d0="2026-01-05"):
    """插入博主+帖子+观点，返回 opinion 字典"""
    db.add_blogger(uid="1", screen_name="A")
    db.save_posts([{"post_id": "p1", "blogger_uid": "1", "content": "x",
                    "created_at": f"{d0} 10:00:00",
                    "reposts_count": 0, "comments_count": 0,
                    "attitudes_count": 0, "topics": ""}])
    op = {"post_id": "p1", "blogger_uid": "1", "sentiment": 0.5,
          "keywords": "", "market_view": view, "sectors": "",
          "tickers": ticker, "confidence": 0.5}
    db.save_opinion(op)
    return op


def _fixed_market(bt, p0, p1, d0="2026-01-05", d1="2026-01-10"):
    """把行情替换为固定两点，避免网络"""
    bt.market.get_kline = lambda code, datalen=120: {d0: p0, d1: p1}


def test_bullish_correct_when_price_rises():
    op = _setup_opinion("bullish")
    bt = Backtester(horizon_days=5, threshold=0.02, demo=True)
    _fixed_market(bt, 100.0, 110.0)   # +10% > 2%
    correct, detail = bt._judge_opinion(op)
    assert correct is True
    assert detail["return"] > 0


def test_bullish_wrong_when_price_falls():
    op = _setup_opinion("bullish")
    bt = Backtester(horizon_days=5, threshold=0.02, demo=True)
    _fixed_market(bt, 100.0, 90.0)    # -10%
    correct, _ = bt._judge_opinion(op)
    assert correct is False


def test_bearish_correct_when_price_falls():
    op = _setup_opinion("bearish")
    bt = Backtester(horizon_days=5, threshold=0.02, demo=True)
    _fixed_market(bt, 100.0, 90.0)
    correct, _ = bt._judge_opinion(op)
    assert correct is True


def test_flat_move_within_threshold_is_wrong_for_directional():
    op = _setup_opinion("bullish")
    bt = Backtester(horizon_days=5, threshold=0.02, demo=True)
    _fixed_market(bt, 100.0, 100.5)   # +0.5% < 2% 阈值
    correct, _ = bt._judge_opinion(op)
    assert correct is False


def test_neutral_opinion_not_evaluated():
    op = _setup_opinion("neutral")
    bt = Backtester(demo=True)
    assert bt._judge_opinion(op) is None


def test_no_ticker_code_not_evaluated():
    op = _setup_opinion("bullish", ticker="宁德时代")  # 非 6 位代码
    bt = Backtester(demo=True)
    assert bt._judge_opinion(op) is None


def test_backtest_blogger_accuracy():
    _setup_opinion("bullish")
    bt = Backtester(demo=True)
    bt.market.get_kline = lambda code, datalen=120: {"2026-01-05": 100.0, "2026-01-10": 110.0}
    res = bt.backtest_blogger("1")
    assert res["evaluated"] == 1
    assert res["correct"] == 1
    assert res["accuracy"] == 1.0
