"""项目总入口。

职责：
    1. st.set_page_config(...) 设置页面标题与布局
    2. 判断登录态：st.session_state 里没有用户 → 只挂载登录页
    3. 已登录：按角色用 st.navigation() + st.Page() 组装导航

⚠️ 关键：ui/pages/ 下的页面不会被 Streamlit 自动发现。
   Streamlit 的自动多页机制只认「与入口脚本同级的扁平 pages/ 目录」，
   不会递归 ui/pages/user/、ui/pages/admin/ 这类子目录。
   所以必须在这里用 st.Page("ui/pages/.../xxx.py", title="...") 显式注册。

保持精简：本文件只做引导，不写业务逻辑、不写 SQL。建议 30 行以内。
"""
