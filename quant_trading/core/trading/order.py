"""订单与交易数据模型。"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class OrderDirection(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderType(str, Enum):
    MARKET = "market"     # 市价单
    LIMIT = "limit"       # 限价单


@dataclass
class Order:
    order_id: str
    symbol: str
    direction: OrderDirection
    order_type: OrderType
    quantity: int                       # 委托数量（股）
    price: float = 0.0                  # 委托价格（市价单为 0）
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: int = 0
    filled_price: float = 0.0
    commission: float = 0.0
    create_time: datetime = field(default_factory=datetime.now)
    fill_time: Optional[datetime] = None
    note: str = ""

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def pnl(self) -> float:
        """仅对卖出单有意义，需外部计算后赋值。"""
        return 0.0


@dataclass
class Position:
    symbol: str
    quantity: int              # 持有股数
    cost_price: float          # 成本价（买入均价）
    buy_date: datetime         # 最后一次买入日期
    name: str = ""

    @property
    def can_sell_today(self) -> bool:
        """A 股 T+1：当日买入不能当日卖出。"""
        today = datetime.now().date()
        return self.buy_date.date() < today

    def market_value(self, current_price: float) -> float:
        return self.quantity * current_price

    def unrealized_pnl(self, current_price: float) -> float:
        return (current_price - self.cost_price) * self.quantity

    def unrealized_pnl_pct(self, current_price: float) -> float:
        if self.cost_price == 0:
            return 0.0
        return (current_price - self.cost_price) / self.cost_price


@dataclass
class AccountInfo:
    total_assets: float        # 总资产
    cash: float                # 可用现金
    market_value: float        # 持仓市值
    frozen_cash: float = 0.0   # 冻结资金
    daily_pnl: float = 0.0     # 当日盈亏
    total_pnl: float = 0.0     # 总盈亏
