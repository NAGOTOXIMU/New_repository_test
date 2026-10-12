"""管理端 · 卡种管理。

第一行必须调用 ui.components.require_role("admin")。
功能：卡种增改、上架下架；price >= 0、discount 在 0.01~1.00（与数据库 CHECK 一致）。
"""
