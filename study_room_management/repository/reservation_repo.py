"""预约表（reservation）数据访问，本项目最核心的表。

预期：get_by_id / is_slot_taken / create / cancel / list_by_user / update_status / list_paged
注意：
    - 插入违反唯一索引 uk_seat_slot 会抛 IntegrityError，service 要转成"该时段已被占用"
    - 取消预约必须 SET active_flag = NULL，否则时段不会被释放
"""
