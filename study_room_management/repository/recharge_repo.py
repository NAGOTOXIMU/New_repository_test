"""充值订单表（recharge_order）数据访问。

规范要点：主键 recharge_id；支付状态列是 pay_status(0待支付 1已支付 2已退款)；
支付时间列是 pay_time。

order_no 是幂等键：用户重复点击「提交」时靠它的唯一索引挡住重复下单。
"""
import uuid
from datetime import date

from config import PAY_PAID, PAY_UNPAID
from db.connection import read_cursor, write_cursor

_FIELDS = ("recharge_id, order_no, user_id, card_type_id, card_id, amount, "
           "pay_status, pay_time, create_time")

_JOINED = (
    "SELECT r.recharge_id, r.order_no, r.user_id, r.card_type_id, r.card_id, "
    "       r.amount, r.pay_status, r.pay_time, r.create_time, "
    "       ct.card_name, ct.kind, "
    "       u.phone, u.nickname, "
    "       uc.card_no "
    "FROM recharge_order r "
    "JOIN card_type ct ON r.card_type_id = ct.card_type_id "
    "JOIN `user` u ON r.user_id = u.user_id "
    "LEFT JOIN user_card uc ON r.card_id = uc.card_id "
)


def generate_order_no():
    """充值单号：RC + 日期 + 8 位随机。"""
    return "RC" + date.today().strftime("%Y%m%d") + uuid.uuid4().hex[:8].upper()


def get_by_id(recharge_id):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM recharge_order WHERE recharge_id = %s",
                    (recharge_id,))
        return cur.fetchone()


def get_by_id_joined(recharge_id):
    with read_cursor() as cur:
        cur.execute(_JOINED + "WHERE r.recharge_id = %s", (recharge_id,))
        return cur.fetchone()


def get_by_order_no(order_no):
    """按单号查（幂等校验用）。"""
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM recharge_order WHERE order_no = %s", (order_no,))
        return cur.fetchone()


def create(order_no, user_id, card_type_id, amount, cur=None):
    """创建订单（状态默认「待支付」），返回 recharge_id。

    order_no 撞唯一索引会抛 IntegrityError。
    """
    sql = ("INSERT INTO recharge_order (order_no, user_id, card_type_id, amount) "
           "VALUES (%s, %s, %s, %s)")
    args = (order_no, user_id, card_type_id, amount)
    if cur is not None:
        cur.execute(sql, args)
        return cur.lastrowid
    with write_cursor() as c:
        c.execute(sql, args)
        return c.lastrowid


def mark_paid(recharge_id, card_id=None, cur=None):
    """标记为已支付并记下生成的卡。返回 1 = 成功，0 = 这单已不是待支付。

    靠 WHERE pay_status = 0 保证不会重复支付同一单。
    """
    sql = ("UPDATE recharge_order SET pay_status = %s, pay_time = NOW(), card_id = %s "
           "WHERE recharge_id = %s AND pay_status = %s")
    args = (PAY_PAID, card_id, recharge_id, PAY_UNPAID)
    if cur is not None:
        cur.execute(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, args)
        return c.rowcount


def mark_refunded(recharge_id, cur=None):
    """标记为已退款(2)。返回 1 = 成功，0 = 这单不是已支付状态。"""
    sql = ("UPDATE recharge_order SET pay_status = 2 "
           "WHERE recharge_id = %s AND pay_status = %s")
    args = (recharge_id, PAY_PAID)
    if cur is not None:
        cur.execute(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, args)
        return c.rowcount


def delete_unpaid(recharge_id, cur=None):
    """删除一条「待支付」订单。

    规范里 pay_status 只有 0待支付/1已支付/2已退款，没有「已取消」态；
    待支付订单没有产生任何资产，直接删掉才是干净的语义。
    带 pay_status = 0 条件，保证绝不会误删已支付/已退款的流水。
    """
    sql = "DELETE FROM recharge_order WHERE recharge_id = %s AND pay_status = %s"
    args = (recharge_id, PAY_UNPAID)
    if cur is not None:
        cur.execute(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, args)
        return c.rowcount


def list_by_user(user_id, offset=0, limit=20):
    with read_cursor() as cur:
        cur.execute(
            _JOINED + "WHERE r.user_id = %s ORDER BY r.recharge_id DESC LIMIT %s OFFSET %s",
            (user_id, limit, offset),
        )
        return cur.fetchall()


def count_by_user(user_id):
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM recharge_order WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        return row["n"] if row else 0


def list_paged(pay_status=None, offset=0, limit=20):
    """管理端列表。"""
    sql = _JOINED
    params = []
    if pay_status is not None:
        sql += "WHERE r.pay_status = %s "
        params.append(pay_status)
    sql += "ORDER BY r.recharge_id DESC LIMIT %s OFFSET %s"
    params += [limit, offset]
    with read_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def count_paged(pay_status=None):
    with read_cursor() as cur:
        if pay_status is not None:
            cur.execute("SELECT COUNT(*) AS n FROM recharge_order WHERE pay_status = %s",
                        (pay_status,))
        else:
            cur.execute("SELECT COUNT(*) AS n FROM recharge_order")
        row = cur.fetchone()
        return row["n"] if row else 0


def sum_amount(start_date=None, end_date=None):
    """已支付订单的金额合计（营收）。"""
    with read_cursor() as cur:
        if start_date and end_date:
            cur.execute(
                "SELECT IFNULL(SUM(amount), 0) AS total FROM recharge_order "
                "WHERE pay_status = %s AND DATE(pay_time) BETWEEN %s AND %s",
                (PAY_PAID, start_date, end_date),
            )
        else:
            cur.execute("SELECT IFNULL(SUM(amount), 0) AS total FROM recharge_order "
                        "WHERE pay_status = %s", (PAY_PAID,))
        row = cur.fetchone()
        return row["total"] if row else 0


def sum_refunded(start_date=None, end_date=None):
    """已退款订单的金额合计（看板「退款金额」用）。"""
    with read_cursor() as cur:
        if start_date and end_date:
            cur.execute(
                "SELECT IFNULL(SUM(amount), 0) AS total FROM recharge_order "
                "WHERE pay_status = 2 AND DATE(pay_time) BETWEEN %s AND %s",
                (start_date, end_date),
            )
        else:
            cur.execute("SELECT IFNULL(SUM(amount), 0) AS total FROM recharge_order "
                        "WHERE pay_status = 2")
        row = cur.fetchone()
        return row["total"] if row else 0


def revenue_by_day(start_date, end_date):
    """按天汇总的营收，给数据看板画折线图用。"""
    with read_cursor() as cur:
        cur.execute(
            "SELECT DATE(pay_time) AS day, COUNT(*) AS orders, SUM(amount) AS amount "
            "FROM recharge_order WHERE pay_status = %s AND DATE(pay_time) BETWEEN %s AND %s "
            "GROUP BY DATE(pay_time) ORDER BY day",
            (PAY_PAID, start_date, end_date),
        )
        return cur.fetchall()


def count_by_card_type():
    """各卡种卖了多少张，给看板画饼图用。"""
    with read_cursor() as cur:
        cur.execute(
            "SELECT ct.card_name, ct.kind, COUNT(*) AS n, SUM(r.amount) AS amount "
            "FROM recharge_order r JOIN card_type ct ON r.card_type_id = ct.card_type_id "
            "WHERE r.pay_status = %s GROUP BY ct.card_type_id, ct.card_name, ct.kind "
            "ORDER BY n DESC",
            (PAY_PAID,),
        )
        return cur.fetchall()
