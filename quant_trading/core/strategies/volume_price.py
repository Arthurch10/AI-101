"""量价策略：放量突破、价量背离、缩量回调买点。"""
import pandas as pd
import numpy as np
from .base import BaseStrategy
from ..indicators import sma, volume_ma


class VolumeBreakoutStrategy(BaseStrategy):
    """放量突破策略。价格突破近期高点且成交量显著放大时买入。"""

    name = "放量突破"
    description = "价格突破 N 日高点且成交量 ≥ 均量 * vol_ratio 倍时买入，跌破 N 日低点时卖出。"

    def __init__(self, price_window: int = 20, vol_window: int = 10, vol_ratio: float = 2.0):
        self.price_window = price_window
        self.vol_window = vol_window
        self.vol_ratio = vol_ratio

    def get_params(self) -> dict:
        return {
            "price_window": self.price_window,
            "vol_window": self.vol_window,
            "vol_ratio": self.vol_ratio,
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        prev_high = high.rolling(self.price_window).max().shift(1)
        prev_low = low.rolling(self.price_window).min().shift(1)
        vol_avg = volume_ma(volume, self.vol_window).shift(1)

        signals = pd.Series(0, index=df.index)
        breakout_up = (close > prev_high) & (volume > vol_avg * self.vol_ratio)
        breakout_down = close < prev_low
        signals[breakout_up] = 1
        signals[breakout_down] = -1
        return signals


class VolumeDivergenceStrategy(BaseStrategy):
    """价量背离策略。价格新高但成交量萎缩（顶背离卖出），价格新低但成交量萎缩（底背离买入）。"""

    name = "价量背离"
    description = "价格创新高但成交量未创新高（顶背离）时卖出；价格创新低但成交量未创新低（底背离）时买入。"

    def __init__(self, window: int = 10):
        self.window = window

    def get_params(self) -> dict:
        return {"window": self.window}

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        volume = df["volume"]

        price_high = close.rolling(self.window).max()
        vol_high = volume.rolling(self.window).max()
        price_low = close.rolling(self.window).min()
        vol_low = volume.rolling(self.window).min()

        # 底背离：价格创新低，但成交量未创新低（说明卖盘减弱）
        bottom_div = (close == price_low) & (volume > vol_low * 1.1)
        # 顶背离：价格创新高，但成交量未创新高（说明买盘减弱）
        top_div = (close == price_high) & (volume < vol_high * 0.8)

        signals = pd.Series(0, index=df.index)
        signals[bottom_div] = 1
        signals[top_div] = -1
        return signals


class ShrinkageRetraceStrategy(BaseStrategy):
    """缩量回调买点策略。上涨趋势中，出现缩量回调后放量恢复上涨时买入。"""

    name = "缩量回调"
    description = "在均线多头排列的背景下，出现连续 shrink_days 天缩量回调后，放量反弹时买入。"

    def __init__(self, trend_window: int = 20, shrink_days: int = 3, vol_recover_ratio: float = 1.5):
        self.trend_window = trend_window
        self.shrink_days = shrink_days
        self.vol_recover_ratio = vol_recover_ratio

    def get_params(self) -> dict:
        return {
            "trend_window": self.trend_window,
            "shrink_days": self.shrink_days,
            "vol_recover_ratio": self.vol_recover_ratio,
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        volume = df["volume"]

        ma = sma(close, self.trend_window)
        in_uptrend = close > ma

        vol_avg = volume_ma(volume, 10)
        vol_shrink = volume < vol_avg * 0.8
        # 连续 shrink_days 天缩量
        shrink_streak = vol_shrink.rolling(self.shrink_days).sum() == self.shrink_days
        # 今日放量且价格上涨
        vol_recover = (volume > vol_avg * self.vol_recover_ratio) & (close > close.shift(1))

        signals = pd.Series(0, index=df.index)
        buy = in_uptrend & shrink_streak.shift(1).fillna(False) & vol_recover
        signals[buy] = 1

        # 跌破均线卖出
        sell = (close < ma) & (close.shift(1) >= ma.shift(1))
        signals[sell] = -1
        return signals
