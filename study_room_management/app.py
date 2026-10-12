"""项目总入口：登录门卫 + 导航组装。

注意：ui/pages/ 下的页面不会被 Streamlit 自动发现，必须在这里用 st.Page() 注册。
"""
import streamlit as st

st.set_page_config(page_title="自习室预约系统", layout="wide")

# ——— 门卫：没登录就只挂登录页 ———
if "user" not in st.session_state:
    st.navigation([
        st.Page("ui/login.py", title="登录", icon="🔑"),
    ]).run()
    st.stop()

# ——— 已登录：组装导航（页面写好了就往这里加） ———
pages = [
    st.Page("ui/pages/user/1_home_store.py", title="首页与门店", icon="🏠"),
]
st.navigation(pages).run()
