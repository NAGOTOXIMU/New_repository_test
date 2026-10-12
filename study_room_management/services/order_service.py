"""预约订单业务：创建、取消、状态流转。

注意：本项目有两类订单，本文件只管预约单（reservation），充值单见 recharge_service。
预期：reserve / cancel / list_my_orders / check_in / finish / list_orders
事务：预约要在同一个事务里"写预约 + 扣余额"，用 db/uow.py 的 uow()。
"""
