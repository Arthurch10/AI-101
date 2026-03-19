"""抽象券商接口，方便未来接入真实券商 API（如东方财富、华泰等）。"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from .order import Order, OrderDirection, OrderType, Position, AccountInfo


class AbstractBroker(ABC):
    """
    所有券商适配器的基类。

    实盘接入指引：
        - 东方财富（eitrade）：可通过 eitrade SDK 接入
        - 华泰证券：提供 XTP SDK（机构客户）
        - 通用方案：通过 easytrader 库对接同花顺/通达信客户端
          pip install easytrader

    本项目默认使用 PaperBroker（模拟盘），
    若需接入真实券商，继承本类并实现所有抽象方法即可。
    """

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        direction: OrderDirection,
        quantity: int,
        price: float = 0.0,
        order_type: OrderType = OrderType.MARKET,
    ) -> Order:
        """下单。"""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """撤单。"""

    @abstractmethod
    def get_order(self, order_id: str) -> Optional[Order]:
        """查询订单状态。"""

    @abstractmethod
    def get_orders(self) -> List[Order]:
        """查询所有订单。"""

    @abstractmethod
    def get_positions(self) -> Dict[str, Position]:
        """查询持仓，返回 {symbol: Position}。"""

    @abstractmethod
    def get_account(self) -> AccountInfo:
        """查询账户资金。"""

    @abstractmethod
    def get_trade_history(self) -> List[dict]:
        """查询历史成交记录。"""
