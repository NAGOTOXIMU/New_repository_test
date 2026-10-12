"""座位表（seat）数据访问。

注意：list_available 只服务于界面展示，真正的防抢座靠 reservation 的唯一索引。
"""
from db.connection import read_cursor, write_cursor

_FIELDS = "seat_id, store_id, seat_no, zone, price_per_hour, status"
_UPDATABLE = ("seat_no", "zone", "price_per_hour", "status")


def get_by_id(seat_id):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM seat WHERE seat_id = %s", (seat_id,))
        return cur.fetchone()


def list_by_store(store_id, status=None):
    with read_cursor() as cur:
        if status:
            cur.execute(f"SELECT {_FIELDS} FROM seat WHERE store_id = %s AND status = %s "
                        "ORDER BY seat_no", (store_id, status))
        else:
            cur.execute(f"SELECT {_FIELDS} FROM seat WHERE store_id = %s ORDER BY seat_no",
                        (store_id,))
        return cur.fetchall()


def list_available(store_id, reserve_date, start_time, end_time):
    """某门店在指定时段仍然空闲的座位。

    判断依据是区间重叠：已有预约的 start < 我要的 end，并且已有预约的 end > 我要的 start。
    active_flag IS NOT NULL 表示这条预约还占着时段（取消的会被置成 NULL）。
    """
    with read_cursor() as cur:
        cur.execute(
            "SELECT s.seat_id, s.seat_no, s.zone, s.price_per_hour FROM seat s "
            "WHERE s.store_id = %s AND s.status = '可用' AND NOT EXISTS ("
            "  SELECT 1 FROM reservation r WHERE r.seat_id = s.seat_id "
            "  AND r.reserve_date = %s AND r.active_flag IS NOT NULL "
            "  AND r.start_time < %s AND r.end_time > %s) "
            "ORDER BY s.seat_no",
            (store_id, reserve_date, end_time, start_time),
        )
        return cur.fetchall()


def is_free(seat_id, reserve_date, start_time, end_time):
    """单个座位在某时段是否空闲。返回 True / False。"""
    with read_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM reservation "
            "WHERE seat_id = %s AND reserve_date = %s AND active_flag IS NOT NULL "
            "AND start_time < %s AND end_time > %s",
            (seat_id, reserve_date, end_time, start_time),
        )
        row = cur.fetchone()
        return (row["n"] if row else 0) == 0


def create(store_id, seat_no, zone=None, price_per_hour=0):
    """新增一个座位，返回 seat_id。"""
    with write_cursor() as cur:
        cur.execute(
            "INSERT INTO seat (store_id, seat_no, zone, price_per_hour) "
            "VALUES (%s, %s, %s, %s)",
            (store_id, seat_no, zone, price_per_hour),
        )
        return cur.lastrowid


def batch_create(store_id, seats):
    """批量新增。seats = [(seat_no, zone, price_per_hour), ...]，返回成功条数。"""
    if not seats:
        return 0
    with write_cursor() as cur:
        cur.executemany(
            "INSERT INTO seat (store_id, seat_no, zone, price_per_hour) "
            "VALUES (%s, %s, %s, %s)",
            [(store_id, no, zone, price) for (no, zone, price) in seats],
        )
        return cur.rowcount


def update(seat_id, **fields):
    """局部更新，只接受 _UPDATABLE 里的字段。"""
    updates = {k: v for k, v in fields.items() if k in _UPDATABLE}
    if not updates:
        return 0
    sets = ", ".join(f"{k} = %s" for k in updates)
    with write_cursor() as cur:
        cur.execute(f"UPDATE seat SET {sets} WHERE seat_id = %s",
                    list(updates.values()) + [seat_id])
        return cur.rowcount


def update_status(seat_id, status):
    """可用 / 维修 / 停用。"""
    with write_cursor() as cur:
        cur.execute("UPDATE seat SET status = %s WHERE seat_id = %s", (status, seat_id))
        return cur.rowcount


def count_by_store(store_id, status=None):
    with read_cursor() as cur:
        if status:
            cur.execute("SELECT COUNT(*) AS n FROM seat WHERE store_id = %s AND status = %s",
                        (store_id, status))
        else:
            cur.execute("SELECT COUNT(*) AS n FROM seat WHERE store_id = %s", (store_id,))
        row = cur.fetchone()
        return row["n"] if row else 0
