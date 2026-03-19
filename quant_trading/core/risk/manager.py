"""风险管理器：仓位控制、止损止盈、最大回撤熔断。"""
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import math


@dataclass
class RiskConfig:
    max_position_pct: float = 0.20     # 单股最大仓位占总资产比例
    stop_loss_pct: float = 0.08        # 止损线（持仓亏损达到此比例时触发）
    take_profit_pct: float = 0.20      # 止盈线
    max_drawdown_limit: float = 0.15   # 账户最大回撤熔断线
    max_stocks: int = 5                # 最多同时持有只数
    min_trade_unit: int = 100          # 最小交易单位（股）
    position_method: str = "fixed"     # "fixed"=固定比例, "kelly"=Kelly 公式


class RiskManager:
    """
    风控管理器。

    集成到交易流程：
        1. 下单前调用 check_buy_order() 验证仓位上限
        2. 每个 bar 调用 check_stop_loss() 检查止损止盈
        3. 定期调用 check_max_drawdown() 检查账户回撤
    """

    def __init__(self, config: RiskConfig = None):
        self.config = config or RiskConfig()
        self._peak_equity: float = 0.0    # 历史最高净值（用于回撤计算）

    def calc_position_size(
        self,
        total_assets: float,
        price: float,
        win_rate: float = 0.5,
        avg_profit: float = 0.1,
        avg_loss: float = 0.05,
    ) -> int:
        """
        计算建议买入股数。

        fixed 方法：使用 max_position_pct 的资金，向下取整到 min_trade_unit。
        kelly 方法：Kelly 公式计算最优仓位比例。
        """
        cfg = self.config
        if cfg.position_method == "kelly":
            if avg_loss <= 0:
                frac = cfg.max_position_pct
            else:
                odds = avg_profit / avg_loss
                kelly_f = (win_rate * odds - (1 - win_rate)) / odds
                kelly_f = max(0, min(kelly_f, cfg.max_position_pct))
                frac = kelly_f * 0.5  # 半 Kelly，更保守
        else:
            frac = cfg.max_position_pct

        invest_amount = total_assets * frac
        shares = int(invest_amount / price / cfg.min_trade_unit) * cfg.min_trade_unit
        return max(shares, 0)

    def check_buy_order(
        self,
        symbol: str,
        quantity: int,
        price: float,
        total_assets: float,
        current_positions: Dict[str, object],
    ) -> Tuple[bool, str]:
        """
        买单风控检查。

        Returns
        -------
        (passed: bool, reason: str)
        """
        cfg = self.config

        # 持仓只数检查
        if symbol not in current_positions and len(current_positions) >= cfg.max_stocks:
            return False, f"持仓已达上限 {cfg.max_stocks} 只，不允许新建仓位"

        # 单股仓位上限检查
        order_value = quantity * price
        max_allowed = total_assets * cfg.max_position_pct
        if order_value > max_allowed:
            return False, f"买入金额 {order_value:.0f} 超过单股仓位上限 {max_allowed:.0f}"

        return True, "通过"

    def check_stop_loss(
        self,
        positions: Dict[str, object],
        current_prices: Dict[str, float],
    ) -> Dict[str, str]:
        """
        检查所有持仓是否触及止损/止盈。

        Returns
        -------
        dict: {symbol: "stop_loss" | "take_profit"} 需要平仓的列表
        """
        actions = {}
        cfg = self.config
        for symbol, pos in positions.items():
            price = current_prices.get(symbol)
            if price is None or pos.cost_price <= 0:
                continue
            ret = (price - pos.cost_price) / pos.cost_price
            if ret <= -cfg.stop_loss_pct:
                actions[symbol] = "stop_loss"
            elif ret >= cfg.take_profit_pct:
                actions[symbol] = "take_profit"
        return actions

    def check_max_drawdown(self, current_equity: float) -> Tuple[bool, float]:
        """
        检查账户是否触发最大回撤熔断。

        Returns
        -------
        (triggered: bool, current_drawdown: float)
        """
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity
        if self._peak_equity <= 0:
            return False, 0.0
        drawdown = (self._peak_equity - current_equity) / self._peak_equity
        triggered = drawdown >= self.config.max_drawdown_limit
        return triggered, drawdown

    def reset_peak(self, equity: float):
        """重置历史最高净值。"""
        self._peak_equity = equity
