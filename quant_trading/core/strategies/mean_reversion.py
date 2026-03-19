"""均值回归策略：RSI 超买超卖、布林带均值回归。"""
import pandas as pd
from .base import BaseStrategy
from ..indicators import rsi, bollinger_bands, sma


class RSIStrategy(BaseStrategy):
    """RSI 均值回归策略。RSI 跌至超卖区买入，升至超买区卖出。"""

    name = "RSI均值回归"
    description = "RSI 跌入超卖区（默认 30 以下）时买入，升入超买区（默认 70 以上）时卖出。"

    def __init__(self, window: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        self.window = window
        self.oversold = oversold
        self.overbought = overbought

    def get_params(self) -> dict:
        return {"window": self.window, "oversold": self.oversold, "overbought": self.overbought}

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        r = rsi(df["close"], self.window)

        signals = pd.Series(0, index=df.index)
        # 超卖回升：RSI 从低于 oversold 回升到上方
        cross_up = (r > self.oversold) & (r.shift(1) <= self.oversold)
        # 超买回落：RSI 从高于 overbought 回落到下方
        cross_down = (r < self.overbought) & (r.shift(1) >= self.overbought)
        signals[cross_up] = 1
        signals[cross_down] = -1
        return signals


class BollingerReversionStrategy(BaseStrategy):
    """布林带均值回归策略。价格触及下轨后回归中轨买入，触及上轨后回归中轨卖出。"""

    name = "布林带均值回归"
    description = "价格跌至布林带下轨时买入（等待均值回归），涨至上轨时卖出。"

    def __init__(self, window: int = 20, num_std: float = 2.0):
        self.window = window
        self.num_std = num_std

    def get_params(self) -> dict:
        return {"window": self.window, "num_std": self.num_std}

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        upper, middle, lower = bollinger_bands(close, self.window, self.num_std)

        signals = pd.Series(0, index=df.index)
        # 价格触及或跌破下轨
        touch_lower = close <= lower
        # 价格触及或突破上轨
        touch_upper = close >= upper

        buy_signal = touch_lower & ~touch_lower.shift(1).fillna(False)
        sell_signal = touch_upper & ~touch_upper.shift(1).fillna(False)
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        return signals


class MeanReversionMAStrategy(BaseStrategy):
    """价格偏离均线后回归策略。价格严重低于均线时买入。"""

    name = "均线偏离回归"
    description = "价格大幅低于 N 日均线（超过 threshold）时买入，回归均线时卖出。"

    def __init__(self, window: int = 20, threshold: float = 0.05):
        self.window = window
        self.threshold = threshold  # 偏离阈值，如 0.05 = 5%

    def get_params(self) -> dict:
        return {"window": self.window, "threshold": self.threshold}

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        ma = sma(close, self.window)
        deviation = (close - ma) / ma  # 偏离比例

        signals = pd.Series(0, index=df.index)
        oversold = deviation < -self.threshold
        overbought = deviation > self.threshold

        buy = oversold & ~oversold.shift(1).fillna(False)
        sell = overbought & ~overbought.shift(1).fillna(False)
        signals[buy] = 1
        signals[sell] = -1
        return signals
