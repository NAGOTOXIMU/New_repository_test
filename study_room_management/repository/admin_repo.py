"""管理员表（admin）的数据访问。

本层只做一件事：执行 SQL，把结果返回给 services。
    - 查询返回 dict 或 list[dict]（连接使用 DictCursor）
    - 写操作返回影响行数或新主键
    - 全部使用 %s 占位符参数化，严禁字符串拼接（防 SQL 注入）

禁止：
    - 任何业务判断（"余额够不够"由 services 决定怎么处理）
    - import streamlit
    - 自己开事务（事务由 services 通过 db/uow.py 打开）

预期函数（按需增删）：
    get_by_id(admin_id)
    get_by_username(username)          管理员登录用
    create(username, password_hash, real_name, phone, store_id)
    list_paged(offset, limit)
    update_status(admin_id, status)

注意：admin.store_id 为 NULL 表示超级管理员（可管所有门店），
      非 NULL 表示只负责那一个门店。管理端的查询要据此过滤数据，
      否则店长会看到别家门店的订单（见 docs/DESIGN.md 的 B2）。
"""
