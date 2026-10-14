"""登录 / 注册页面：一张卡片 + 卡片底部的文字链接。

设计稿里没有标签页：三种身份靠卡片底部的「立即注册 / 管理员登录」切换。
这两个链接用普通 <a href="?mode=xxx"> 写（样式和稿子的 .login-alt 一致），
Streamlit 这边读 st.query_params 决定显示哪个表单。
"""
import streamlit as st

from services import admin_service, user_service
from services.exceptions import BizError
from ui.theme import brand_html

# 从链接点进来的 ?mode=xxx 优先；否则沿用上一次的状态
_params_mode = st.query_params.get("mode")
if _params_mode in ("user", "admin", "register"):
    st.session_state["auth_mode"] = _params_mode
st.session_state.setdefault("auth_mode", "user")
mode = st.session_state["auth_mode"]

with st.container(key="login_card"):
    st.markdown(brand_html("自习室预约系统", "Study Room Booking"), unsafe_allow_html=True)

    if mode == "user":
        st.markdown('<div class="login-title serif">欢迎回来</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-desc">登录后即可预约座位、管理你的会员卡。</div>',
                    unsafe_allow_html=True)
        with st.form("login_form"):
            phone = st.text_input("手机号", placeholder="请输入 11 位手机号")
            password = st.text_input("密码", type="password", placeholder="请输入密码")
            submitted = st.form_submit_button("登 录", width="stretch", type="primary")
        if submitted:
            try:
                st.session_state["user"] = user_service.login(phone, password)
                st.rerun()
            except BizError as e:
                st.error(str(e))

    elif mode == "admin":
        st.markdown('<div class="login-title serif">管理员登录</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-desc">用管理员用户名登录后台。</div>',
                    unsafe_allow_html=True)
        with st.form("admin_login_form"):
            username = st.text_input("管理员用户名", placeholder="请输入用户名")
            password = st.text_input("密码", type="password", placeholder="请输入密码",
                                     key="a_password")
            submitted = st.form_submit_button("登 录", width="stretch", type="primary")
        if submitted:
            try:
                st.session_state["user"] = admin_service.login(username, password)
                st.rerun()
            except BizError as e:
                st.error(str(e))

    else:
        st.markdown('<div class="login-title serif">注册账号</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-desc">用手机号注册，注册后即可预约座位。</div>',
                    unsafe_allow_html=True)
        with st.form("register_form"):
            phone = st.text_input("手机号", placeholder="请输入 11 位手机号", key="r_phone")
            password = st.text_input("密码（至少 6 位）", type="password",
                                     placeholder="请输入密码", key="r_password")
            nickname = st.text_input("昵称", placeholder="怎么称呼你", key="r_nickname")
            submitted = st.form_submit_button("注 册", width="stretch", type="primary")
        if submitted:
            try:
                user_service.register(phone, password, nickname)
                st.success("注册成功，请到登录入口登录")
            except BizError as e:
                st.error(str(e))

    # —— 卡片底部的链接区（照设计稿的 .login-alt：两行，各自整体居中） ——
    if mode == "user":
        st.markdown(
            '<div class="login-alt">'
            '<p>还没有账号？<a href="?mode=register">立即注册</a></p>'
            '<p><a href="?mode=admin">管理员登录</a>'
            '<span class="sep">·</span><span>帮助中心</span></p>'
            '</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="login-alt"><p><a href="?mode=user">返回登录</a></p></div>',
            unsafe_allow_html=True)
