"""项目总入口：全站样式 + 登录门卫 + 导航组装。

注意：ui/pages/ 下的页面不会被 Streamlit 自动发现，必须在这里用 st.Page() 注册。
"""
import streamlit as st

from ui.theme import apply as apply_theme

st.set_page_config(page_title="自习室预约系统", layout="wide")

# 样式注入必须在这里（入口每轮都会执行，页面脚本之前），登录页和登录后的页面才会都有样式
apply_theme()

# ——— 门卫：没登录就只挂登录页 ———
current = st.session_state.get("user")
if not current:
    st.navigation([
        st.Page("ui/login.py", title="登录", icon="🔑"),
    ]).run()
    st.stop()

# ——— 已登录：按角色组装导航 ———
if current.get("role") == "admin":
    pages = [
        st.Page("ui/pages/admin/1_store_seat_manage.py", title="门店与座位", icon="🏢"),
        st.Page("ui/pages/admin/2_card_type_manage.py", title="卡种管理", icon="💳"),
        st.Page("ui/pages/admin/3_order_manage.py", title="订单管理", icon="📋"),
        st.Page("ui/pages/admin/4_user_manage.py", title="用户管理", icon="👥"),
        st.Page("ui/pages/admin/5_dashboard.py", title="运营看板", icon="📊"),
    ]
else:
    pages = [
        st.Page("ui/pages/user/1_home_store.py", title="首页与门店", icon="🏠"),
        st.Page("ui/pages/user/2_seat_reservation.py", title="座位预约", icon="🪑"),
        st.Page("ui/pages/user/3_my_orders.py", title="我的订单", icon="📋"),
        st.Page("ui/pages/user/4_member_recharge.py", title="会员充值", icon="💳"),
    ]

st.navigation(pages).run()
