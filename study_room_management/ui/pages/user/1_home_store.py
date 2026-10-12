"""用户端 · 首页与门店列表。

职责：
    - 展示门店列表（名称、地址、营业时间、座位数）
    - 支持按门店名 / 地址筛选
    - 选中门店后跳转到座位预约页（st.switch_page 或写入 session_state）

依赖：services/store_service.py

注意：本文件不会被自动发现，必须在 app.py 里注册。
"""
