"""趋势跟踪策略：MA 金叉死叉、MACD 柱状图、布林带突破。"""
import pandas as pd
import numpy as np
from .base import BaseStrategy
from ..indicators import sma, ema, macd, bollinger_bands


class MACrossStrategy(BaseStrategy):
    """双均线金叉死叉策略。快线上穿慢线买入，下穿卖出。"""

    name = "MA金叉死叉"
    description = "快速均线上穿慢速均线时买入，下穿时卖出。适合趋势明显的行情。"

    def __init__(self, fast: int = 5, slow: int = 20, ma_type: str = "sma"):
        self.fast = fast
        self.slow = slow
        self.ma_type = ma_type  # "sma" or "ema"

    def get_params(self) -> dict:
        return {"fast": self.fast, "slow": self.slow, "ma_type": self.ma_type}

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        fn = sma if self.ma_type == "sma" else ema
        ma_fast = fn(close, self.fast)
        ma_slow = fn(close, self.slow)

        signals = pd.Series(0, index=df.index)
        cross_up = (ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1))
        cross_down = (ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))
        signals[cross_up] = 1
        signals[cross_down] = -1
        return signals


class MACDStrategy(BaseStrategy):
    """MACD 柱状图策略。柱状图由负转正买入，由正转负卖出。"""

    name = "MACD策略"
    description = "MACD 柱状图由负转正时买入，由正转负时卖出。适合中长线趋势判断。"

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def get_params(self) -> dict:
        return {"fast": self.fast, "slow": self.slow, "signal": self.signal}

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        _, _, hist = macd(df["close"], self.fast, self.slow, self.signal)

        signals = pd.Series(0, index=df.index)
        cross_up = (hist > 0) & (hist.shift(1) <= 0)
        cross_down = (hist < 0) & (hist.shift(1) >= 0)
        signals[cross_up] = 1
        signals[cross_down] = -1
        return signals


class BollingerBreakoutStrategy(BaseStrategy):
    """布林带突破策略。价格突破上轨买入，跌破下轨卖出。"""

    name = "布林带突破"
    description = "价格突破布林带上轨时买入（趋势延续），跌破下轨时卖出。"

    def __init__(self, window: int = 20, num_std: float = 2.0):
        self.window = window
        self.num_std = num_std

    def get_params(self) -> dict:
        return {"window": self.window, "num_std": self.num_std}

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        upper, middle, lower = bollinger_bands(close, self.window, self.num_std)

        signals = pd.Series(0, index=df.index)
        break_up = (close > upper) & (close.shift(1) <= upper.shift(1))
        break_down = (close < lower) & (close.shift(1) >= lower.shift(1))
        signals[break_up] = 1
        signals[break_down] = -1
        return signals


class TripleMAStrategy(BaseStrategy):
    """三均线策略。短期、中期、长期均线三线多头排列时买入。"""

    name = "三均线策略"
    description = "短、中、长三条均线多头排列（短>中>长）时持多，空头排列时清仓。"

    def __init__(self, short: int = 5, mid: int = 20, long: int = 60):
        self.short = short
        self.mid = mid
        self.long = long

    def get_params(self) -> dict:
        return {"short": self.short, "mid": self.mid, "long": self.long}

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        ma_s = sma(close, self.short)
        ma_m = sma(close, self.mid)
        ma_l = sma(close, self.long)

        bull = (ma_s > ma_m) & (ma_m > ma_l)
        bear = (ma_s < ma_m) & (ma_m < ma_l)

        signals = pd.Series(0, index=df.index)
        enter = bull & ~bull.shift(1).fillna(False)
        exit_ = bear & ~bear.shift(1).fillna(False)
        signals[enter] = 1
        signals[exit_] = -1
        return signals
