"""预约表（reservation）数据访问，本项目最核心的表。

注意：
    - create 违反唯一索引 uk_seat_slot 会抛 IntegrityError，service 要转成友好提示
    - cancel 必须把 active_flag 置为 NULL，否则那个时段不会被释放
"""
import uuid
from datetime import date

from db.connection import read_cursor, write_cursor

_FIELDS = ("reservation_id, order_no, user_id, seat_id, card_id, reserve_date, "
           "start_time, end_time, hours, amount, status, active_flag")

_JOINED = (
    "SELECT r.reservation_id, r.order_no, r.reserve_date, r.start_time, r.end_time, "
    "       r.hours, r.amount, r.status, r.created_at, "
    "       s.seat_no, s.zone, st.store_id, st.name AS store_name "
    "FROM reservation r "
    "JOIN seat s ON r.seat_id = s.seat_id "
    "JOIN store st ON s.store_id = st.store_id "
)


def generate_order_no():
    """预约单号：R + 日期 + 8 位随机。"""
    return "R" + date.today().strftime("%Y%m%d") + uuid.uuid4().hex[:8].upper()


def get_by_id(reservation_id):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM reservation WHERE reservation_id = %s",
                    (reservation_id,))
        return cur.fetchone()


def get_by_order_no(order_no):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM reservation WHERE order_no = %s", (order_no,))
        return cur.fetchone()


def is_slot_taken(seat_id, reserve_date, start_time):
    """该座位、该日期、该开始时间是否已经有有效预约。"""
    with read_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM reservation "
            "WHERE seat_id = %s AND reserve_date = %s AND start_time = %s "
            "AND active_flag IS NOT NULL",
            (seat_id, reserve_date, start_time),
        )
        return cur.fetchone()["n"] > 0


def create(order_no, user_id, seat_id, reserve_date, start_time, end_time,
           hours, amount, card_id=None):
    """写入一条预约，返回 reservation_id。

    ⚠️ 如果这个座位该时段已被占用，会抛 pymysql.err.IntegrityError
       （唯一索引 uk_seat_slot 拦下的），调用方要捕获它。
    """
    with write_cursor() as cur:
        cur.execute(
            "INSERT INTO reservation (order_no, user_id, seat_id, card_id, reserve_date, "
            "start_time, end_time, hours, amount) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (order_no, user_id, seat_id, card_id, reserve_date,
             start_time, end_time, hours, amount),
        )
        return cur.lastrowid


def cancel(reservation_id):
    """取消预约：状态改成已取消，并把 active_flag 置 NULL 释放时段。"""
    with write_cursor() as cur:
        cur.execute(
            "UPDATE reservation SET status = '已取消', active_flag = NULL "
            "WHERE reservation_id = %s AND status IN ('待使用', '使用中')",
            (reservation_id,),
        )
        return cur.rowcount


def update_status(reservation_id, status):
    """推进状态：待使用 / 使用中 / 已完成。"""
    with write_cursor() as cur:
        cur.execute("UPDATE reservation SET status = %s WHERE reservation_id = %s",
                    (status, reservation_id))
        return cur.rowcount


def list_by_user(user_id, offset=0, limit=20):
    """我的订单（带座位号和门店名）。"""
    with read_cursor() as cur:
        cur.execute(
            _JOINED + "WHERE r.user_id = %s "
            "ORDER BY r.reserve_date DESC, r.start_time DESC LIMIT %s OFFSET %s",
            (user_id, limit, offset),
        )
        return cur.fetchall()


def count_by_user(user_id):
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM reservation WHERE user_id = %s", (user_id,))
        return cur.fetchone()["n"]


def list_paged(store_id=None, status=None, offset=0, limit=20):
    """管理端订单列表，可按门店和状态筛。"""
    where, params = [], []
    if store_id:
        where.append("st.store_id = %s")
        params.append(store_id)
    if status:
        where.append("r.status = %s")
        params.append(status)
    sql = _JOINED + (" WHERE " + " AND ".join(where) if where else "")
    sql += " ORDER BY r.reservation_id DESC LIMIT %s OFFSET %s"
    params += [limit, offset]
    with read_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def count_paged(store_id=None, status=None):
    """配合 list_paged 算总数。"""
    sql = ("SELECT COUNT(*) AS n FROM reservation r "
           "JOIN seat s ON r.seat_id = s.seat_id "
           "JOIN store st ON s.store_id = st.store_id")
    where, params = [], []
    if store_id:
        where.append("st.store_id = %s")
        params.append(store_id)
    if status:
        where.append("r.status = %s")
        params.append(status)
    if where:
        sql += " WHERE " + " AND ".join(where)
    with read_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()["n"]


def count_by_status(status):
    """看板用：某状态的预约数。"""
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM reservation WHERE status = %s", (status,))
        return cur.fetchone()["n"]


def count_between(start_date, end_date, store_id=None):
    """看板用：某日期区间内的预约数。"""
    sql = ("SELECT COUNT(*) AS n FROM reservation r "
           "JOIN seat s ON r.seat_id = s.seat_id")
    params = [start_date, end_date]
    if store_id:
        sql += " WHERE s.store_id = %s AND r.reserve_date BETWEEN %s AND %s"
        params = [store_id, start_date, end_date]
    else:
        sql += " WHERE r.reserve_date BETWEEN %s AND %s"
    with read_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()["n"]
