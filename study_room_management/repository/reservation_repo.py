"""预约表（reservation）的数据访问 —— 本项目最核心的表。

本层只做一件事：执行 SQL，把结果返回给 services。
    - 查询返回 dict 或 list[dict]（连接使用 DictCursor）
    - 写操作返回影响行数或新主键
    - 全部使用 %s 占位符参数化，严禁字符串拼接（防 SQL 注入）

禁止：
    - 任何业务判断（"余额够不够"由 services 决定怎么处理）
    - import streamlit
    - 自己开事务（事务由 services 通过 db/uow.py 打开）

预期函数（按需增删）：
    get_by_id(reservation_id)
    get_by_order_no(order_no)
    is_slot_taken(seat_id, reserve_date, start_time)
        查该座位该时段是否已有有效预约（active_flag IS NOT NULL）
    create(order_no, user_id, seat_id, card_id, reserve_date,
           start_time, end_time, hours, amount) -> 新 reservation_id
        ⚠️ 插入若违反唯一索引 uk_seat_slot 会抛 IntegrityError，
           services 层必须捕获它并转成"该时段已被占用"的业务提示
    cancel(reservation_id)
        取消：SET status='已取消', active_flag=NULL（置 NULL 才会释放时段）
    list_by_user(user_id, offset, limit)     我的订单
    update_status(reservation_id, status)    待使用 → 使用中 → 已完成
    list_paged(store_id, status, offset, limit)  管理端订单列表

关于并发：抢座的最后一道防线是数据库的唯一索引 uk_seat_slot，
         不是本文件的查询，别把安全性寄托在 SELECT 上。
"""
