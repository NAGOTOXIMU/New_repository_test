"""门店与座位的管理业务。

职责：
    - 校验业务规则，失败时抛 BizError（带中文提示），由 ui 层统一捕获显示
    - 调用 repository 完成读写
    - 事务边界在本层，用 db/uow.py 的 with uow() as cur 打开

禁止：
    - 写 SQL（属于 repository/）
    - import streamlit
    - 直接操作 st.session_state（界面状态由 ui 层负责写）

预期函数（按需增删）：
    list_stores() / get_store(store_id)
    create_store(...) / update_store(...) / set_store_status(...)
    list_seats(store_id)
    batch_add_seats(store_id, prefix, count, zone, price_per_hour)
        批量新增座位（如 A01~A20），注意处理座位编号重复
    set_seat_status(seat_id, status)
    find_available_seats(store_id, reserve_date, start_time, end_time)
        组合查询：先取门店座位，再排除该时段已被占用的

权限范围：店长只能操作自己门店的数据（admin.store_id，见 DESIGN.md B2）。
"""
