"""用户持有的卡（user_card）数据访问。余额、次数、时长账户都在这里。

写函数都支持传事务游标：cur=... 时在事务里执行，不传就自己开连接。
"""
import uuid
from datetime import date

from db.connection import read_cursor, write_cursor

_FIELDS = ("card_id, card_no, user_id, card_type_id, balance, remaining_times, "
           "remaining_hours, expire_at, status")


def generate_card_no():
    """生成卡号：C + 日期 + 8 位随机。"""
    return "C" + date.today().strftime("%Y%m%d") + uuid.uuid4().hex[:8].upper()


def get_by_id(card_id):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM user_card WHERE card_id = %s", (card_id,))
        return cur.fetchone()


def get_by_no(card_no):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM user_card WHERE card_no = %s", (card_no,))
        return cur.fetchone()


def list_by_user(user_id):
    """某人持有的所有卡（含已过期的）。"""
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM user_card WHERE user_id = %s "
                    "ORDER BY card_id DESC", (user_id,))
        return cur.fetchall()


def list_active_by_user(user_id):
    """某人当前可用的卡（状态正常且未过期）。"""
    with read_cursor() as cur:
        cur.execute(
            f"SELECT {_FIELDS} FROM user_card "
            "WHERE user_id = %s AND status = '正常' "
            "AND (expire_at IS NULL OR expire_at >= CURDATE()) ORDER BY card_id",
            (user_id,),
        )
        return cur.fetchall()


def get_for_update(cur, card_id):
    """在事务里锁定一张卡，防止并发扣到同一张卡上。

    ⚠️ 它只接受事务游标（必须由 uow() 提供），用法：

        with uow() as cur:
            card = user_card_repo.get_for_update(cur, card_id)
    """
    cur.execute(f"SELECT {_FIELDS} FROM user_card WHERE card_id = %s FOR UPDATE", (card_id,))
    return cur.fetchone()


def create(card_no, user_id, card_type_id, balance=0, remaining_times=None,
           remaining_hours=None, expire_at=None, cur=None):
    """开一张卡，返回 card_id。"""
    sql = ("INSERT INTO user_card (card_no, user_id, card_type_id, balance, "
           "remaining_times, remaining_hours, expire_at) VALUES (%s, %s, %s, %s, %s, %s, %s)")
    args = (card_no, user_id, card_type_id, balance, remaining_times, remaining_hours, expire_at)
    if cur is not None:
        cur.execute(sql, args)
        return cur.lastrowid
    with write_cursor() as c:
        c.execute(sql, args)
        return c.lastrowid


def add_balance(card_id, amount, cur=None):
    """加余额（充值到账 / 退款）。返回影响行数。"""
    sql = "UPDATE user_card SET balance = balance + %s WHERE card_id = %s"
    args = (amount, card_id)
    if cur is not None:
        cur.execute(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, args)
        return c.rowcount


def deduct_balance(card_id, amount, cur=None):
    """扣余额。返回 1 = 成功，0 = 余额不足。

    防超扣靠 SQL 里的 balance >= %s，而不是"先查再改"——后者在并发下会算错。
    """
    sql = ("UPDATE user_card SET balance = balance - %s "
           "WHERE card_id = %s AND balance >= %s")
    args = (amount, card_id, amount)
    if cur is not None:
        cur.execute(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, args)
        return c.rowcount


def add_times(card_id, times=1, cur=None):
    """加次数（退款 / 充值到账）。"""
    sql = "UPDATE user_card SET remaining_times = remaining_times + %s WHERE card_id = %s"
    args = (times, card_id)
    if cur is not None:
        cur.execute(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, args)
        return c.rowcount


def add_hours(card_id, hours, cur=None):
    """加时长（退款 / 充值到账）。"""
    sql = "UPDATE user_card SET remaining_hours = remaining_hours + %s WHERE card_id = %s"
    args = (hours, card_id)
    if cur is not None:
        cur.execute(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, args)
        return c.rowcount


def deduct_times(card_id, times=1, cur=None):
    """扣次数（次卡用）。返回 1 = 成功，0 = 次数不够。"""
    sql = ("UPDATE user_card SET remaining_times = remaining_times - %s "
           "WHERE card_id = %s AND remaining_times >= %s")
    args = (times, card_id, times)
    if cur is not None:
        cur.execute(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, args)
        return c.rowcount


def deduct_hours(card_id, hours, cur=None):
    """扣时长（时长卡用）。返回 1 = 成功，0 = 时长不够。"""
    sql = ("UPDATE user_card SET remaining_hours = remaining_hours - %s "
           "WHERE card_id = %s AND remaining_hours >= %s")
    args = (hours, card_id, hours)
    if cur is not None:
        cur.execute(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, args)
        return c.rowcount


def update_status(card_id, status):
    """正常 / 冻结 / 已过期 / 已用完。"""
    with write_cursor() as cur:
        cur.execute("UPDATE user_card SET status = %s WHERE card_id = %s", (status, card_id))
        return cur.rowcount


def count_by_user(user_id):
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM user_card WHERE user_id = %s", (user_id,))
        return cur.fetchone()["n"]
