"""座位表（seat）数据访问。

规范要点：座位编号列叫 seat_code（不是 seat_no）；区域是 area_type(TINYINT)；
status 是 TINYINT（1 可用 / 0 维修中）。规范里座位表没有价格列，
计费口径由卡种决定（见 services/order_service.py）。
"""
from config import ORDER_CANCELLED
from db.connection import read_cursor, write_cursor

_FIELDS = ("seat_id, store_id, seat_code, area_type, has_socket, status, create_time")
_UPDATABLE = ("seat_code", "area_type", "has_socket", "status")


def get_by_id(seat_id):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM seat WHERE seat_id = %s", (seat_id,))
        return cur.fetchone()


def list_by_store(store_id, status=None):
    with read_cursor() as cur:
        if status is not None:
            cur.execute(
                f"SELECT {_FIELDS} FROM seat WHERE store_id = %s AND status = %s "
                "ORDER BY seat_code",
                (store_id, status),
            )
        else:
            cur.execute(
                f"SELECT {_FIELDS} FROM seat WHERE store_id = %s ORDER BY seat_code",
                (store_id,),
            )
        return cur.fetchall()


def count_by_store(store_id, status=None):
    with read_cursor() as cur:
        if status is not None:
            cur.execute("SELECT COUNT(*) AS n FROM seat WHERE store_id = %s AND status = %s",
                        (store_id, status))
        else:
            cur.execute("SELECT COUNT(*) AS n FROM seat WHERE store_id = %s", (store_id,))
        row = cur.fetchone()
        return row["n"] if row else 0


def list_available(store_id, reserve_date, start_time, end_time):
    """某门店在指定时段仍然空闲的座位。

    判断依据是区间重叠：已有预约的 start < 我要的 end，并且已有预约的 end > 我要的 start。
    active_flag IS NOT NULL 表示这条预约还占着时段（取消的会被置成 NULL）。
    已取消/已过期的订单必然 active_flag IS NULL，所以不会挡路。
    """
    with read_cursor() as cur:
        cur.execute(
            f"SELECT {_FIELDS} FROM seat s "
            "WHERE s.store_id = %s AND s.status = 1 AND NOT EXISTS ("
            "  SELECT 1 FROM reservation_order r WHERE r.seat_id = s.seat_id "
            "  AND r.reserve_date = %s AND r.active_flag IS NOT NULL "
            "  AND r.start_time < %s AND r.end_time > %s) "
            "ORDER BY s.seat_code",
            (store_id, reserve_date, end_time, start_time),
        )
        return cur.fetchall()


def is_free(seat_id, reserve_date, start_time, end_time):
    """单个座位在某时段是否空闲。返回 True / False。"""
    with read_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM reservation_order "
            "WHERE seat_id = %s AND reserve_date = %s AND active_flag IS NOT NULL "
            "AND start_time < %s AND end_time > %s",
            (seat_id, reserve_date, end_time, start_time),
        )
        row = cur.fetchone()
        return (row["n"] if row else 0) == 0


def create(store_id, seat_code, area_type=1, has_socket=1, cur=None):
    """新增一个座位，返回 seat_id。同门店 seat_code 重复会抛 IntegrityError。"""
    sql = ("INSERT INTO seat (store_id, seat_code, area_type, has_socket) "
           "VALUES (%s, %s, %s, %s)")
    args = (store_id, seat_code, area_type, has_socket)
    if cur is not None:
        cur.execute(sql, args)
        return cur.lastrowid
    with write_cursor() as c:
        c.execute(sql, args)
        return c.lastrowid


def batch_create(store_id, seats, cur=None):
    """批量新增。seats = [(seat_code, area_type, has_socket), ...]，返回成功条数。"""
    if not seats:
        return 0
    sql = ("INSERT INTO seat (store_id, seat_code, area_type, has_socket) "
           "VALUES (%s, %s, %s, %s)")
    args = [(store_id, code, area, sock) for (code, area, sock) in seats]
    if cur is not None:
        cur.executemany(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.executemany(sql, args)
        return c.rowcount


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
    """可用(1) / 维修中(0)。"""
    with write_cursor() as cur:
        cur.execute("UPDATE seat SET status = %s WHERE seat_id = %s", (status, seat_id))
        return cur.rowcount


def has_active_reservation(cur, seat_id, reserve_date, start_time, end_time):
    """事务内校验：该座位该时段是否已被有效预约占用。

    与 create 的原子性由 reservation_order.uk_seat_slot 唯一索引兜底，
    本函数只用于给出友好提示（先查后插在并发下不可靠，唯一索引才是防线）。
    """
    cur.execute(
        "SELECT COUNT(*) AS n FROM reservation_order "
        "WHERE seat_id = %s AND reserve_date = %s AND active_flag IS NOT NULL "
        "AND order_status <> %s AND start_time < %s AND end_time > %s",
        (seat_id, reserve_date, ORDER_CANCELLED, end_time, start_time),
    )
    row = cur.fetchone()
    return bool(row and row["n"] > 0)
