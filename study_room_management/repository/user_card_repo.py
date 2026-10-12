"""用户持有的卡（user_card）数据访问。余额、次数、时长账户都在这里。

这个文件是整个系统"钱"的出口：充值让它加，预约让它减，退款让它回。
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

    ⚠️ 必须传事务内的游标（不能用 read_cursor），用法在 services 层：

        with uow() as cur:
            card = user_card_repo.get_for_update(cur, card_id)
    """
    cur.execute(f"SELECT {_FIELDS} FROM user_card WHERE card_id = %s FOR UPDATE", (card_id,))
    return cur.fetchone()


def create(card_no, user_id, card_type_id, balance=0, remaining_times=None,
           remaining_hours=None, expire_at=None):
    """开一张卡，返回 card_id。"""
    with write_cursor() as cur:
        cur.execute(
            "INSERT INTO user_card (card_no, user_id, card_type_id, balance, "
            "remaining_times, remaining_hours, expire_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (card_no, user_id, card_type_id, balance, remaining_times,
             remaining_hours, expire_at),
        )
        return cur.lastrowid


def add_balance(card_id, amount):
    """加余额（充值到账 / 退款）。返回影响行数。"""
    with write_cursor() as cur:
        cur.execute("UPDATE user_card SET balance = balance + %s WHERE card_id = %s",
                    (amount, card_id))
        return cur.rowcount


def deduct_balance(card_id, amount):
    """扣余额。返回 1 = 成功，0 = 余额不足。

    防超扣靠 SQL 里的 balance >= %s 条件，而不是"先查再改"——
    后者在并发下会算错。单条 UPDATE 本身就是原子的。
    """
    with write_cursor() as cur:
        cur.execute(
            "UPDATE user_card SET balance = balance - %s WHERE card_id = %s AND balance >= %s",
            (amount, card_id, amount),
        )
        return cur.rowcount


def deduct_times(card_id, times=1):
    """扣次数（次卡用）。返回 1 = 成功，0 = 次数不够。"""
    with write_cursor() as cur:
        cur.execute(
            "UPDATE user_card SET remaining_times = remaining_times - %s "
            "WHERE card_id = %s AND remaining_times >= %s",
            (times, card_id, times),
        )
        return cur.rowcount


def deduct_hours(card_id, hours):
    """扣时长（时长卡用）。返回 1 = 成功，0 = 时长不够。"""
    with write_cursor() as cur:
        cur.execute(
            "UPDATE user_card SET remaining_hours = remaining_hours - %s "
            "WHERE card_id = %s AND remaining_hours >= %s",
            (hours, card_id, hours),
        )
        return cur.rowcount


def update_status(card_id, status):
    """正常 / 冻结 / 已过期 / 已用完。"""
    with write_cursor() as cur:
        cur.execute("UPDATE user_card SET status = %s WHERE card_id = %s", (status, card_id))
        return cur.rowcount


def count_by_user(user_id):
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM user_card WHERE user_id = %s", (user_id,))
        return cur.fetchone()["n"]
