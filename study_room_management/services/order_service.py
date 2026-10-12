"""预约订单业务：创建、查询、取消、状态流转。

⚠️ 命名提醒：本项目有两类「订单」——预约单（reservation）与充值单（recharge）。
   本文件只管【预约单】；充值单见 recharge_service.py。
   若觉得 order_service 容易混淆，可改名为 reservation_service.py。

职责：
    - 校验业务规则，失败时抛 BizError（带中文提示），由 ui 层统一捕获显示
    - 调用 repository 完成读写
    - 事务边界在本层，用 db/uow.py 的 with uow() as cur 打开

禁止：
    - 写 SQL（属于 repository/）
    - import streamlit
    - 直接操作 st.session_state（界面状态由 ui 层负责写）

预期函数（按需增删）：
    reserve(user_id, seat_id, card_id, reserve_date, start_time, hours) -> reservation
        并发风险的两道防线（缺一不可）：
          1) 取 user_card 时用 SELECT ... FOR UPDATE 锁住账户行
          2) INSERT 命中唯一索引 uk_seat_slot 时捕获 IntegrityError，
             转成 BizError("该时段已被预约")
        ⚠️ 扣余额与写预约必须在【同一个事务】里
    cancel(reservation_id, user_id)
        校验归属与状态 → 事务内：置 active_flag=NULL + 退款
    list_my_orders(user_id, page)
    check_in(reservation_id)            待使用 → 使用中（推进方式见 DESIGN.md A1）
    finish(reservation_id)              使用中 → 已完成
    list_orders(store_id, status, page) 管理端

扣费金额怎么算见 docs/DESIGN.md 的 A3 决策，定完在这里实现。
"""
