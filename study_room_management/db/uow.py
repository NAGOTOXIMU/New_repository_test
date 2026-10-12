"""事务上下文管理器（Unit of Work）。

职责：
    提供 with uow() as cur: 的写法，把「开事务 / 提交 / 回滚」收敛到一处：
        - 进入时 BEGIN
        - 正常退出时 COMMIT
        - 中途抛异常时自动 ROLLBACK

设计约定：
    - 事务边界【只允许】从 services/ 层打开，repository 不许自己开事务
      （只有 service 知道"扣费"和"占时段"是一个不可分割的业务动作）
    - 这里不写业务判断，也不写 SQL

用法示意：
    with uow() as cur:
        cur.execute("UPDATE user_card SET balance = balance - %s WHERE card_id = %s", (amt, cid))
        cur.execute("INSERT INTO reservation (...) VALUES (...)", (...))
    # 两句话同成同败：上面任何一步抛异常，整体回滚
"""
