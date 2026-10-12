"""登录（与注册）页面。

职责：
    - 用 st.form 收集用户名 / 密码（用 form 包住，避免每敲一个字就重跑脚本查库）
    - 调用 services/user_service.login()
    - 成功后把用户信息写进 st.session_state["user"]（界面状态由 ui 层负责写）
    - 失败时显示 services 抛出的 BizError 文案
    - 注册表单同理，调 user_service.register()

注意：
    - 本文件由 app.py 在未登录时通过 st.navigation 挂载
    - 不写 SQL、不写业务判断
"""
