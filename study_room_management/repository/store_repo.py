"""门店表（store）的数据访问。

本层只做一件事：执行 SQL，把结果返回给 services。
    - 查询返回 dict 或 list[dict]（连接使用 DictCursor）
    - 写操作返回影响行数或新主键
    - 全部使用 %s 占位符参数化，严禁字符串拼接（防 SQL 注入）

禁止：
    - 任何业务判断（"余额够不够"由 services 决定怎么处理）
    - import streamlit
    - 自己开事务（事务由 services 通过 db/uow.py 打开）

预期函数（按需增删）：
    get_by_id(store_id)
    list_all(status=None)               用户端门店列表（只取营业中）
    list_paged(keyword, offset, limit)  管理端分页列表
    count(keyword)
    create(name, address, phone, open_time, close_time)
    update(store_id, **fields)          局部更新
    update_status(store_id, status)     营业 / 停业
"""
