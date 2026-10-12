"""用户端首页。先占位，后面换成真正的门店列表。"""
import streamlit as st

user = st.session_state["user"]

st.title(f"欢迎，{user['real_name']}")

with st.sidebar:
    st.write(f"当前用户：{user['username']}")
    if st.button("退出登录"):
        st.session_state.clear()
        st.rerun()

st.info("门店列表与座位预约功能开发中……")
a = 1