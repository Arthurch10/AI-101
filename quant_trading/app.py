"""A 股量化交易软件 - Streamlit 入口文件。"""
import streamlit as st

st.set_page_config(
    page_title="A股量化交易系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = {
    "市场": [
        st.Page("pages/1_dashboard.py", title="市场总览", icon="📊"),
        st.Page("pages/2_data.py", title="数据管理", icon="🗄️"),
    ],
    "研究": [
        st.Page("pages/3_backtest.py", title="策略回测", icon="🔬"),
        st.Page("pages/4_strategies.py", title="策略信号", icon="📈"),
        st.Page("pages/7_multifactor.py", title="多因子选股", icon="🎯"),
    ],
    "交易": [
        st.Page("pages/5_portfolio.py", title="模拟账户", icon="💼"),
        st.Page("pages/6_risk.py", title="风控设置", icon="🛡️"),
    ],
}

pg = st.navigation(pages)
pg.run()
