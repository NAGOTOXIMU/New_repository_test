"""充值订单表（recharge）数据访问。

预期：create / get_by_order_no / mark_paid / cancel / list_by_user / sum_amount_by_period
注意：order_no 有唯一索引，重复插入抛 IntegrityError，service 要转成友好提示。

待办：user_card 表还没有对应 repo，建议单独建 repository/user_card_repo.py。
"""
