"""充值 / 购卡订单表（recharge）的数据访问。

本层只做一件事：执行 SQL，把结果返回给 services。
    - 查询返回 dict 或 list[dict]（连接使用 DictCursor）
    - 写操作返回影响行数或新主键
    - 全部使用 %s 占位符参数化，严禁字符串拼接（防 SQL 注入）

禁止：
    - 任何业务判断（"余额够不够"由 services 决定怎么处理）
    - import streamlit
    - 自己开事务（事务由 services 通过 db/uow.py 打开）

预期函数（按需增删）：
    create(order_no, user_id, card_type_id, amount, pay_method) -> 新 recharge_id
        status 默认 '待支付'
    get_by_order_no(order_no)           幂等校验用
        ⚠️ order_no 有唯一索引：用户双击按钮 / 刷新页面重复提交时，
           第二次插入会抛 IntegrityError，services 捕获后返回"订单已存在"
    mark_paid(recharge_id, card_id)     SET status='已支付', paid_at=NOW(), card_id=?
    cancel(recharge_id)                 取消未支付订单
    list_by_user(user_id, offset, limit)
    list_paged(status, offset, limit)   管理端
    sum_amount_by_period(start, end)    数据看板：区间营收统计

⚠️ 缺口提醒：user_card（用户持有的卡）目前没有独立的 repo 文件。
   它是充值到账和预约扣费都要写的中枢表，建议单独建 repository/user_card_repo.py，
   或明确约定暂时并入本文件。加的东西：get_active(user_id) / get_for_update(card_id)
   / add_balance(...) / deduct(...) / create_from_card_type(...)。
"""
