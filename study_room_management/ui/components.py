"""通用 UI 组件。"""
import streamlit as st


def require_role(*roles):
    """限制只有指定角色能访问当前页面。放在受限页面的第一行。

    注意：导航里隐藏页面不等于权限控制，用户可以直接改 URL 访问，
    所以每个受限页面都必须显式调用一次。
    """
    user = st.session_state.get("user")
    if not user or user.get("role") not in roles:
        st.error("无权访问该页面")
        st.stop()
