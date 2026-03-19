"""模拟账户页：持仓管理、手动下单、交易记录。"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trading.paper_broker import PaperBroker
from core.trading.order import OrderDirection, OrderType
from core.data import fetcher

# ------------------------------------------------------------------
# 初始化模拟账户（session_state 持久化）
# ------------------------------------------------------------------
if "paper_broker" not in st.session_state:
    st.session_state.paper_broker = PaperBroker(initial_capital=500_000.0)

broker: PaperBroker = st.session_state.paper_broker

st.title("💼 模拟账户")

# ------------------------------------------------------------------
# 账户概览
# ------------------------------------------------------------------
# 更新持仓价格
positions = broker.get_positions()
if positions:
    try:
        rt = fetcher.get_realtime_quotes()
        if not rt.empty:
            prices = dict(zip(rt["code"], rt["price"]))
            broker.update_prices(prices)
    except Exception:
        pass

account = broker.get_account()

col1, col2, col3, col4 = st.columns(4)
col1.metric("总资产", f"¥{account.total_assets:,.2f}")
col2.metric("可用现金", f"¥{account.cash:,.2f}")
col3.metric("持仓市值", f"¥{account.market_value:,.2f}")
pnl_color = "normal" if account.total_pnl >= 0 else "inverse"
col4.metric("总盈亏", f"¥{account.total_pnl:,.2f}",
            f"{account.total_pnl/broker.initial_capital*100:+.2f}%",
            delta_color=pnl_color)

st.divider()

# ------------------------------------------------------------------
# 持仓列表
# ------------------------------------------------------------------
st.subheader("当前持仓")
if positions:
    rows = []
    for sym, pos in positions.items():
        price = broker._latest_prices.get(sym, pos.cost_price)
        pnl = pos.unrealized_pnl(price)
        pnl_pct = pos.unrealized_pnl_pct(price) * 100
        rows.append({
            "代码": sym,
            "名称": pos.name or sym,
            "持仓数量": pos.quantity,
            "成本价": round(pos.cost_price, 2),
            "当前价": round(price, 2),
            "市值": round(pos.market_value(price), 2),
            "浮盈亏": round(pnl, 2),
            "收益率%": round(pnl_pct, 2),
            "可卖出": "是" if pos.can_sell_today else "否(T+1)",
        })
    pos_df = pd.DataFrame(rows)
    st.dataframe(pos_df, use_container_width=True, hide_index=True)
else:
    st.info("当前无持仓。")

# ------------------------------------------------------------------
# 手动下单
# ------------------------------------------------------------------
st.divider()
st.subheader("手动下单")

with st.form("order_form"):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        order_symbol = st.text_input("股票代码", max_chars=6)
    with col2:
        direction = st.selectbox("方向", ["买入", "卖出"])
    with col3:
        quantity = st.number_input("数量（股）", min_value=100, step=100, value=100)
    with col4:
        price = st.number_input("价格（0=市价）", min_value=0.0, step=0.01, value=0.0)
    submitted = st.form_submit_button("提交委托", type="primary")

if submitted and order_symbol:
    dir_map = {"买入": OrderDirection.BUY, "卖出": OrderDirection.SELL}
    order = broker.place_order(
        symbol=order_symbol,
        direction=dir_map[direction],
        quantity=quantity,
        price=price,
        order_type=OrderType.MARKET if price == 0 else OrderType.LIMIT,
    )
    if order.is_filled:
        st.success(f"✅ 委托成功！{direction} {order_symbol} {quantity}股 @ {order.filled_price:.2f}")
    else:
        st.error(f"❌ 委托失败：{order.note}")

# ------------------------------------------------------------------
# 重置账户
# ------------------------------------------------------------------
st.divider()
col1, col2 = st.columns([3, 1])
with col1:
    new_capital = st.number_input("初始资金（元）", value=500000, step=10000)
with col2:
    st.write("")
    st.write("")
    if st.button("🔄 重置账户", type="secondary"):
        st.session_state.paper_broker = PaperBroker(initial_capital=float(new_capital))
        st.success("账户已重置！")
        st.rerun()

# ------------------------------------------------------------------
# 历史成交记录
# ------------------------------------------------------------------
st.divider()
st.subheader("历史成交记录")
trades = broker.get_trade_history()
if trades:
    trades_df = pd.DataFrame(trades)
    trades_df["date"] = pd.to_datetime(trades_df["date"]).dt.strftime("%Y-%m-%d %H:%M")
    for col in ["price", "amount", "commission"]:
        if col in trades_df.columns:
            trades_df[col] = trades_df[col].round(2)
    if "pnl" in trades_df.columns:
        trades_df["pnl"] = trades_df["pnl"].round(2)
    st.dataframe(trades_df, use_container_width=True, hide_index=True)
else:
    st.info("暂无成交记录。")
