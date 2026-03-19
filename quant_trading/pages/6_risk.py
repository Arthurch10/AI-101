"""风控设置页：配置仓位上限、止损止盈、回撤熔断参数。"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.risk.manager import RiskManager, RiskConfig

st.title("🛡️ 风控设置")
st.caption("所有风控参数将应用于模拟账户的自动止损/止盈检查。")

# 从 session_state 获取或初始化风控配置
if "risk_config" not in st.session_state:
    st.session_state.risk_config = RiskConfig()

cfg: RiskConfig = st.session_state.risk_config

# ------------------------------------------------------------------
# 仓位管理
# ------------------------------------------------------------------
st.subheader("仓位管理")
col1, col2 = st.columns(2)
with col1:
    max_pos_pct = st.slider(
        "单股最大仓位占比",
        min_value=0.05, max_value=1.0, value=cfg.max_position_pct, step=0.05,
        help="单只股票持仓市值不超过总资产的此比例",
        format="%.0f%%",
    )
    max_stocks = st.number_input(
        "最多同时持有只数",
        min_value=1, max_value=20, value=cfg.max_stocks,
        help="控制分散度，建议 3-8 只",
    )
with col2:
    position_method = st.selectbox(
        "仓位计算方法",
        ["fixed（固定比例）", "kelly（Kelly 公式）"],
        index=0 if cfg.position_method == "fixed" else 1,
        help="Kelly 公式根据历史胜率和盈亏比动态计算最优仓位",
    )
    method_val = "fixed" if "fixed" in position_method else "kelly"

st.divider()

# ------------------------------------------------------------------
# 止损止盈
# ------------------------------------------------------------------
st.subheader("止损 / 止盈")
col1, col2 = st.columns(2)
with col1:
    stop_loss = st.slider(
        "止损线（亏损达到此比例时自动卖出）",
        min_value=0.02, max_value=0.30, value=cfg.stop_loss_pct, step=0.01,
        format="%.0f%%",
        help="建议 5%-10%，避免亏损扩大",
    )
with col2:
    take_profit = st.slider(
        "止盈线（盈利达到此比例时自动卖出）",
        min_value=0.05, max_value=1.0, value=cfg.take_profit_pct, step=0.05,
        format="%.0f%%",
        help="建议 15%-30%，锁定利润",
    )

st.divider()

# ------------------------------------------------------------------
# 回撤熔断
# ------------------------------------------------------------------
st.subheader("账户最大回撤熔断")
max_dd = st.slider(
    "最大回撤熔断线（账户净值从最高点回撤此比例时停止交易）",
    min_value=0.05, max_value=0.50, value=cfg.max_drawdown_limit, step=0.01,
    format="%.0f%%",
    help="触发熔断后系统将停止发出新的买入信号，已有持仓仍会按止损线管理",
)

st.divider()

# ------------------------------------------------------------------
# 保存配置
# ------------------------------------------------------------------
if st.button("💾 保存风控配置", type="primary"):
    st.session_state.risk_config = RiskConfig(
        max_position_pct=max_pos_pct,
        stop_loss_pct=stop_loss,
        take_profit_pct=take_profit,
        max_drawdown_limit=max_dd,
        max_stocks=int(max_stocks),
        position_method=method_val,
    )
    st.success("✅ 风控配置已保存！")

# ------------------------------------------------------------------
# 当前配置预览
# ------------------------------------------------------------------
st.subheader("当前配置")
saved = st.session_state.risk_config
col1, col2, col3, col4 = st.columns(4)
col1.metric("单股最大仓位", f"{saved.max_position_pct*100:.0f}%")
col2.metric("止损线", f"{saved.stop_loss_pct*100:.0f}%")
col3.metric("止盈线", f"{saved.take_profit_pct*100:.0f}%")
col4.metric("回撤熔断", f"{saved.max_drawdown_limit*100:.0f}%")

# ------------------------------------------------------------------
# 风控说明
# ------------------------------------------------------------------
with st.expander("📖 风控说明"):
    st.markdown("""
### A 股交易风控要点

**T+1 规则**
当日买入的股票次日才能卖出，系统已自动遵守此规则。

**仓位管理建议（50万本金）**
- 单股仓位：建议不超过总资产的 20%，即约 10 万元/只
- 分散持仓：建议同时持有 3-5 只，降低个股风险
- 留有现金：建议保留 20-30% 的现金应对市场波动

**止损原则**
- 严格止损是避免大亏损的核心纪律
- 建议设置 5%-8% 的硬止损，不要随意放宽
- 止损后冷静分析，不要立即追回

**止盈策略**
- 可采用移动止盈：盈利超过 15% 后，将止损线上移至成本价
- 分批止盈：盈利 10% 卖出 1/3，20% 再卖 1/3，剩余跑趋势

**回撤熔断**
- 单月回撤超过 10% 应停止交易，反思策略
- 全年回撤超过 15% 建议切换到保守策略或暂停系统交易
    """)
