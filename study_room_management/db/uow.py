"""事务上下文管理器（Unit of Work）。

职责：
    提供 with uow() as cur: 的写法，把「开事务 / 提交 / 回滚」收敛到一处：
        - 进入后执行第一条 SQL 即开启事务（pymysql 默认 autocommit=False）
        - 正常退出时 COMMIT
        - 中途抛异常时自动 ROLLBACK，并把异常继续往上抛

设计约定：
    - 事务边界【只允许】从 services/ 层打开，repository 不许自己开事务
      （只有 service 知道"扣费"和"占时段"是一个不可分割的业务动作）
    - 这里不写业务判断，也不写 SQL

用法示意：
    from db.uow import uow

    def reserve(...):
        with uow() as cur:
            cur.execute("UPDATE user_card SET balance = balance - %s WHERE card_id = %s",
                        (amount, card_id))
            cur.execute("INSERT INTO reservation (...) VALUES (...)", (...))
        # 两句话同成同败：上面任何一步抛异常，整体回滚，余额不会被扣掉
"""
from contextlib import contextmanager

from db.connection import get_conn


@contextmanager
def uow():
    """打开一个事务，yield 一个游标。

        with uow() as cur:
            ...多条写操作...

    正常走完 → COMMIT；抛异常 → ROLLBACK 后把异常抛给调用方。
    无论成功失败，连接都会在 finally 里关闭。
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
