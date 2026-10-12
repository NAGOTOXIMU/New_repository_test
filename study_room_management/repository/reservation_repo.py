"""预约订单表（reservation_order）数据访问，本项目最核心的表。

规范要点：主键 order_id；时段列是 reserve_date / start_time / end_time；
时长列是 duration（单位分钟）；状态列是 order_status(TINYINT)。

并发安全（★ 关键）：
    create() 违反唯一索引 uk_seat_slot 会抛 IntegrityError，
    这是「同一座位同一时段只能有一条有效预约」的**唯一可靠防线**。
    「先查后插」在并发下不可靠，只能用于给用户友好提示。

取消：
    cancel() 必须把 active_flag 置为 NULL，否则那个时段不会被释放。
"""
import uuid
from datetime import date

from config import ORDER_CANCELLED, ORDER_DONE, ORDER_ONGOING, ORDER_PENDING
from db.connection import read_cursor, write_cursor

_FIELDS = ("order_id, order_no, user_id, seat_id, store_id, card_id, reserve_date, "
           "start_time, end_time, duration, amount, order_status, active_flag, create_time")

# 列表页要带座位号、区域、门店名、持卡号
_JOINED = (
    "SELECT r.order_id, r.order_no, r.user_id, r.seat_id, r.store_id, r.card_id, "
    "       r.reserve_date, r.start_time, r.end_time, r.duration, r.amount, "
    "       r.order_status, r.active_flag, r.create_time, "
    "       s.seat_code, s.area_type, "
    "       st.store_name, "
    "       uc.card_no "
    "FROM reservation_order r "
    "JOIN seat s ON r.seat_id = s.seat_id "
    "JOIN store st ON r.store_id = st.store_id "
    "LEFT JOIN user_card uc ON r.card_id = uc.card_id "
)


def generate_order_no():
    """预约单号：R + 日期 + 8 位随机。"""
    return "R" + date.today().strftime("%Y%m%d") + uuid.uuid4().hex[:8].upper()


def get_by_id(order_id):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM reservation_order WHERE order_id = %s", (order_id,))
        return cur.fetchone()


def get_by_id_joined(order_id):
    with read_cursor() as cur:
        cur.execute(_JOINED + "WHERE r.order_id = %s", (order_id,))
        return cur.fetchone()


def get_by_order_no(order_no):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM reservation_order WHERE order_no = %s", (order_no,))
        return cur.fetchone()


def is_slot_taken(seat_id, reserve_date, start_time):
    """该座位、该日期、该开始时间是否已经有有效预约（仅用于友好提示）。"""
    with read_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM reservation_order "
            "WHERE seat_id = %s AND reserve_date = %s AND start_time = %s "
            "AND active_flag IS NOT NULL",
            (seat_id, reserve_date, start_time),
        )
        row = cur.fetchone()
        return bool(row and row["n"] > 0)


def create(order_no, user_id, seat_id, store_id, reserve_date, start_time, end_time,
           duration, amount, card_id=None, cur=None):
    """写入一条预约订单，返回 order_id。

    ⚠️ 这个座位该时段若已被占用，会抛 pymysql.err.IntegrityError（uk_seat_slot 拦下）。
    """
    sql = ("INSERT INTO reservation_order (order_no, user_id, seat_id, store_id, card_id, "
           "reserve_date, start_time, end_time, duration, amount) "
           "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
    args = (order_no, user_id, seat_id, store_id, card_id, reserve_date,
            start_time, end_time, duration, amount)
    if cur is not None:
        cur.execute(sql, args)
        return cur.lastrowid
    with write_cursor() as c:
        c.execute(sql, args)
        return c.lastrowid


def cancel(order_id, cur=None):
    """取消预约：状态改成「已取消(4)」，并把 active_flag 置 NULL 释放时段。"""
    sql = ("UPDATE reservation_order SET order_status = %s, active_flag = NULL "
           "WHERE order_id = %s AND order_status IN (%s, %s)")
    args = (ORDER_CANCELLED, order_id, ORDER_PENDING, ORDER_ONGOING)
    if cur is not None:
        cur.execute(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, args)
        return c.rowcount


def update_status(order_id, order_status, cur=None):
    """推进状态：1 待使用 / 2 进行中 / 3 已完成。"""
    sql = "UPDATE reservation_order SET order_status = %s WHERE order_id = %s"
    args = (order_status, order_id)
    if cur is not None:
        cur.execute(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, args)
        return c.rowcount


def expire_overdue(cur=None):
    """把「已过预约日期且仍未使用」的订单标成已过期(5)，并释放时段。

    返回被更新的行数。建议由管理端或定时任务调用。
    """
    sql = ("UPDATE reservation_order SET order_status = %s, active_flag = NULL "
           "WHERE order_status IN (%s, %s) AND reserve_date < CURDATE()")
    args = (5, ORDER_PENDING, ORDER_ONGOING)   # 5 = 已过期
    if cur is not None:
        cur.execute(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, args)
        return c.rowcount


def list_by_user(user_id, offset=0, limit=20):
    """我的订单（带座位号、门店名、卡号）。"""
    with read_cursor() as cur:
        cur.execute(
            _JOINED + "WHERE r.user_id = %s "
            "ORDER BY r.reserve_date DESC, r.start_time DESC LIMIT %s OFFSET %s",
            (user_id, limit, offset),
        )
        return cur.fetchall()


def count_by_user(user_id):
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM reservation_order WHERE user_id = %s",
                    (user_id,))
        row = cur.fetchone()
        return row["n"] if row else 0


