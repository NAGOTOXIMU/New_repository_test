"""管理端 · 订单管理。

第一行必须调用 ui.components.require_role("admin")。
功能：预约订单与充值订单列表（按门店/状态/日期筛选），推进订单状态。
注意：状态由谁推进还没拍板，见 docs/DESIGN.md 的 A1。
"""
