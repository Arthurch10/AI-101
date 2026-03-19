"""回测绩效指标计算。"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List


@dataclass
class BacktestMetrics:
    total_return: float = 0.0          # 总收益率
    annual_return: float = 0.0         # 年化收益率
    sharpe_ratio: float = 0.0          # Sharpe 比率（年化）
    max_drawdown: float = 0.0          # 最大回撤
    win_rate: float = 0.0              # 胜率
    profit_loss_ratio: float = 0.0     # 盈亏比
    total_trades: int = 0              # 总交易次数
    profit_trades: int = 0             # 盈利交易次数
    loss_trades: int = 0               # 亏损交易次数
    avg_profit: float = 0.0            # 平均盈利
    avg_loss: float = 0.0              # 平均亏损
    volatility: float = 0.0            # 年化波动率
    calmar_ratio: float = 0.0          # Calmar 比率
    total_commission: float = 0.0      # 总手续费
    benchmark_return: float = 0.0      # 基准收益率（上证指数）
    alpha: float = 0.0                 # Alpha
    trade_details: List[dict] = field(default_factory=list)  # 逐笔交易记录


def calc_metrics(
    equity_curve: pd.Series,
    trade_records: List[dict],
    risk_free_rate: float = 0.03,
    benchmark_curve: pd.Series = None,
) -> BacktestMetrics:
    """
    计算回测绩效指标。

    Parameters
    ----------
    equity_curve : pd.Series
        每日账户净值序列（DatetimeIndex）
    trade_records : list of dict
        每笔交易记录，含 pnl 字段
    risk_free_rate : float
        年化无风险利率（默认 3%）
    benchmark_curve : pd.Series, optional
        基准净值序列
    """
    m = BacktestMetrics()
    if equity_curve.empty or len(equity_curve) < 2:
        return m

    # 收益率序列
    returns = equity_curve.pct_change().dropna()
    m.total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1

    # 年化收益率（假设一年 252 个交易日）
    n_days = len(equity_curve)
    m.annual_return = (1 + m.total_return) ** (252 / n_days) - 1

    # 年化波动率
    m.volatility = returns.std() * np.sqrt(252)

    # Sharpe 比率
    daily_rf = risk_free_rate / 252
    excess_return = returns - daily_rf
    if excess_return.std() > 0:
        m.sharpe_ratio = (excess_return.mean() / excess_return.std()) * np.sqrt(252)

    # 最大回撤
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max
    m.max_drawdown = drawdown.min()

    # Calmar 比率
    if abs(m.max_drawdown) > 0:
        m.calmar_ratio = m.annual_return / abs(m.max_drawdown)

    # 交易统计
    m.total_trades = len(trade_records)
    m.trade_details = trade_records
    if trade_records:
        pnls = [t.get("pnl", 0) for t in trade_records]
        profits = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        m.profit_trades = len(profits)
        m.loss_trades = len(losses)
        m.win_rate = m.profit_trades / m.total_trades if m.total_trades > 0 else 0
        m.avg_profit = np.mean(profits) if profits else 0
        m.avg_loss = np.mean(losses) if losses else 0
        if abs(m.avg_loss) > 0:
            m.profit_loss_ratio = abs(m.avg_profit / m.avg_loss)

    # 基准对比
    if benchmark_curve is not None and not benchmark_curve.empty:
        m.benchmark_return = (benchmark_curve.iloc[-1] / benchmark_curve.iloc[0]) - 1
        m.alpha = m.annual_return - m.benchmark_return

    m.total_commission = sum(t.get("commission", 0) for t in trade_records)
    return m


def calc_drawdown_series(equity_curve: pd.Series) -> pd.Series:
    """计算回撤序列，用于绘图。"""
    rolling_max = equity_curve.cummax()
    return (equity_curve - rolling_max) / rolling_max
