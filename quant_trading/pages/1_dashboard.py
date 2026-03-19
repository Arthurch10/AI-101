"""市场总览页：大盘指数 + 自选股实时行情。"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data import fetcher

st.title("📊 市场总览")

# ------------------------------------------------------------------
# 大盘指数走势
# ------------------------------------------------------------------
st.subheader("大盘指数")

INDEX_MAP = {
    "上证指数": "000001",
    "深证成指": "399001",
    "创业板指": "399006",
    "沪深300": "000300",
}

col1, col2 = st.columns([3, 1])
with col2:
    selected_index = st.selectbox("选择指数", list(INDEX_MAP.keys()))
    period = st.selectbox("周期", ["近1个月", "近3个月", "近6个月", "近1年", "近3年"])

period_days = {"近1个月": 30, "近3个月": 90, "近6个月": 180, "近1年": 365, "近3年": 1095}
import datetime
end = datetime.date.today()
start = end - datetime.timedelta(days=period_days[period])

with col1:
    with st.spinner("加载指数数据..."):
        try:
            df = fetcher.get_index_kline(
                symbol=INDEX_MAP[selected_index],
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
            if not df.empty:
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                    row_heights=[0.7, 0.3], vertical_spacing=0.02)
                fig.add_trace(go.Candlestick(
                    x=df.index, open=df["open"], high=df["high"],
                    low=df["low"], close=df["close"], name=selected_index,
                    increasing_line_color="#e63946", decreasing_line_color="#2a9d8f",
                ), row=1, col=1)
                fig.add_trace(go.Bar(
                    x=df.index, y=df["volume"], name="成交量",
                    marker_color="#adb5bd",
                ), row=2, col=1)
                fig.update_layout(
                    height=450, xaxis_rangeslider_visible=False,
                    margin=dict(l=0, r=0, t=30, b=0),
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)

                # 指数统计
                latest = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else latest
                chg_pct = (latest["close"] - prev["close"]) / prev["close"] * 100
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("最新价", f"{latest['close']:.2f}",
                          f"{chg_pct:+.2f}%",
                          delta_color="inverse" if chg_pct < 0 else "normal")
                c2.metric("今日最高", f"{latest['high']:.2f}")
                c3.metric("今日最低", f"{latest['low']:.2f}")
                c4.metric("成交量（万手）", f"{latest['volume']/1e4:.0f}")
        except Exception as e:
            st.error(f"加载指数数据失败：{e}")

# ------------------------------------------------------------------
# 自选股
# ------------------------------------------------------------------
st.divider()
st.subheader("自选股行情")

if "watchlist" not in st.session_state:
    st.session_state.watchlist = ["000001", "600519", "000858", "300750", "601318"]

with st.expander("管理自选股"):
    new_code = st.text_input("添加股票代码（6位）", max_chars=6)
    if st.button("添加") and len(new_code) == 6:
        if new_code not in st.session_state.watchlist:
            st.session_state.watchlist.append(new_code)
    to_remove = st.multiselect("移除股票", st.session_state.watchlist)
    if st.button("移除选中"):
        for c in to_remove:
            st.session_state.watchlist.remove(c)

if st.button("🔄 刷新行情"):
    st.cache_data.clear()

@st.cache_data(ttl=60)
def load_realtime():
    return fetcher.get_realtime_quotes()

try:
    with st.spinner("加载实时行情..."):
        rt = load_realtime()
        if not rt.empty:
            watched = rt[rt["code"].isin(st.session_state.watchlist)].copy()
            if not watched.empty:
                display_cols = [c for c in ["code", "name", "price", "change_pct",
                                             "change_amount", "volume", "amount", "pe", "pb"] if c in watched.columns]
                rename = {
                    "code": "代码", "name": "名称", "price": "最新价",
                    "change_pct": "涨跌幅%", "change_amount": "涨跌额",
                    "volume": "成交量", "amount": "成交额", "pe": "市盈率", "pb": "市净率"
                }
                disp = watched[display_cols].rename(columns=rename)

                def color_pct(val):
                    if isinstance(val, (int, float)):
                        color = "#e63946" if val > 0 else ("#2a9d8f" if val < 0 else "")
                        return f"color: {color}"
                    return ""

                st.dataframe(
                    disp.style.applymap(color_pct, subset=["涨跌幅%"] if "涨跌幅%" in disp.columns else []),
                    use_container_width=True, hide_index=True,
                )
            else:
                st.info("自选股中无匹配行情，请检查股票代码。")
except Exception as e:
    st.error(f"加载实时行情失败：{e}")
    st.info("提示：实时行情需要在 A 股交易时段（9:30-15:00）访问。")
