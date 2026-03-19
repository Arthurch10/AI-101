"""数据管理页：下载/更新历史 K 线数据，查看缓存状态。"""
import streamlit as st
import pandas as pd
import datetime
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data import fetcher, cache

st.title("🗄️ 数据管理")

# ------------------------------------------------------------------
# 下载历史数据
# ------------------------------------------------------------------
st.subheader("下载历史 K 线数据")

col1, col2, col3, col4 = st.columns(4)
with col1:
    symbol = st.text_input("股票代码（6位）", value="000001")
with col2:
    start_date = st.date_input("起始日期", value=datetime.date(2020, 1, 1))
with col3:
    end_date = st.date_input("截止日期", value=datetime.date.today())
with col4:
    adjust = st.selectbox("复权方式", ["qfq（前复权）", "hfq（后复权）", "不复权"])
    adjust_map = {"qfq（前复权）": "qfq", "hfq（后复权）": "hfq", "不复权": ""}
    adjust_val = adjust_map[adjust]

if st.button("📥 下载数据", type="primary"):
    if len(symbol) != 6 or not symbol.isdigit():
        st.error("请输入正确的 6 位股票代码")
    else:
        with st.spinner(f"正在下载 {symbol} 数据..."):
            try:
                df = fetcher.get_kline(
                    symbol=symbol,
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                    adjust=adjust_val,
                    use_cache=False,
                )
                if df.empty:
                    st.warning("未获取到数据，请检查股票代码或日期范围。")
                else:
                    st.success(f"✅ 成功下载 {len(df)} 条记录（{df.index[0].date()} ~ {df.index[-1].date()}）")
                    st.dataframe(df.tail(10), use_container_width=True)
            except Exception as e:
                st.error(f"下载失败：{e}")

st.divider()

# ------------------------------------------------------------------
# 批量下载
# ------------------------------------------------------------------
st.subheader("批量下载（常用股票）")

DEFAULT_SYMBOLS = ["000001", "600519", "000858", "300750", "601318",
                   "000002", "600036", "601166", "000333", "002415"]

batch_symbols = st.text_area(
    "输入股票代码（每行一个）",
    value="\n".join(DEFAULT_SYMBOLS),
    height=150,
)
batch_start = st.date_input("批量起始日期", value=datetime.date(2022, 1, 1), key="batch_start")

if st.button("📥 批量下载"):
    symbols = [s.strip() for s in batch_symbols.strip().split("\n") if s.strip()]
    progress = st.progress(0)
    status = st.empty()
    ok, fail = 0, 0
    for i, sym in enumerate(symbols):
        status.text(f"正在下载 {sym} ({i+1}/{len(symbols)})...")
        try:
            df = fetcher.get_kline(
                sym,
                start_date=batch_start.strftime("%Y%m%d"),
                end_date=datetime.date.today().strftime("%Y%m%d"),
                use_cache=False,
            )
            ok += 1 if not df.empty else 0
        except Exception:
            fail += 1
        progress.progress((i + 1) / len(symbols))
    status.text(f"完成：成功 {ok} 只，失败 {fail} 只")
    st.success("批量下载完成！")

st.divider()

# ------------------------------------------------------------------
# 缓存统计
# ------------------------------------------------------------------
st.subheader("本地缓存状态")

try:
    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache.db")
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        stats = pd.read_sql_query(
            "SELECT symbol, COUNT(*) as records, MIN(date) as earliest, MAX(date) as latest "
            "FROM kline_daily GROUP BY symbol ORDER BY records DESC",
            conn
        )
        conn.close()
        if not stats.empty:
            st.metric("已缓存股票数量", len(stats))
            st.metric("总记录数", stats["records"].sum())
            st.dataframe(stats, use_container_width=True, hide_index=True)
        else:
            st.info("缓存为空，请先下载数据。")
        if st.button("🗑️ 清空缓存"):
            conn = sqlite3.connect(db_path)
            conn.execute("DELETE FROM kline_daily")
            conn.commit()
            conn.close()
            st.success("缓存已清空。")
    else:
        st.info("缓存数据库尚未创建，下载数据后自动生成。")
except Exception as e:
    st.error(f"读取缓存状态失败：{e}")
