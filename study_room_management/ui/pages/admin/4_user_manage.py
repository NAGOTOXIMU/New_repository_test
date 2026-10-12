"""管理端 · 用户管理。

⚠️ 第一行调用 ui.components.require_role("admin")。

职责：
    - 用户列表（服务端分页，按用户名 / 手机号搜索）
    - 查看某用户的持仓（user_card）、预约记录、充值记录
    - 冻结 / 解冻账号（改 user.status）

依赖：services/user_service.py

注意：用户密码字段存的是哈希，界面任何地方都不展示原始值。
"""
