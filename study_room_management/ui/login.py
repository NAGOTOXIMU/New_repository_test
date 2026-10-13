"""登录 / 注册页面。只做三件事：收集输入 → 调 service → 显示结果。

规范口径：用户用「手机号 + 密码」登录；管理员用「用户名 + 密码」登录。
"""
import streamlit as st

from services import admin_service, user_service
from services.exceptions import BizError
from ui.theme import brand_html

# 整页一张居中卡片（.st-key-login_card 的样式在 ui/theme.py）
with st.container(key="login_card"):
    st.markdown(brand_html("自习室预约系统", "Study Room Booking", "login-brand"),
                unsafe_allow_html=True)
    st.markdown('<div class="login-title">欢迎回来</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-desc">登录后即可预约座位、管理你的会员卡。</div>',
                unsafe_allow_html=True)

    tab_login, tab_admin, tab_register = st.tabs(["用户登录", "管理员登录", "用户注册"])

    with tab_login:
        with st.form("login_form"):
            phone = st.text_input("手机号")
            password = st.text_input("密码", type="password")
            submitted = st.form_submit_button("登录", width="stretch")

        if submitted:
            try:
                user = user_service.login(phone, password)
                st.session_state["user"] = user      # 登录成功的标志
                st.rerun()
            except BizError as e:
                st.error(str(e))

    with tab_admin:
        with st.form("admin_login_form"):
            a_username = st.text_input("管理员用户名")
            a_password = st.text_input("密码", type="password", key="a_password")
            a_submitted = st.form_submit_button("登录", width="stretch")

        if a_submitted:
            try:
                admin = admin_service.login(a_username, a_password)
                st.session_state["user"] = admin
                st.rerun()
            except BizError as e:
                st.error(str(e))

    with tab_register:
        with st.form("register_form"):
            r_phone = st.text_input("手机号", key="r_phone")
            r_password = st.text_input("密码（至少 6 位）", type="password", key="r_password")
            r_nickname = st.text_input("昵称", key="r_nickname")
            r_submitted = st.form_submit_button("注册", width="stretch")

        if r_submitted:
            try:
                user_service.register(r_phone, r_password, r_nickname)
                st.success("注册成功，请到「用户登录」标签页登录")
            except BizError as e:
                st.error(str(e))
