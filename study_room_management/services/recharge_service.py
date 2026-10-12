"""充值 / 购卡业务，事务边界最典型的地方。

预期：create_order / pay / cancel_order / list_my_recharges / list_all
事务：支付要在一个事务里"订单改已支付 + 生成/更新 user_card"，两步同成同败。
幂等：order_no 唯一索引兜底，捕获 IntegrityError 就返回已存在的订单。
"""
