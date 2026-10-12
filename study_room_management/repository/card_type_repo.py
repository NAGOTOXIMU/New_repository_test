"""卡种表（card_type）的数据访问。

本层只做一件事：执行 SQL，把结果返回给 services。
    - 查询返回 dict 或 list[dict]（连接使用 DictCursor）
    - 写操作返回影响行数或新主键
    - 全部使用 %s 占位符参数化，严禁字符串拼接（防 SQL 注入）

禁止：
    - 任何业务判断（"余额够不够"由 services 决定怎么处理）
    - import streamlit
    - 自己开事务（事务由 services 通过 db/uow.py 打开）

预期函数（按需增删）：
    get_by_id(card_type_id)
    list_online()                        用户端只能看到「上架」的卡种
    list_paged(offset, limit)            管理端全部（含已下架）
    create(name, kind, price, face_value, total_times, total_hours,
           valid_days, discount)
    update(card_type_id, **fields)
    update_status(card_type_id, status)  上架 / 下架

注意：下架不等于删除 —— 已售出的卡还要能查到它的卡种信息，
      所以本表不做物理删除，用 status 控制是否可售。
"""
