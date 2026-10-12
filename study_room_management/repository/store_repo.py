"""门店表（store）数据访问。"""
from db.connection import read_cursor, write_cursor

_FIELDS = "store_id, name, address, phone, open_time, close_time, status"
_UPDATABLE = ("name", "address", "phone", "open_time", "close_time")


def get_by_id(store_id):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM store WHERE store_id = %s", (store_id,))
        return cur.fetchone()


def list_all(status=None):
    """门店列表。传 status='营业' 就只取营业中的（用户端用）。"""
    with read_cursor() as cur:
        if status:
            cur.execute(f"SELECT {_FIELDS} FROM store WHERE status = %s ORDER BY store_id",
                        (status,))
        else:
            cur.execute(f"SELECT {_FIELDS} FROM store ORDER BY store_id")
        return cur.fetchall()


def list_paged(keyword=None, offset=0, limit=20):
    """管理端分页列表。"""
    with read_cursor() as cur:
        if keyword:
            cur.execute(
                f"SELECT {_FIELDS} FROM store WHERE name LIKE %s OR address LIKE %s "
                "ORDER BY store_id LIMIT %s OFFSET %s",
                (f"%{keyword}%", f"%{keyword}%", limit, offset),
            )
        else:
            cur.execute(f"SELECT {_FIELDS} FROM store ORDER BY store_id LIMIT %s OFFSET %s",
                        (limit, offset))
        return cur.fetchall()


def count(keyword=None):
    with read_cursor() as cur:
        if keyword:
            cur.execute("SELECT COUNT(*) AS n FROM store WHERE name LIKE %s OR address LIKE %s",
                        (f"%{keyword}%", f"%{keyword}%"))
        else:
            cur.execute("SELECT COUNT(*) AS n FROM store")
        return cur.fetchone()["n"]


def create(name, address, phone=None, open_time="08:00:00", close_time="22:00:00"):
    """新增门店，返回 store_id。"""
    with write_cursor() as cur:
        cur.execute(
            "INSERT INTO store (name, address, phone, open_time, close_time) "
            "VALUES (%s, %s, %s, %s, %s)",
            (name, address, phone, open_time, close_time),
        )
        return cur.lastrowid


def update(store_id, **fields):
    """局部更新，只接受 _UPDATABLE 里的字段，返回影响行数。

    注意：列名不能用 %s 占位符，所以这里是拼字符串；因为列名来自白名单，安全。
    """
    updates = {k: v for k, v in fields.items() if k in _UPDATABLE}
    if not updates:
        return 0
    sets = ", ".join(f"{k} = %s" for k in updates)
    with write_cursor() as cur:
        cur.execute(f"UPDATE store SET {sets} WHERE store_id = %s",
                    list(updates.values()) + [store_id])
        return cur.rowcount


def update_status(store_id, status):
    """营业 / 停业。"""
    with write_cursor() as cur:
        cur.execute("UPDATE store SET status = %s WHERE store_id = %s", (status, store_id))
        return cur.rowcount
