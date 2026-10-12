"""数据库连接。

一般不用直接调 get_conn()，用下面的 read_cursor() / write_cursor() 即可。
"""
from contextlib import contextmanager

import pymysql

from config import DB_CONFIG


def get_conn(autocommit: bool = False):
    """新建一条连接。DictCursor 让查询结果返回 dict 而不是元组。"""
    return pymysql.connect(
        **DB_CONFIG,
        autocommit=autocommit,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,      # MySQL 没启动时最多等 5 秒
    )


@contextmanager
def read_cursor():
    """只读查询用。自动开关连接：

        with read_cursor() as cur:
            cur.execute("SELECT ...")
            rows = cur.fetchall()
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


@contextmanager
def write_cursor():
    """写入用。自动开关连接，并负责 COMMIT / ROLLBACK：

        with write_cursor() as cur:
            cur.execute("INSERT ...")
            return cur.lastrowid

    注意：跨多张表的写操作不要用它，用 db/uow.py 的 uow()。
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


def check_connection() -> tuple[bool, str]:
    """连通性自检，返回 (是否成功, 说明文字)。"""
    try:
        conn = get_conn()
    except Exception as e:
        return False, f"连接失败：{e}"
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION() AS version, DATABASE() AS db")
            row = cur.fetchone()
        return True, f"连接成功：MySQL {row['version']}，当前库 {row['db']}"
    except Exception as e:
        return False, f"已连上但查询失败：{e}"
    finally:
        conn.close()
