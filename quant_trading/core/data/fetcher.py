"""AKShare 封装层，提供统一的数据获取接口，并写入 SQLite 缓存。"""
import pandas as pd
import akshare as ak
from datetime import datetime, timedelta
from . import cache


def get_stock_list() -> pd.DataFrame:
    """获取 A 股全部股票列表（代码 + 名称）。有缓存则使用缓存。"""
    if cache.is_stock_list_fresh(hours=24):
        df = cache.load_stock_list()
        if not df.empty:
            return df
    try:
        df = ak.stock_info_a_code_name()
        df = df.rename(columns={"code": "code", "name": "name"})
        # 字段标准化
        if "股票代码" in df.columns:
            df = df.rename(columns={"股票代码": "code", "股票简称": "name"})
        cache.save_stock_list(df[["code", "name"]])
        cache.mark_stock_list_updated()
        return df[["code", "name"]]
    except Exception as e:
        cached = cache.load_stock_list()
        if not cached.empty:
            return cached
        raise RuntimeError(f"获取股票列表失败: {e}")


def get_kline(
    symbol: str,
    start_date: str,
    end_date: str,
    period: str = "daily",
    adjust: str = "qfq",
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    获取 A 股历史 K 线数据。

    symbol: 6 位股票代码，如 "000001"
    start_date / end_date: "YYYYMMDD" 格式
    adjust: "qfq"=前复权, "hfq"=后复权, ""=不复权
    返回 DataFrame，index 为日期，列：open/high/low/close/volume/turnover/change_pct
    """
    # 先尝试从缓存读取（仅 daily + qfq 缓存）
    if use_cache and period == "daily" and adjust == "qfq":
        cached = cache.load_kline(symbol, start_date[:4] + "-" + start_date[4:6] + "-" + start_date[6:],
                                   end_date[:4] + "-" + end_date[4:6] + "-" + end_date[6:])
        # 简单判断：缓存数据是否覆盖了所需范围
        if not cached.empty:
            min_d, max_d = cache.get_cached_date_range(symbol)
            req_start = pd.Timestamp(start_date)
            req_end = pd.Timestamp(end_date)
            if min_d and max_d:
                if pd.Timestamp(min_d) <= req_start and pd.Timestamp(max_d) >= req_end:
                    return cached

    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
    except Exception as e:
        raise RuntimeError(f"获取 {symbol} K 线失败: {e}")

    if df is None or df.empty:
        return pd.DataFrame()

    # 列名标准化（AKShare 返回中文列名）
    col_map = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "turnover",
        "涨跌幅": "change_pct",
        "振幅": "amplitude",
        "换手率": "turnover_rate",
    }
    df = df.rename(columns=col_map)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df = df[["open", "high", "low", "close", "volume", "turnover", "change_pct"]].copy()
    df = df.astype(float)

    # 写入缓存
    if period == "daily" and adjust == "qfq":
        cache_df = df.reset_index().rename(columns={"index": "date"})
        cache.save_kline(symbol, cache_df)

    return df


def get_realtime_quotes() -> pd.DataFrame:
    """
    获取全市场 A 股实时行情快照。
    返回 DataFrame，含：code, name, price, change_pct, volume, amount, pe, pb
    """
    try:
        df = ak.stock_zh_a_spot_em()
    except Exception as e:
        raise RuntimeError(f"获取实时行情失败: {e}")

    col_map = {
        "代码": "code",
        "名称": "name",
        "最新价": "price",
        "涨跌幅": "change_pct",
        "涨跌额": "change_amount",
        "成交量": "volume",
        "成交额": "amount",
        "市盈率-动态": "pe",
        "市净率": "pb",
        "总市值": "market_cap",
        "流通市值": "float_cap",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    keep = [c for c in ["code", "name", "price", "change_pct", "change_amount",
                         "volume", "amount", "pe", "pb", "market_cap", "float_cap"] if c in df.columns]
    return df[keep].copy()


def get_index_kline(
    symbol: str = "000001",  # 上证指数
    start_date: str = "20200101",
    end_date: str = None,
    period: str = "daily",
) -> pd.DataFrame:
    """获取指数历史 K 线数据。"""
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")
    try:
        df = ak.index_zh_a_hist(symbol=symbol, period=period,
                                 start_date=start_date, end_date=end_date)
    except Exception as e:
        raise RuntimeError(f"获取指数 {symbol} 数据失败: {e}")

    col_map = {
        "日期": "date", "开盘": "open", "收盘": "close",
        "最高": "high", "最低": "low", "成交量": "volume",
        "成交额": "turnover", "涨跌幅": "change_pct",
    }
    df = df.rename(columns=col_map)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    cols = [c for c in ["open", "high", "low", "close", "volume", "turnover", "change_pct"] if c in df.columns]
    return df[cols].astype(float)


def get_stock_financial(symbol: str) -> pd.DataFrame:
    """获取股票财务摘要（用于多因子选股）。"""
    try:
        df = ak.stock_financial_abstract(stock=symbol)
        return df
    except Exception:
        return pd.DataFrame()


def get_stock_info(symbol: str) -> dict:
    """获取股票基本信息。"""
    try:
        df = ak.stock_individual_info_em(symbol=symbol)
        if df is not None and not df.empty:
            result = {}
            for _, row in df.iterrows():
                result[row.iloc[0]] = row.iloc[1]
            return result
    except Exception:
        pass
    return {}
