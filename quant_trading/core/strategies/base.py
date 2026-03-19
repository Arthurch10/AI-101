"""策略基类，所有策略均继承此类。"""
from abc import ABC, abstractmethod
import pandas as pd


class BaseStrategy(ABC):
    """
    策略基类。子类实现 generate_signals() 方法。

    信号约定：
        +1  = 买入信号
        -1  = 卖出信号
         0  = 无操作
    """

    name: str = "BaseStrategy"
    description: str = ""

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        根据 OHLCV 数据生成交易信号。

        Parameters
        ----------
        df : pd.DataFrame
            包含 open/high/low/close/volume 列，DatetimeIndex

        Returns
        -------
        pd.Series
            信号序列（+1 / -1 / 0），与 df 同索引
        """

    def get_params(self) -> dict:
        """返回当前策略参数，供 UI 展示和调整。"""
        return {}

    def set_params(self, **kwargs):
        """批量设置参数。"""
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def __repr__(self):
        return f"{self.name}({self.get_params()})"
