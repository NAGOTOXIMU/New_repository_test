"""管理端 · 订单管理。

⚠️ 第一行调用 ui.components.require_role("admin")。

职责：
    - 预约订单列表：按门店 / 状态 / 日期筛选，服务端分页
    - 充值订单列表：查看充值记录与金额
    - 操作：签到（待使用 → 使用中）、完成、代取消
      ⚠️ 状态由谁推进尚未拍板，见 docs/DESIGN.md 的 A1 决策

依赖：services/order_service.py、services/recharge_service.py

注意：改状态是写操作，要走 service 的事务，不要在页面里直接调 repository。
"""
