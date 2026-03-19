"""策略信号页：查看当前策略对指定股票的最新信号。"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data import fetcher
from core.strategies.trend import MACrossStrategy, MACDStrategy, BollingerBreakoutStrategy, TripleMAStrategy
from core.strategies.mean_reversion import RSIStrategy, BollingerReversionStrategy, MeanReversionMAStrategy
from core.strategies.volume_price import VolumeBreakoutStrategy, VolumeDivergenceStrategy, ShrinkageRetraceStrategy
from core.indicators import sma, ema, macd, rsi, bollinger_bands

STRATEGY_MAP = {
    "MA金叉死叉": MACrossStrategy,
    "MACD策略": MACDStrategy,
    "布林带突破": BollingerBreakoutStrategy,
    "三均线策略": TripleMAStrategy,
    "RSI均值回归": RSIStrategy,
    "布林带均值回归": BollingerReversionStrategy,
    "均线偏离回归": MeanReversionMAStrategy,
    "放量突破": VolumeBreakoutStrategy,
    "价量背离": VolumeDivergenceStrategy,
    "缩量回调": ShrinkageRetraceStrategy,
}

st.title("📈 策略信号")
st.caption("查看策略在指定股票上的最新信号与指标叠加图。")

col1, col2, col3 = st.columns(3)
with col1:
    symbol = st.text_input("股票代码", value="000001")
with col2:
    strategy_name = st.selectbox("策略", list(STRATEGY_MAP.keys()))
with col3:
    lookback = st.selectbox("回看天数", [60, 120, 250, 500], index=1)

if st.button("生成信号图", type="primary"):
    end = datetime.date.today()
    start = end - datetime.timedelta(days=lookback * 2)  # 多取些数据供指标预热

    with st.spinner("加载数据..."):
        try:
            df = fetcher.get_kline(
                symbol=symbol,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
            if df.empty:
                st.error("未获取到数据")
                st.stop()
            df = df.tail(lookback)
        except Exception as e:
            st.error(f"数据加载失败：{e}")
            st.stop()

    strategy = STRATEGY_MAP[strategy_name]()
    signals = strategy.generate_signals(df)

    # 最新信号提示
    latest_sig = signals.iloc[-1]
    latest_price = df["close"].iloc[-1]
    sig_text = {1: "🔴 买入信号", -1: "🟢 卖出信号", 0: "⚪ 无信号"}
    st.info(f"**{symbol}** 最新收盘价：**{latest_price:.2f}**　|　当前信号：**{sig_text.get(latest_sig, '无')}**")

    # 绘制主图 + 指标
    if strategy_name in ["MA金叉死叉", "三均线策略"]:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.75, 0.25], vertical_spacing=0.02)
        p = strategy.get_params()
        fast = p.get("fast", p.get("short", 5))
        slow = p.get("slow", p.get("mid", 20))
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="K线", increasing_line_color="#e63946", decreasing_line_color="#2a9d8f",
        ), row=1, col=1)
        fn = sma if p.get("ma_type", "sma") == "sma" else ema
        fig.add_trace(go.Scatter(x=df.index, y=fn(df["close"], fast),
                                 name=f"MA{fast}", line=dict(color="#f4a261", width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=fn(df["close"], slow),
                                 name=f"MA{slow}", line=dict(color="#457b9d", width=1.5)), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df["volume"], name="成交量",
                             marker_color="#adb5bd"), row=2, col=1)

    elif strategy_name == "MACD策略":
        p = strategy.get_params()
        ml, sl, hist = macd(df["close"], p["fast"], p["slow"], p["signal"])
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.6, 0.4], vertical_spacing=0.02)
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="K线", increasing_line_color="#e63946", decreasing_line_color="#2a9d8f",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=ml, name="MACD", line=dict(color="#e63946")), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=sl, name="Signal", line=dict(color="#457b9d")), row=2, col=1)
        colors = ["#e63946" if v >= 0 else "#2a9d8f" for v in hist]
        fig.add_trace(go.Bar(x=df.index, y=hist, name="Histogram", marker_color=colors), row=2, col=1)

    elif strategy_name in ["RSI均值回归"]:
        p = strategy.get_params()
        r = rsi(df["close"], p["window"])
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.6, 0.4], vertical_spacing=0.02)
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="K线", increasing_line_color="#e63946", decreasing_line_color="#2a9d8f",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=r, name="RSI", line=dict(color="#f4a261")), row=2, col=1)
        fig.add_hline(y=p["overbought"], line_dash="dash", line_color="#e63946", row=2, col=1)
        fig.add_hline(y=p["oversold"], line_dash="dash", line_color="#2a9d8f", row=2, col=1)

    else:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.75, 0.25], vertical_spacing=0.02)
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="K线", increasing_line_color="#e63946", decreasing_line_color="#2a9d8f",
        ), row=1, col=1)
        upper, mid, lower = bollinger_bands(df["close"])
        fig.add_trace(go.Scatter(x=df.index, y=upper, name="上轨", line=dict(color="#e63946", dash="dash", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=mid, name="中轨", line=dict(color="#adb5bd", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=lower, name="下轨", line=dict(color="#2a9d8f", dash="dash", width=1)), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df["volume"], name="成交量", marker_color="#adb5bd"), row=2, col=1)

    # 标注信号
    buy_idx = signals[signals == 1].index
    sell_idx = signals[signals == -1].index
    if len(buy_idx) > 0:
        fig.add_trace(go.Scatter(
            x=buy_idx, y=df.loc[buy_idx, "low"] * 0.98,
            mode="markers", marker=dict(symbol="triangle-up", size=10, color="#e63946"),
            name="买入",
        ), row=1, col=1)
    if len(sell_idx) > 0:
        fig.add_trace(go.Scatter(
            x=sell_idx, y=df.loc[sell_idx, "high"] * 1.02,
            mode="markers", marker=dict(symbol="triangle-down", size=10, color="#2a9d8f"),
            name="卖出",
        ), row=1, col=1)

    fig.update_layout(height=550, xaxis_rangeslider_visible=False,
                      margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

    # 最近 20 个信号
    recent_signals = signals[signals != 0].tail(20)
    if not recent_signals.empty:
        st.subheader("最近信号列表")
        sig_df = pd.DataFrame({
            "日期": recent_signals.index.date,
            "信号": recent_signals.map({1: "买入 🔴", -1: "卖出 🟢"}).values,
            "收盘价": df.loc[recent_signals.index, "close"].values,
        })
        st.dataframe(sig_df, use_container_width=True, hide_index=True)
