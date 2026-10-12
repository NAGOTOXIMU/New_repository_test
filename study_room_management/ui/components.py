"""通用 UI 组件与界面层工具。

放什么：
    - require_role(*roles)   权限断言：受限页面第一行调用，角色不符就 st.stop()
        ⚠️ 为什么必须要：导航里隐藏页面【不等于】权限控制，
           用户可以直接在地址栏输 URL 访问管理端页面
    - 统一错误显示：捕获 services 抛出的 BizError → st.error(...)
    - 复用组件：分页表格、确认对话框、金额 / 日期格式化、空状态提示

约定：
    - 组件只接收普通数据（dict / list / DataFrame），不接收 SQL 或业务逻辑
    - 这里可以 import streamlit（属于 ui 层）

示例：
    def require_role(*roles):
        u = st.session_state.get("user")
        if not u or u["role"] not in roles:
            st.error("无权访问该页面")
            st.stop()
"""
