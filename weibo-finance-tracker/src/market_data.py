"""行情数据模块 - 获取 A 股/指数历史日线 (真实接口 + 演示模拟)"""

import math
import requests


# 新浪财经日线接口（免费，无需 key）
SINA_KLINE = ("http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
              "CN_MarketData.getKLineData")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Referer": "http://finance.sina.com.cn/",
}


def normalize_symbol(code):
    """把 6 位代码规范化为带市场前缀的 symbol (sh/sz)"""
    code = str(code).strip()
    if not code.isdigit() or len(code) != 6:
        return None
    if code.startswith(("60", "68", "5", "11", "51")):  # 沪市/科创/沪基金
        return "sh" + code
    if code.startswith(("00", "30", "12", "15", "16")):  # 深市/创业/深基金
        return "sz" + code
    if code.startswith("000"):  # 指数按沪市处理（简化）
        return "sh" + code
    return "sh" + code


class MarketData:
    """行情数据获取器"""

    def __init__(self, demo=False):
        self.demo = demo
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._cache = {}

    def get_kline(self, code, datalen=120):
        """获取日线收盘价序列，返回 {date_str: close}"""
        key = (code, datalen)
        if key in self._cache:
            return self._cache[key]

        if self.demo:
            data = self._demo_kline(code, datalen)
        else:
            data = self._real_kline(code, datalen)

        self._cache[key] = data
        return data

    def _real_kline(self, code, datalen):
        """从新浪接口获取真实日线"""
        symbol = normalize_symbol(code)
        if not symbol:
            return {}
        params = {"symbol": symbol, "scale": 240, "ma": "no", "datalen": datalen}
        try:
            resp = self.session.get(SINA_KLINE, params=params, timeout=15)
            resp.raise_for_status()
            rows = resp.json()
            return {r["day"]: float(r["close"]) for r in rows}
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return {}

    def _demo_kline(self, code, datalen):
        """演示模式: 基于代码确定性生成价格序列（可复现）"""
        from datetime import datetime, timedelta
        # 用代码字符和生成确定性种子
        seed = sum(ord(ch) for ch in str(code))
        base = 20 + seed % 80          # 基准价 20~100
        drift = ((seed % 7) - 3) * 0.002  # 每日漂移 -0.6%~+0.8%
        amp = 0.03 + (seed % 5) * 0.01    # 波动幅度

        today = datetime.now()
        out = {}
        price = base
        for i in range(datalen, 0, -1):
            day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            # 确定性正弦波 + 漂移
            wave = math.sin((seed + i) * 0.3) * amp
            price = max(1.0, price * (1 + drift + wave))
            out[day] = round(price, 2)
        return out

    def price_on_or_after(self, kline, date_str):
        """取 date_str 当天或之后最近一个交易日的收盘价"""
        if not kline:
            return None
        for d in sorted(kline.keys()):
            if d >= date_str:
                return kline[d]
        return None
