"""用户端 · 我的订单。

职责：
    - 列出当前用户的预约记录（服务端分页），显示状态、座位、时段、金额
    - 提供「取消预约」→ 调 services/order_service.cancel(...)
      取消会退款并释放时段，界面要二次确认
    - 也可用 Tab 展示充值记录，调 recharge_service.list_my_recharges

注意：列表必须服务端分页（LIMIT / OFFSET），不要把整表拉进 st.dataframe。
"""
