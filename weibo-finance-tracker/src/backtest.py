"""观点回测模块 - 用真实行情校验博主历史观点的准确率"""

from datetime import datetime, timedelta

from . import database as db
from .market_data import MarketData, normalize_symbol


def _horizon_date(date_str, days):
    """返回观点日期 + days 天的日期字符串"""
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    return (dt + timedelta(days=days)).strftime("%Y-%m-%d")


class Backtester:
    """博主观点回测器"""

    def __init__(self, horizon_days=5, threshold=0.02, demo=False):
        """
        horizon_days: 观点发布后多少天检验涨跌
        threshold:    判定涨/跌的收益率阈值 (默认 ±2%)
        demo:         使用模拟行情
        """
        self.horizon_days = horizon_days
        self.threshold = threshold
        self.market = MarketData(demo=demo)

    def _judge_opinion(self, opinion):
        """判定单条观点是否正确，返回 (correct, detail) 或 None(无法判定)"""
        view = opinion.get("market_view")
        if view not in ("bullish", "bearish"):
            return None  # 中性观点不计入准确率

        tickers = [t for t in (opinion.get("tickers") or "").split(",") if t]
        codes = [t for t in tickers if normalize_symbol(t)]
        if not codes:
            return None  # 无有效股票代码，无法回测

        post = _get_post(opinion["post_id"])
        if not post or not post.get("created_at"):
            return None
        d0 = post["created_at"][:10]
        d1 = _horizon_date(d0, self.horizon_days)
        if not d1:
            return None

        # 取所有相关个股的平均收益
        returns = []
        for code in codes:
            kline = self.market.get_kline(code)
            p0 = self.market.price_on_or_after(kline, d0)
            p1 = self.market.price_on_or_after(kline, d1)
            if p0 and p1 and p0 > 0:
                returns.append((p1 - p0) / p0)
        if not returns:
            return None

        avg_ret = sum(returns) / len(returns)

        # 判定正确性
        if view == "bullish":
            correct = avg_ret > self.threshold
        else:  # bearish
            correct = avg_ret < -self.threshold

        return correct, {
            "post_id": opinion["post_id"],
            "view": view,
            "codes": codes,
            "return": round(avg_ret, 4),
            "correct": correct,
        }

    def backtest_blogger(self, uid):
        """回测单个博主，返回准确率统计"""
        opinions = db.get_opinions(uid, limit=500)
        evaluated, correct, details = 0, 0, []
        for op in opinions:
            result = self._judge_opinion(op)
            if result is None:
                continue
            is_correct, detail = result
            evaluated += 1
            if is_correct:
                correct += 1
            details.append(detail)

        accuracy = (correct / evaluated) if evaluated else None
        return {
            "uid": uid,
            "evaluated": evaluated,
            "correct": correct,
            "accuracy": round(accuracy, 4) if accuracy is not None else None,
            "details": details,
        }

    def backtest_all(self):
        """回测所有博主并写入数据库"""
        results = []
        for b in db.get_all_bloggers():
            r = self.backtest_blogger(b["uid"])
            r["screen_name"] = b["screen_name"]
            if r["accuracy"] is not None:
                db.save_backtest(r["uid"], r["accuracy"], r["evaluated"], r["correct"])
            results.append(r)
        return results


def _get_post(post_id):
    """按 post_id 取单条帖子"""
    conn = db.get_connection()
    row = conn.execute("SELECT * FROM posts WHERE post_id = ?", (post_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
