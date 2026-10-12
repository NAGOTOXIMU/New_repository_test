"""登录 / 注册页面。只做三件事：收集输入 → 调 service → 显示结果。"""
import streamlit as st

from services import user_service
from services.exceptions import BizError

st.title("自习室预约系统")

tab_login, tab_register = st.tabs(["登录", "注册"])

with tab_login:
    with st.form("login_form"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        submitted = st.form_submit_button("登录", use_container_width=True)

    if submitted:
        try:
            user = user_service.login(username, password)
            st.session_state["user"] = user      # 登录成功的标志
            st.rerun()
        except BizError as e:
            st.error(str(e))

with tab_register:
    with st.form("register_form"):
        r_username = st.text_input("用户名", key="r_username")
        r_password = st.text_input("密码", type="password", key="r_password")
        r_real_name = st.text_input("姓名", key="r_real_name")
        r_phone = st.text_input("手机号", key="r_phone")
        r_submitted = st.form_submit_button("注册", use_container_width=True)

    if r_submitted:
        try:
            user_service.register(r_username, r_password, r_real_name, r_phone)
            st.success("注册成功，请到「登录」标签页登录")
        except BizError as e:
            st.error(str(e))
