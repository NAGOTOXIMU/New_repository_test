"""门店表（store）数据访问。

规范要点：列名是 store_name（不是 name）、status 是 TINYINT、时间列 create_time。
"""
from config import STATUS_ON
from db.connection import read_cursor, write_cursor

_FIELDS = "store_id, store_name, address, open_time, close_time, seat_count, status, create_time"
_UPDATABLE = ("store_name", "address", "open_time", "close_time", "seat_count")


def get_by_id(store_id):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM store WHERE store_id = %s", (store_id,))
        return cur.fetchone()


def list_all(status=None):
    """门店列表。传 status=1 就只取营业中的（用户端用）。"""
    with read_cursor() as cur:
        if status is not None:
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
                f"SELECT {_FIELDS} FROM store WHERE store_name LIKE %s OR address LIKE %s "
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
            cur.execute(
                "SELECT COUNT(*) AS n FROM store WHERE store_name LIKE %s OR address LIKE %s",
                (f"%{keyword}%", f"%{keyword}%"),
            )
        else:
            cur.execute("SELECT COUNT(*) AS n FROM store")
        row = cur.fetchone()
        return row["n"] if row else 0


def create(store_name, address, open_time="08:00:00", close_time="22:00:00", seat_count=0):
    """新增门店，返回 store_id。store_name 撞唯一索引会抛 IntegrityError。"""
    with write_cursor() as cur:
        cur.execute(
            "INSERT INTO store (store_name, address, open_time, close_time, seat_count) "
            "VALUES (%s, %s, %s, %s, %s)",
            (store_name, address, open_time, close_time, seat_count),
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
    """营业(1) / 停业(0)。"""
    with write_cursor() as cur:
        cur.execute("UPDATE store SET status = %s WHERE store_id = %s", (status, store_id))
        return cur.rowcount


def sync_seat_count(store_id, cur=None):
    """把「该门店实际座位数」回写 store.seat_count（冗余字段保持一致）。"""
    sql = ("UPDATE store s SET s.seat_count = ("
           "  SELECT COUNT(*) FROM seat WHERE seat.store_id = s.store_id"
           ") WHERE s.store_id = %s")
    if cur is not None:
        cur.execute(sql, (store_id,))
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, (store_id,))
        return c.rowcount
