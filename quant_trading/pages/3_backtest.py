"""策略回测页：选择策略和参数，查看回测结果与图表。"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data import fetcher
from core.backtest.engine import BacktestEngine, BacktestConfig
from core.strategies.trend import MACrossStrategy, MACDStrategy, BollingerBreakoutStrategy, TripleMAStrategy
from core.strategies.mean_reversion import RSIStrategy, BollingerReversionStrategy, MeanReversionMAStrategy
from core.strategies.volume_price import VolumeBreakoutStrategy, VolumeDivergenceStrategy, ShrinkageRetraceStrategy

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

st.title("🔬 策略回测")

# ------------------------------------------------------------------
# 参数配置
# ------------------------------------------------------------------
with st.sidebar:
    st.header("回测参数")
    symbol = st.text_input("股票代码", value="000001")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("起始日期", value=datetime.date(2021, 1, 1))
    with col2:
        end_date = st.date_input("截止日期", value=datetime.date.today())

    strategy_name = st.selectbox("选择策略", list(STRATEGY_MAP.keys()))
    st.subheader("策略参数")

    strategy_cls = STRATEGY_MAP[strategy_name]
    strategy_obj = strategy_cls()
    params = strategy_obj.get_params()
    new_params = {}
    for k, v in params.items():
        if isinstance(v, bool):
            new_params[k] = st.checkbox(k, value=v)
        elif isinstance(v, int):
            new_params[k] = st.number_input(k, value=v, step=1, min_value=1)
        elif isinstance(v, float):
            new_params[k] = st.number_input(k, value=v, step=0.01, format="%.3f")
        elif isinstance(v, str):
            new_params[k] = st.selectbox(k, ["sma", "ema"], index=0 if v == "sma" else 1)

    st.subheader("资金设置")
    initial_capital = st.number_input("初始资金（元）", value=500000, step=10000, min_value=10000)
    position_pct = st.slider("建仓比例", min_value=0.1, max_value=1.0, value=0.95, step=0.05)

    run_btn = st.button("▶ 运行回测", type="primary", use_container_width=True)

# ------------------------------------------------------------------
# 运行回测
# ------------------------------------------------------------------
if run_btn:
    with st.spinner("正在加载数据并运行回测..."):
        try:
            df = fetcher.get_kline(
                symbol=symbol,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
            if df.empty:
                st.error("未获取到数据，请检查股票代码或日期范围。")
                st.stop()

            # 创建策略并设置参数
            strategy = strategy_cls()
            strategy.set_params(**new_params)
            signals = strategy.generate_signals(df)

            # 加载基准（上证指数）
            try:
                bm_df = fetcher.get_index_kline(
                    symbol="000001",
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                )
            except Exception:
                bm_df = None

            # 运行回测
            cfg = BacktestConfig(
                initial_capital=initial_capital,
                position_pct=position_pct,
            )
            engine = BacktestEngine(cfg)
            result = engine.run(df, signals, benchmark_df=bm_df)
            m = result.metrics

            st.session_state["backtest_result"] = result
            st.session_state["backtest_df"] = df
            st.session_state["backtest_bm"] = bm_df

        except Exception as e:
            st.error(f"回测失败：{e}")
            st.stop()

# ------------------------------------------------------------------
# 展示结果
# ------------------------------------------------------------------
if "backtest_result" in st.session_state:
    result = st.session_state["backtest_result"]
    df = st.session_state["backtest_df"]
    bm_df = st.session_state.get("backtest_bm")
    m = result.metrics

    # 关键指标
    st.subheader("📊 绩效概览")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("总收益率", f"{m.total_return*100:.2f}%",
              delta_color="normal" if m.total_return >= 0 else "inverse")
    c2.metric("年化收益率", f"{m.annual_return*100:.2f}%")
    c3.metric("Sharpe 比率", f"{m.sharpe_ratio:.2f}")
    c4.metric("最大回撤", f"{m.max_drawdown*100:.2f}%",
              delta_color="inverse")
    c5.metric("胜率", f"{m.win_rate*100:.1f}%")
    c6.metric("总交易次数", str(m.total_trades))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("盈亏比", f"{m.profit_loss_ratio:.2f}")
    c2.metric("年化波动率", f"{m.volatility*100:.2f}%")
    c3.metric("Calmar 比率", f"{m.calmar_ratio:.2f}")
    c4.metric("总手续费", f"¥{m.total_commission:.2f}")

    # ------------------------------------------------------------------
    # 净值曲线 + 基准对比
    # ------------------------------------------------------------------
    st.subheader("📈 净值曲线")
    fig = go.Figure()
    norm_equity = result.equity_curve / result.equity_curve.iloc[0]
    fig.add_trace(go.Scatter(x=norm_equity.index, y=norm_equity.values,
                             name="策略净值", line=dict(color="#e63946", width=2)))
    if bm_df is not None and not bm_df.empty:
        bm_close = bm_df["close"].reindex(result.equity_curve.index).ffill()
        norm_bm = bm_close / bm_close.iloc[0]
        fig.add_trace(go.Scatter(x=norm_bm.index, y=norm_bm.values,
                                 name="上证指数", line=dict(color="#6c757d", width=1.5, dash="dash")))
    fig.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(x=0.01, y=0.99))
    st.plotly_chart(fig, use_container_width=True)

    # ------------------------------------------------------------------
    # K 线图 + 信号
    # ------------------------------------------------------------------
    st.subheader("📉 K 线图与交易信号")
    fig2 = make_subplots(rows=2, cols=1, shared_xaxes=True,
                         row_heights=[0.75, 0.25], vertical_spacing=0.02)
    fig2.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="K线",
        increasing_line_color="#e63946", decreasing_line_color="#2a9d8f",
    ), row=1, col=1)

    # 买入信号
    buy_dates = result.signals[result.signals == 1].index
    buy_prices = df.loc[buy_dates, "low"] * 0.98 if len(buy_dates) > 0 else pd.Series()
    if len(buy_dates) > 0:
        fig2.add_trace(go.Scatter(
            x=buy_dates, y=buy_prices,
            mode="markers", marker=dict(symbol="triangle-up", size=10, color="#e63946"),
            name="买入", showlegend=True,
        ), row=1, col=1)

    # 卖出信号
    sell_dates = result.signals[result.signals == -1].index
    sell_prices = df.loc[sell_dates, "high"] * 1.02 if len(sell_dates) > 0 else pd.Series()
    if len(sell_dates) > 0:
        fig2.add_trace(go.Scatter(
            x=sell_dates, y=sell_prices,
            mode="markers", marker=dict(symbol="triangle-down", size=10, color="#2a9d8f"),
            name="卖出", showlegend=True,
        ), row=1, col=1)

    fig2.add_trace(go.Bar(x=df.index, y=df["volume"], name="成交量",
                          marker_color="#adb5bd"), row=2, col=1)
    fig2.update_layout(height=500, xaxis_rangeslider_visible=False,
                       margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig2, use_container_width=True)

    # ------------------------------------------------------------------
    # 交易记录
    # ------------------------------------------------------------------
    st.subheader("📋 交易记录")
    if result.trade_records:
        trades_df = pd.DataFrame(result.trade_records)
        trades_df["date"] = pd.to_datetime(trades_df["date"]).dt.date
        for col in ["price", "commission", "pnl", "cash_after"]:
            if col in trades_df.columns:
                trades_df[col] = trades_df[col].round(2)
        st.dataframe(trades_df, use_container_width=True, hide_index=True)
    else:
        st.info("本次回测未产生交易记录。")
