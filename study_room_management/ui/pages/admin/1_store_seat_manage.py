"""管理端 · 门店与座位管理。

⚠️ 本文件第一行必须调用 ui.components.require_role("admin")。
   原因：导航里不显示这个页面【不等于】别人访问不到，URL 可以直接输。

职责：
    - 门店列表与信息维护（名称、地址、营业时间、营业 / 停业）
    - 座位管理：查看某门店座位、批量新增（如 A01~A20）、停用 / 维修
    - 店长只能看到自己的门店（用 admin.store_id 过滤，见 DESIGN.md B2）

依赖：services/store_service.py
"""
