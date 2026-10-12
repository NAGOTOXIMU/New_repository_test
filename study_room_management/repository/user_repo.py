"""用户表（`user`）的数据访问。

本层只做一件事：执行 SQL，把结果返回给 services。
    - 查询返回 dict 或 list[dict]（连接使用 DictCursor）
    - 写操作返回影响行数或新主键
    - 全部使用 %s 占位符参数化，严禁字符串拼接（防 SQL 注入）

禁止：
    - 任何业务判断（"余额够不够"由 services 决定怎么处理）
    - import streamlit
    - 自己开事务（事务由 services 通过 db/uow.py 打开）

预期函数（按需增删）：
    get_by_id(user_id)                  查单个用户
    get_by_username(username)           登录用
    exists_username(username)           注册查重
    exists_phone(phone)                 注册查重
    create(username, password_hash, real_name, phone, email) -> 新 user_id
    update_profile(user_id, real_name, phone, email)
    update_password(user_id, password_hash)
    update_status(user_id, status)      冻结 / 解冻
    list_paged(keyword, offset, limit)  管理端列表（服务端分页）
    count(keyword)                      分页总数
"""
