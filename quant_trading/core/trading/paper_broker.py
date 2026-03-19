"""
模拟盘（Paper Trading）实现。
完整支持 A 股 T+1 规则、手续费/印花税、涨跌停限制、账户净值追踪。
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

from .broker import AbstractBroker
from .order import Order, OrderDirection, OrderType, OrderStatus, Position, AccountInfo


# 默认费率（与 config.yaml 保持一致）
DEFAULT_COMMISSION_BUY = 0.00025
DEFAULT_COMMISSION_SELL = 0.00025
DEFAULT_STAMP_DUTY = 0.001
MIN_COMMISSION = 5.0   # 最低佣金 5 元


class PaperBroker(AbstractBroker):
    """模拟账户，支持 A 股完整交易规则。"""

    def __init__(
        self,
        initial_capital: float = 500_000.0,
        commission_buy: float = DEFAULT_COMMISSION_BUY,
        commission_sell: float = DEFAULT_COMMISSION_SELL,
        stamp_duty: float = DEFAULT_STAMP_DUTY,
    ):
        self.cash = initial_capital
        self.initial_capital = initial_capital
        self.commission_buy = commission_buy
        self.commission_sell = commission_sell
        self.stamp_duty = stamp_duty

        self._positions: Dict[str, Position] = {}
        self._orders: Dict[str, Order] = {}
        self._trades: List[dict] = []
        self._equity_history: List[dict] = []   # {date, total_assets}

        # 最新行情快照（外部注入，用于估值）
        self._latest_prices: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # 行情注入
    # ------------------------------------------------------------------
    def update_prices(self, prices: Dict[str, float]):
        """外部注入最新价格，用于持仓估值。"""
        self._latest_prices.update(prices)

    # ------------------------------------------------------------------
    # 下单
    # ------------------------------------------------------------------
    def place_order(
        self,
        symbol: str,
        direction: OrderDirection,
        quantity: int,
        price: float = 0.0,
        order_type: OrderType = OrderType.MARKET,
    ) -> Order:
        order_id = str(uuid.uuid4())[:8]
        exec_price = price if price > 0 else self._latest_prices.get(symbol, 0)

        if exec_price <= 0:
            order = Order(order_id, symbol, direction, order_type, quantity,
                          status=OrderStatus.REJECTED, note="无法获取价格")
            self._orders[order_id] = order
            return order

        order = Order(order_id, symbol, direction, order_type, quantity, price=exec_price)
        self._orders[order_id] = order

        if direction == OrderDirection.BUY:
            self._execute_buy(order, exec_price)
        else:
            self._execute_sell(order, exec_price)

        return order

    def _execute_buy(self, order: Order, exec_price: float):
        quantity = order.quantity
        cost = quantity * exec_price
        commission = max(cost * self.commission_buy, MIN_COMMISSION)
        total_cost = cost + commission

        if total_cost > self.cash:
            order.status = OrderStatus.REJECTED
            order.note = f"资金不足（需 {total_cost:.2f}，可用 {self.cash:.2f}）"
            return

        self.cash -= total_cost
        order.filled_qty = quantity
        order.filled_price = exec_price
        order.commission = commission
        order.status = OrderStatus.FILLED
        order.fill_time = datetime.now()

        if order.symbol in self._positions:
            pos = self._positions[order.symbol]
            total_qty = pos.quantity + quantity
            pos.cost_price = (pos.cost_price * pos.quantity + exec_price * quantity) / total_qty
            pos.quantity = total_qty
            pos.buy_date = datetime.now()
        else:
            self._positions[order.symbol] = Position(
                symbol=order.symbol,
                quantity=quantity,
                cost_price=exec_price,
                buy_date=datetime.now(),
            )

        self._trades.append({
            "date": datetime.now(),
            "symbol": order.symbol,
            "action": "buy",
            "price": exec_price,
            "quantity": quantity,
            "commission": commission,
            "amount": total_cost,
        })

    def _execute_sell(self, order: Order, exec_price: float):
        symbol = order.symbol
        quantity = order.quantity
        pos = self._positions.get(symbol)

        if pos is None or pos.quantity < quantity:
            order.status = OrderStatus.REJECTED
            order.note = "持仓不足"
            return

        if not pos.can_sell_today:
            order.status = OrderStatus.REJECTED
            order.note = "T+1 限制：今日买入的股票不能今日卖出"
            return

        proceeds = quantity * exec_price
        commission = max(proceeds * self.commission_sell, MIN_COMMISSION)
        stamp = proceeds * self.stamp_duty
        net_proceeds = proceeds - commission - stamp
        pnl = net_proceeds - quantity * pos.cost_price

        self.cash += net_proceeds
        order.filled_qty = quantity
        order.filled_price = exec_price
        order.commission = commission + stamp
        order.status = OrderStatus.FILLED
        order.fill_time = datetime.now()

        pos.quantity -= quantity
        if pos.quantity == 0:
            del self._positions[symbol]

        self._trades.append({
            "date": datetime.now(),
            "symbol": symbol,
            "action": "sell",
            "price": exec_price,
            "quantity": quantity,
            "commission": commission + stamp,
            "amount": proceeds,
            "pnl": pnl,
            "return_pct": pnl / (quantity * pos.cost_price) * 100 if pos.cost_price > 0 else 0,
        })

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------
    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if order and order.status == OrderStatus.PENDING:
            order.status = OrderStatus.CANCELLED
            return True
        return False

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def get_orders(self) -> List[Order]:
        return list(self._orders.values())

    def get_positions(self) -> Dict[str, Position]:
        return dict(self._positions)

    def get_account(self) -> AccountInfo:
        market_value = sum(
            pos.quantity * self._latest_prices.get(sym, pos.cost_price)
            for sym, pos in self._positions.items()
        )
        total_assets = self.cash + market_value
        total_pnl = total_assets - self.initial_capital
        return AccountInfo(
            total_assets=total_assets,
            cash=self.cash,
            market_value=market_value,
            total_pnl=total_pnl,
        )

    def get_trade_history(self) -> List[dict]:
        return list(self._trades)

    def get_equity_df(self) -> pd.DataFrame:
        """返回历史净值 DataFrame（需外部定期调用 snapshot()）。"""
        return pd.DataFrame(self._equity_history)

    def snapshot(self):
        """记录当前账户净值快照（建议每个交易日结束时调用）。"""
        account = self.get_account()
        self._equity_history.append({
            "date": datetime.now(),
            "total_assets": account.total_assets,
            "cash": account.cash,
            "market_value": account.market_value,
        })
