"""多因子选股页：对股票池进行多因子综合评分排名。"""
import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data import fetcher
from core.strategies.multi_factor import MultiFactorScorer

st.title("🎯 多因子选股")
st.caption("对自定义股票池进行动量、波动率、RSI趋势、均线趋势等多因子综合评分排名。")

# ------------------------------------------------------------------
# 股票池配置
# ------------------------------------------------------------------
st.subheader("股票池设置")

DEFAULT_POOL = [
    "000001", "600519", "000858", "300750", "601318",
    "000002", "600036", "601166", "000333", "002415",
    "600276", "601398", "600887", "000725", "002594",
]

col1, col2 = st.columns([2, 1])
with col1:
    pool_input = st.text_area(
        "输入股票代码（每行一个，建议 10-50 只）",
        value="\n".join(DEFAULT_POOL),
        height=200,
    )
with col2:
    st.markdown("**因子权重配置**")
    w_mom20 = st.slider("20日动量权重", 0.0, 1.0, 0.30, 0.05)
    w_mom60 = st.slider("60日动量权重", 0.0, 1.0, 0.25, 0.05)
    w_vol = st.slider("低波动率权重", 0.0, 1.0, 0.20, 0.05)
    w_rsi = st.slider("RSI趋势权重", 0.0, 1.0, 0.15, 0.05)
    w_ma = st.slider("均线趋势权重", 0.0, 1.0, 0.10, 0.05)
    top_n = st.number_input("选出前 N 只", min_value=1, max_value=20, value=5)

run_btn = st.button("🚀 运行多因子选股", type="primary")

if run_btn:
    symbols = [s.strip() for s in pool_input.strip().split("\n") if s.strip() and len(s.strip()) == 6]
    if not symbols:
        st.error("请输入有效的股票代码。")
        st.stop()

    end = datetime.date.today()
    start = end - datetime.timedelta(days=365)

    progress = st.progress(0)
    status = st.empty()
    stock_data = {}

    for i, sym in enumerate(symbols):
        status.text(f"加载 {sym} 数据 ({i+1}/{len(symbols)})...")
        try:
            df = fetcher.get_kline(
                sym,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
            if not df.empty:
                stock_data[sym] = df
        except Exception:
            pass
        progress.progress((i + 1) / len(symbols))

    status.text(f"数据加载完成，共 {len(stock_data)}/{len(symbols)} 只。正在评分...")

    total_w = w_mom20 + w_mom60 + w_vol + w_rsi + w_ma
    if total_w == 0:
        st.error("因子权重之和不能为0。")
        st.stop()

    weights = {
        "momentum_20": w_mom20 / total_w,
        "momentum_60": w_mom60 / total_w,
        "volatility": w_vol / total_w,
        "rsi_trend": w_rsi / total_w,
        "ma_trend": w_ma / total_w,
    }
    scorer = MultiFactorScorer(weights=weights, top_n=top_n)
    scored_df = scorer.score_stocks(stock_data)

    if scored_df.empty:
        st.error("评分失败，数据不足（每只股票至少需要 65 个交易日数据）。")
        st.stop()

    st.success(f"✅ 评分完成！共评估 {len(scored_df)} 只股票。")

    # 获取股票名称
    try:
        stock_list = fetcher.get_stock_list()
        name_map = dict(zip(stock_list["code"], stock_list["name"]))
        scored_df["name"] = scored_df["symbol"].map(name_map).fillna("")
    except Exception:
        scored_df["name"] = ""

    # ------------------------------------------------------------------
    # 展示结果
    # ------------------------------------------------------------------
    st.subheader(f"📊 综合评分排名（前 {top_n} 名推荐）")

    top_df = scored_df.head(top_n)[["symbol", "name", "score", "rank",
                                    "momentum_20", "momentum_60", "volatility",
                                    "rsi_trend", "ma_trend"]].copy()
    for col in ["score", "momentum_20", "momentum_60", "volatility", "rsi_trend", "ma_trend"]:
        if col in top_df.columns:
            top_df[col] = top_df[col].round(4)

    rename_map = {
        "symbol": "代码", "name": "名称", "score": "综合评分", "rank": "排名",
        "momentum_20": "20日动量", "momentum_60": "60日动量",
        "volatility": "低波动因子", "rsi_trend": "RSI趋势", "ma_trend": "均线趋势",
    }
    st.dataframe(top_df.rename(columns=rename_map), use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------
    # 评分分布图
    # ------------------------------------------------------------------
    st.subheader("评分分布")
    show_n = min(30, len(scored_df))
    chart_df = scored_df.head(show_n).copy()
    chart_df["label"] = chart_df["symbol"] + " " + chart_df.get("name", "")
    fig = px.bar(
        chart_df, x="label", y="score",
        color="score", color_continuous_scale="RdYlGn",
        title=f"前 {show_n} 只股票综合评分",
        labels={"label": "股票", "score": "综合评分"},
    )
    fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0),
                      xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    # ------------------------------------------------------------------
    # 因子热力图
    # ------------------------------------------------------------------
    st.subheader("因子热力图（前20只）")
    hm_df = scored_df.head(20)[["symbol", "momentum_20", "momentum_60",
                                  "volatility", "rsi_trend", "ma_trend"]].copy()
    hm_df = hm_df.set_index("symbol")
    fig2 = px.imshow(
        hm_df.T,
        color_continuous_scale="RdYlGn",
        title="各因子 Z-score 热力图",
        labels=dict(x="股票代码", y="因子", color="Z-score"),
    )
    fig2.update_layout(height=300, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig2, use_container_width=True)

    st.caption("⚠️ 多因子选股结果仅供参考，不构成投资建议。投资有风险，请结合基本面分析和个人判断。")