def list_paged(store_id=None, order_status=None, start_date=None, end_date=None,
               offset=0, limit=20):
    """管理端订单列表，可按门店、状态、预约日期区间筛。

    start_date / end_date 是预约日期（reserve_date）的闭区间，
    传 date 或 'YYYY-MM-DD' 字符串都行；只传一端就是单边条件。
    """
    where, params = [], []
    if store_id:
        where.append("r.store_id = %s")
        params.append(store_id)
    if order_status:
        where.append("r.order_status = %s")
        params.append(order_status)
    if start_date:
        where.append("r.reserve_date >= %s")
        params.append(start_date)
    if end_date:
        where.append("r.reserve_date <= %s")
        params.append(end_date)
    sql = _JOINED + (" WHERE " + " AND ".join(where) if where else "")
    sql += " ORDER BY r.order_id DESC LIMIT %s OFFSET %s"
    params += [limit, offset]
    with read_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def count_paged(store_id=None, order_status=None, start_date=None, end_date=None):
    """配合 list_paged 算总数，筛选条件必须和 list_paged 完全一致。"""
    sql = "SELECT COUNT(*) AS n FROM reservation_order r"
    where, params = [], []
    if store_id:
        where.append("r.store_id = %s")
        params.append(store_id)
    if order_status:
        where.append("r.order_status = %s")
        params.append(order_status)
    if start_date:
        where.append("r.reserve_date >= %s")
        params.append(start_date)
    if end_date:
        where.append("r.reserve_date <= %s")
        params.append(end_date)
    if where:
        sql += " WHERE " + " AND ".join(where)
    with read_cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row["n"] if row else 0


def count_by_status(order_status):
    """看板用：某状态的预约数。"""
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM reservation_order WHERE order_status = %s",
                    (order_status,))
        row = cur.fetchone()
        return row["n"] if row else 0


def count_between(start_date, end_date, store_id=None):
    """看板用：某日期区间内的预约数。"""
    sql = "SELECT COUNT(*) AS n FROM reservation_order r"
    params = [start_date, end_date]
    if store_id:
        sql += " WHERE r.store_id = %s AND r.reserve_date BETWEEN %s AND %s"
        params = [store_id, start_date, end_date]
    else:
        sql += " WHERE r.reserve_date BETWEEN %s AND %s"
    with read_cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row["n"] if row else 0


def count_by_hour(store_id=None, days=30):
    """按开始时间的小时统计预约量（看热门时段）。"""
    sql = ("SELECT HOUR(r.start_time) AS hour, COUNT(*) AS n "
           "FROM reservation_order r "
           "WHERE r.reserve_date >= CURDATE() - INTERVAL %s DAY "
           "AND r.order_status <> %s")
    params = [days, ORDER_CANCELLED]
    if store_id:
        sql += " AND r.store_id = %s"
        params.append(store_id)
    sql += " GROUP BY HOUR(r.start_time) ORDER BY hour"
    with read_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def count_by_store(start_date, end_date):
    """按门店统计预约量（看板用）。"""
    with read_cursor() as cur:
        cur.execute(
            "SELECT st.store_id, st.store_name, COUNT(r.order_id) AS n "
            "FROM store st LEFT JOIN reservation_order r "
            "  ON r.store_id = st.store_id AND r.reserve_date BETWEEN %s AND %s "
            "GROUP BY st.store_id, st.store_name ORDER BY st.store_id",
            (start_date, end_date),
        )
        return cur.fetchall()
