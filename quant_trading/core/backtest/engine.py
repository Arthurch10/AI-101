"""
向量化回测引擎（含 A 股特殊规则）。

A 股规则：
  - T+1：当日买入，次日才能卖出
  - 涨停不能买入（change_pct >= 9.9%），跌停不能卖出（change_pct <= -9.9%）
  - 手续费：买入 0.025%，卖出 0.025% + 印花税 0.1%
  - 最小交易单位：100 股（1 手）
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional
from .metrics import BacktestMetrics, calc_metrics


@dataclass
class BacktestConfig:
    initial_capital: float = 500_000.0
    commission_buy: float = 0.00025       # 买入佣金 0.025%
    commission_sell: float = 0.00025      # 卖出佣金 0.025%
    stamp_duty: float = 0.001             # 印花税 0.1%（仅卖出）
    slippage: float = 0.0                 # 滑点
    min_trade_unit: int = 100             # 最小交易单位（手）
    position_pct: float = 1.0            # 建仓时使用资金比例（0~1）
    limit_pct: float = 0.099             # 涨跌停判断阈值


@dataclass
class BacktestResult:
    config: BacktestConfig = None
    equity_curve: pd.Series = field(default_factory=pd.Series)
    trade_records: List[dict] = field(default_factory=list)
    metrics: BacktestMetrics = field(default_factory=BacktestMetrics)
    signals: pd.Series = field(default_factory=pd.Series)
    positions: pd.Series = field(default_factory=pd.Series)


class BacktestEngine:
    """
    单标的向量化回测引擎。

    使用方式：
        engine = BacktestEngine(config)
        result = engine.run(df, signals)
    """

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()

    def run(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        benchmark_df: Optional[pd.DataFrame] = None,
    ) -> BacktestResult:
        """
        Parameters
        ----------
        df : pd.DataFrame
            OHLCV 数据，DatetimeIndex，列含 open/high/low/close/volume/change_pct
        signals : pd.Series
            策略信号（+1/-1/0），与 df 同索引
        benchmark_df : pd.DataFrame, optional
            基准指数数据，用于计算 alpha
        """
        cfg = self.config
        df = df.copy()
        signals = signals.reindex(df.index).fillna(0)

        # 确保 change_pct 列存在（用于涨跌停检测）
        if "change_pct" not in df.columns:
            df["change_pct"] = df["close"].pct_change() * 100

        n = len(df)
        cash = cfg.initial_capital
        shares = 0              # 持有股数
        buy_date_idx = -999     # 买入时的 bar 索引（T+1 限制）
        cost_price = 0.0        # 持仓成本价

        equity = np.zeros(n)
        position_arr = np.zeros(n)
        trade_records = []

        for i in range(n):
            row = df.iloc[i]
            price = row["close"]
            change_pct = row.get("change_pct", 0)
            sig = signals.iloc[i]

            # 当日持仓市值 + 现金 = 账户净值
            equity[i] = cash + shares * price
            position_arr[i] = shares

            # 买入信号：无持仓 + 非涨停
            if sig == 1 and shares == 0 and change_pct < cfg.limit_pct * 100:
                invest = cash * cfg.position_pct
                # 按收盘价 + 滑点买入，取整到 100 手
                buy_price = price * (1 + cfg.slippage)
                max_shares = int(invest / buy_price / cfg.min_trade_unit) * cfg.min_trade_unit
                if max_shares > 0:
                    commission = max_shares * buy_price * cfg.commission_buy
                    total_cost = max_shares * buy_price + commission
                    if total_cost <= cash:
                        cash -= total_cost
                        shares = max_shares
                        cost_price = buy_price
                        buy_date_idx = i
                        trade_records.append({
                            "date": df.index[i],
                            "action": "buy",
                            "price": buy_price,
                            "shares": shares,
                            "commission": commission,
                            "pnl": 0.0,
                            "cash_after": cash,
                        })

            # 卖出信号：有持仓 + T+1 满足 + 非跌停
            elif sig == -1 and shares > 0 and (i - buy_date_idx) >= 1 and change_pct > -cfg.limit_pct * 100:
                sell_price = price * (1 - cfg.slippage)
                proceeds = shares * sell_price
                commission = proceeds * (cfg.commission_sell + cfg.stamp_duty)
                net_proceeds = proceeds - commission
                pnl = net_proceeds - shares * cost_price
                cash += net_proceeds
                trade_records.append({
                    "date": df.index[i],
                    "action": "sell",
                    "price": sell_price,
                    "shares": shares,
                    "commission": commission,
                    "pnl": pnl,
                    "cash_after": cash,
                    "hold_days": i - buy_date_idx,
                    "return_pct": pnl / (shares * cost_price) * 100,
                })
                shares = 0
                cost_price = 0.0
                buy_date_idx = -999

        # 最终强制平仓（若仍持仓）
        if shares > 0:
            final_price = df["close"].iloc[-1]
            proceeds = shares * final_price
            commission = proceeds * (self.config.commission_sell + self.config.stamp_duty)
            net_proceeds = proceeds - commission
            pnl = net_proceeds - shares * cost_price
            cash += net_proceeds
            trade_records.append({
                "date": df.index[-1],
                "action": "close",
                "price": final_price,
                "shares": shares,
                "commission": commission,
                "pnl": pnl,
                "cash_after": cash,
                "hold_days": n - 1 - buy_date_idx,
                "return_pct": pnl / (shares * cost_price) * 100,
            })
            equity[-1] = cash

        equity_series = pd.Series(equity, index=df.index, name="equity")
        position_series = pd.Series(position_arr, index=df.index, name="position")

        # 计算基准净值
        benchmark_curve = None
        if benchmark_df is not None and not benchmark_df.empty:
            bm = benchmark_df["close"].reindex(df.index).ffill()
            benchmark_curve = bm / bm.iloc[0] * cfg.initial_capital

        metrics = calc_metrics(equity_series, trade_records, benchmark_curve=benchmark_curve)

        return BacktestResult(
            config=cfg,
            equity_curve=equity_series,
            trade_records=trade_records,
            metrics=metrics,
            signals=signals,
            positions=position_series,
        )
