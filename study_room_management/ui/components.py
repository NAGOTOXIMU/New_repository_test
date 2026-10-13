"""通用 UI 组件：身份信息、权限断言、状态名映射、侧边栏。"""
import streamlit as st

from config import (AREA_NAMES, KIND_NAMES, MEMBER_LEVEL_NAMES, ORDER_STATUS_NAMES,
                    PAY_STATUS_NAMES, STATUS_ON)
from ui.theme import brand_html


def display_name(user=None):
    """取当前登录人的展示名（用户看昵称，管理员看姓名）。"""
    user = user or st.session_state.get("user") or {}
    return (user.get("nickname") or user.get("real_name")
            or user.get("username") or user.get("phone") or "未登录")


def account_label(user=None):
    """取当前登录人的账号（用户看手机号，管理员看用户名）。"""
    user = user or st.session_state.get("user") or {}
    return user.get("phone") or user.get("username") or ""


def _user_menu_html(user, is_admin):
    """用户弹出菜单里的信息块（菜单项由 st.popover 里的组件提供）。"""
    rows = [f'<div class="user-menu-txt"><b>{display_name(user)}</b>']
    account = account_label(user)
    if account:
        rows.append(f'<div class="mono">{account}</div>')
    if is_admin:
        rows.append(f'<div>{user.get("role_name") or "管理员"}</div>')
    else:
        level = MEMBER_LEVEL_NAMES.get(int(user.get("member_level") or 0), "普通用户")
        rows.append(f'<div>{level}</div>')
        rows.append(f'<div>余额 <span class="mono">{user.get("balance", 0)}</span> 元 · '
                    f'剩余 <span class="mono">{user.get("remaining_hours", 0)}</span> 小时</div>')
    rows.append('</div>')
    return ''.join(rows)


def sidebar_user():
    """侧边栏：顶部品牌区 + 底部「头像 + 用户菜单」。返回当前 user dict。

    注意：Streamlit 的页面导航由它自己插在侧边栏里，Python 里挪不动，
    品牌区排到导航上方靠的是 ui/theme.py 里的 flex order，别在这里改顺序。
    """
    user = st.session_state.get("user") or {}
    is_admin = user.get("role") == "admin"

    with st.sidebar:
        with st.container(key="side_brand"):
            st.markdown(brand_html("自习室", "管理端" if is_admin else "用户端"),
                        unsafe_allow_html=True)

        with st.container(key="side_user"):
            with st.popover(display_name(user)):
                st.markdown(_user_menu_html(user, is_admin), unsafe_allow_html=True)
                if st.button("退出登录", width="stretch", key="logout_btn"):
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


def flash(message=None, kind="success"):
    """一次性提示：即使后面立刻 st.rerun()，用户也能看到。

    用法：
        flash()                          # 页面顶部调一次，把上一轮留下的提示显示出来
        flash("已更新")                  # 操作成功后，代替 st.success
        flash("操作失败", "error")       # kind 还可用 error / warning / info
    """
    if message is not None:
        st.session_state["_flash"] = (kind, message)
        return
    item = st.session_state.pop("_flash", None)
    if item:
        kind, msg = item
        getattr(st, kind)(msg)
