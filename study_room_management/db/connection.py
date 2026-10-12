"""数据库连接。每次调用新建一条连接，用完必须 close()。

注意：跨多张表的写操作请用 db/uow.py 的 uow()。
"""
import pymysql

from config import DB_CONFIG


def get_conn(autocommit: bool = False):
    """新建一条连接。DictCursor 让查询结果返回 dict 而不是元组。"""
    return pymysql.connect(
        **DB_CONFIG,
        autocommit=autocommit,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,      # MySQL 没启动时最多等 5 秒，别让人干等
    )


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
