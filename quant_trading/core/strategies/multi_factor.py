"""
多因子选股策略。
对股票池（多只股票）按因子综合打分排名，选出排名靠前的股票持有。
因子：动量、波动率（低波动），结合 RSI 和均线趋势。
财务因子（PE/PB/ROE）作为可选增强层。
"""
import pandas as pd
import numpy as np
from typing import Dict, List
from ..indicators import momentum, rsi, sma


def _zscore(series: pd.Series) -> pd.Series:
    """Z-score 标准化，处理 NaN。"""
    mean = series.mean()
    std = series.std()
    if std == 0 or pd.isna(std):
        return pd.Series(0.0, index=series.index)
    return (series - mean) / std


class MultiFactorScorer:
    """
    多因子综合打分器。输入多只股票的最新 K 线快照，输出排名。

    支持的因子：
        momentum_20  : 20 日动量（越高越好）
        momentum_60  : 60 日动量（越高越好）
        volatility   : 20 日波动率（越低越好，取反）
        rsi_trend    : RSI 趋势强度（50-70 区间最佳，取 |RSI-60| 取反）
        ma_trend     : 价格/60日均线 比值（越高越好）
    """

    def __init__(
        self,
        weights: Dict[str, float] = None,
        top_n: int = 5,
    ):
        self.weights = weights or {
            "momentum_20": 0.30,
            "momentum_60": 0.25,
            "volatility": 0.20,
            "rsi_trend": 0.15,
            "ma_trend": 0.10,
        }
        self.top_n = top_n

    def score_stocks(self, stock_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Parameters
        ----------
        stock_data : dict
            {symbol: df} 其中 df 为该股票的日线 OHLCV DataFrame

        Returns
        -------
        pd.DataFrame
            columns: symbol, score, rank, momentum_20, momentum_60, volatility, rsi_trend, ma_trend
        """
        records = []
        for symbol, df in stock_data.items():
            if df is None or len(df) < 65:
                continue
            close = df["close"]
            try:
                mom20 = momentum(close, 20).iloc[-1]
                mom60 = momentum(close, 60).iloc[-1]
                vol20 = close.pct_change().rolling(20).std().iloc[-1]
                r = rsi(close, 14).iloc[-1]
                rsi_score = -(abs(r - 60))  # RSI 越接近 60 分越高
                ma60 = sma(close, 60).iloc[-1]
                ma_trend_val = close.iloc[-1] / ma60 - 1 if ma60 > 0 else 0
                records.append({
                    "symbol": symbol,
                    "momentum_20": mom20,
                    "momentum_60": mom60,
                    "volatility": -vol20,  # 越低波动越好，取负
                    "rsi_trend": rsi_score,
                    "ma_trend": ma_trend_val,
                })
            except Exception:
                continue

        if not records:
            return pd.DataFrame()

        df_score = pd.DataFrame(records).set_index("symbol")

        # Z-score 标准化各因子
        factor_cols = list(self.weights.keys())
        for col in factor_cols:
            if col in df_score.columns:
                df_score[f"z_{col}"] = _zscore(df_score[col])

        # 加权综合评分
        df_score["score"] = sum(
            self.weights.get(col, 0) * df_score[f"z_{col}"]
            for col in factor_cols
            if f"z_{col}" in df_score.columns
        )
        df_score["rank"] = df_score["score"].rank(ascending=False)
        df_score = df_score.sort_values("score", ascending=False).reset_index()
        return df_score

    def get_top_stocks(self, stock_data: Dict[str, pd.DataFrame]) -> List[str]:
        """返回评分最高的 top_n 只股票代码列表。"""
        scored = self.score_stocks(stock_data)
        if scored.empty:
            return []
        return scored.head(self.top_n)["symbol"].tolist()
