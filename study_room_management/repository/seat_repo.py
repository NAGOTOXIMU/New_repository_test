"""座位表（seat）的数据访问。

本层只做一件事：执行 SQL，把结果返回给 services。
    - 查询返回 dict 或 list[dict]（连接使用 DictCursor）
    - 写操作返回影响行数或新主键
    - 全部使用 %s 占位符参数化，严禁字符串拼接（防 SQL 注入）

禁止：
    - 任何业务判断（"余额够不够"由 services 决定怎么处理）
    - import streamlit
    - 自己开事务（事务由 services 通过 db/uow.py 打开）

预期函数（按需增删）：
    get_by_id(seat_id)
    list_by_store(store_id, status=None)          某门店的座位列表
    list_available(store_id, reserve_date, start_time, end_time)
        关键查询：某门店在某时段内**仍然空闲**的座位
        （用 NOT EXISTS 排除已被有效预约占用的座位）
    create(store_id, seat_no, zone, price_per_hour)
    batch_create(items)                           批量新增座位
    update_status(seat_id, status)                可用 / 维修 / 停用

注意：判断"时段是否被占用"的真正兜底是 reservation 表的唯一索引，
       list_available 只服务于界面展示，不承担并发安全职责。
"""
