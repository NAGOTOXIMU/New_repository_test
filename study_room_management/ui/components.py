"""通用 UI 组件：身份信息、权限断言、状态名映射。"""
import streamlit as st

from config import (AREA_NAMES, KIND_NAMES, MEMBER_LEVEL_NAMES, ORDER_STATUS_NAMES,
                    PAY_STATUS_NAMES, STATUS_ON)


def display_name(user=None):
    """取当前登录人的展示名（用户看昵称，管理员看姓名）。"""
    user = user or st.session_state.get("user") or {}
    return (user.get("nickname") or user.get("real_name")
            or user.get("username") or user.get("phone") or "未登录")


def account_label(user=None):
    """取当前登录人的账号（用户看手机号，管理员看用户名）。"""
    user = user or st.session_state.get("user") or {}
    return user.get("phone") or user.get("username") or ""


def sidebar_user():
    """侧边栏：显示当前登录人 + 退出登录按钮。返回当前 user dict。"""
    user = st.session_state.get("user") or {}
    with st.sidebar:
        st.write(f"当前用户：{display_name(user)}")
        st.caption(f"账号：{account_label(user)}")
        if user.get("role") == "user":
            st.caption(f"余额：{user.get('balance', 0)} 元 ｜ "
                       f"剩余时长：{user.get('remaining_hours', 0)} 小时")
            level = MEMBER_LEVEL_NAMES.get(int(user.get("member_level") or 0), "普通用户")
            st.caption(f"会员等级：{level}")
        elif user.get("role") == "admin":
            st.caption(f"角色：{user.get('role_name', '普通运营员')}")
        if st.button("退出登录"):
            st.session_state.clear()
            st.rerun()
    return user


def require_role(*roles):
    """限制只有指定角色能访问当前页面。放在受限页面的第一行。

    注意：导航里隐藏页面不等于权限控制，用户可以直接改 URL 访问，
    所以每个受限页面都必须显式调用一次。
    """
    user = st.session_state.get("user")
    if not user or user.get("role") not in roles:
        st.error("无权访问该页面")
        st.stop()


def order_status_name(value):
    return ORDER_STATUS_NAMES.get(int(value), f"未知({value})")


def pay_status_name(value):
    return PAY_STATUS_NAMES.get(int(value), f"未知({value})")


def kind_name(value):
    return KIND_NAMES.get(int(value), f"未知({value})")


def area_name(value):
    return AREA_NAMES.get(int(value), f"未知({value})")


def on_off(value, on_text="是", off_text="否"):
    return on_text if int(value) == STATUS_ON else off_text
