"""充值订单表（recharge）数据访问。

注意：order_no 有唯一索引，重复插入抛 IntegrityError，service 要转成友好提示。
"""
import uuid
from datetime import date

from db.connection import read_cursor, write_cursor

_FIELDS = ("recharge_id, order_no, user_id, card_type_id, card_id, amount, "
           "pay_method, status, paid_at, created_at")

_JOINED = (
    "SELECT r.recharge_id, r.order_no, r.user_id, r.card_type_id, r.card_id, "
    "       r.amount, r.pay_method, r.status, r.paid_at, r.created_at, "
    "       ct.name AS card_type_name, ct.kind AS card_type_kind "
    "FROM recharge r "
    "JOIN card_type ct ON r.card_type_id = ct.card_type_id "
)


def generate_order_no():
    """充值单号：RC + 日期 + 8 位随机。"""
    return "RC" + date.today().strftime("%Y%m%d") + uuid.uuid4().hex[:8].upper()


def get_by_id(recharge_id):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM recharge WHERE recharge_id = %s", (recharge_id,))
        return cur.fetchone()


def get_by_order_no(order_no):
    """按单号查（幂等校验用）。"""
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM recharge WHERE order_no = %s", (order_no,))
        return cur.fetchone()


def create(order_no, user_id, card_type_id, amount, pay_method="微信"):
    """创建订单（状态默认"待支付"），返回 recharge_id。order_no 撞了会抛 IntegrityError。"""
    with write_cursor() as cur:
        cur.execute(
            "INSERT INTO recharge (order_no, user_id, card_type_id, amount, pay_method) "
            "VALUES (%s, %s, %s, %s, %s)",
            (order_no, user_id, card_type_id, amount, pay_method),
        )
        return cur.lastrowid


def mark_paid(recharge_id, card_id=None, cur=None):
    """标记为已支付并记下生成的卡。返回 1 = 成功，0 = 这单已不是待支付。

    靠 WHERE status = '待支付' 保证不会重复支付同一单。
    """
    sql = ("UPDATE recharge SET status = '已支付', paid_at = NOW(), card_id = %s "
           "WHERE recharge_id = %s AND status = '待支付'")
    args = (card_id, recharge_id)
    if cur is not None:
        cur.execute(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, args)
        return c.rowcount


def cancel(recharge_id):
    """取消未支付的订单。"""
    with write_cursor() as cur:
        cur.execute(
            "UPDATE recharge SET status = '已取消' WHERE recharge_id = %s AND status = '待支付'",
            (recharge_id,),
        )
        return cur.rowcount


def list_by_user(user_id, offset=0, limit=20):
    with read_cursor() as cur:
        cur.execute(
            _JOINED + "WHERE r.user_id = %s ORDER BY r.recharge_id DESC LIMIT %s OFFSET %s",
            (user_id, limit, offset),
        )
        return cur.fetchall()


def count_by_user(user_id):
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM recharge WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        return row["n"] if row else 0


def list_paged(status=None, start_date=None, end_date=None, offset=0, limit=20):
    """管理端列表，可按状态、下单日期筛。"""
    sql = _JOINED
    where, params = [], []
    if status:
        where.append("r.status = %s")
        params.append(status)
    if start_date:
        where.append("DATE(r.created_at) >= %s")
        params.append(start_date)
    if end_date:
        where.append("DATE(r.created_at) <= %s")
        params.append(end_date)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY r.recharge_id DESC LIMIT %s OFFSET %s"
    params += [limit, offset]
    with read_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def count_paged(status=None, start_date=None, end_date=None):
    where, params = [], []
    if status:
        where.append("status = %s")
        params.append(status)
    if start_date:
        where.append("DATE(created_at) >= %s")
        params.append(start_date)
    if end_date:
        where.append("DATE(created_at) <= %s")
        params.append(end_date)
    sql = "SELECT COUNT(*) AS n FROM recharge"
    if where:
        sql += " WHERE " + " AND ".join(where)
    with read_cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row["n"] if row else 0


def sum_amount(start_date=None, end_date=None):
    """已支付订单的金额合计（营收）。"""
    with read_cursor() as cur:
        if start_date and end_date:
            cur.execute(
                "SELECT IFNULL(SUM(amount), 0) AS total FROM recharge "
                "WHERE status = '已支付' AND DATE(paid_at) BETWEEN %s AND %s",
                (start_date, end_date),
            )
        else:
            cur.execute("SELECT IFNULL(SUM(amount), 0) AS total FROM recharge "
                        "WHERE status = '已支付'")
        row = cur.fetchone()
        return row["total"] if row else 0


def revenue_by_day(start_date, end_date):
    """按天汇总的营收，给数据看板画折线图用。"""
    with read_cursor() as cur:
        cur.execute(
            "SELECT DATE(paid_at) AS day, COUNT(*) AS orders, SUM(amount) AS amount "
            "FROM recharge WHERE status = '已支付' AND DATE(paid_at) BETWEEN %s AND %s "
            "GROUP BY DATE(paid_at) ORDER BY day",
            (start_date, end_date),
        )
        return cur.fetchall()


def count_by_card_type():
    """各卡种卖了多少张，给看板画饼图用。"""
    with read_cursor() as cur:
        cur.execute(
            "SELECT ct.name, COUNT(*) AS n, SUM(r.amount) AS amount "
            "FROM recharge r JOIN card_type ct ON r.card_type_id = ct.card_type_id "
            "WHERE r.status = '已支付' GROUP BY ct.card_type_id, ct.name ORDER BY n DESC"
        )
        return cur.fetchall()
