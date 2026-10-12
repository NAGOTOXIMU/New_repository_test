"""事务管理器。

    with uow() as cur:
        cur.execute(...)
        cur.execute(...)
    # 正常结束自动 COMMIT，抛异常自动 ROLLBACK

注意：事务只能从 services 层打开，repository 不许自己开事务。
"""
from contextlib import contextmanager

from db.connection import get_conn


@contextmanager
def uow():
    """打开一个事务并产出游标，自动 COMMIT / ROLLBACK / 关连接。"""
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
