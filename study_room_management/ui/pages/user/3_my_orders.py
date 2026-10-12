"""用户端 · 我的订单。

列出预约记录并支持取消（调 order_service.cancel，会退款并释放时段）。
注意：列表必须服务端分页，不要把整表拉进 st.dataframe。
"""
