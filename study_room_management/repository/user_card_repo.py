"""用户持卡实例表（user_card）数据访问 —— 账户：余额 / 次数 / 时长都在这里。

这是《数据库规范》的缺口补充表：card_type 是「卖什么卡」的字典，
user_card 是「用户实际持有的那张卡」，资产必须挂在卡上才能按卡归属、按卡扣减。

写函数都支持传事务游标：cur=... 时在事务里执行，不传就自己开连接。
"""
import uuid
from datetime import date

from db.connection import read_cursor, write_cursor

_FIELDS = ("card_id, card_no, user_id, card_type_id, balance, remaining_times, "
           "remaining_minutes, expire_at, status, create_time")

# 列表页要同时看到卡种名称，统一用这段 join
_JOINED = (
    "SELECT uc.card_id, uc.card_no, uc.user_id, uc.card_type_id, uc.balance, "
    "       uc.remaining_times, uc.remaining_minutes, uc.expire_at, uc.status, "
    "       uc.create_time, ct.card_name, ct.kind, ct.price "
    "FROM user_card uc JOIN card_type ct ON uc.card_type_id = ct.card_type_id "
)


def generate_card_no():
    """生成卡号：C + 日期 + 8 位随机。"""
    return "C" + date.today().strftime("%Y%m%d") + uuid.uuid4().hex[:8].upper()


def get_by_id(card_id):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM user_card WHERE card_id = %s", (card_id,))
        return cur.fetchone()


def get_by_id_joined(card_id):
    """带卡种名称/类型的单卡查询（界面展示用）。"""
    with read_cursor() as cur:
        cur.execute(_JOINED + "WHERE uc.card_id = %s", (card_id,))
        return cur.fetchone()


def get_by_no(card_no):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM user_card WHERE card_no = %s", (card_no,))
        return cur.fetchone()


def list_by_user(user_id):
    """某人持有的所有卡（含已过期的）。"""
    with read_cursor() as cur:
        cur.execute(_JOINED + "WHERE uc.user_id = %s ORDER BY uc.card_id DESC", (user_id,))
        return cur.fetchall()


def list_active_by_user(user_id):
    """某人当前可用的卡（状态正常且未过期）。"""
    with read_cursor() as cur:
        cur.execute(
            _JOINED + "WHERE uc.user_id = %s AND uc.status = 1 "
            "AND (uc.expire_at IS NULL OR uc.expire_at >= CURDATE()) "
            "ORDER BY uc.card_id",
            (user_id,),
        )
        return cur.fetchall()


def find_active_by_type(user_id, card_type_id, cur=None):
    """找某人某个卡种下第一张可用的卡（充值到账时决定「累加还是新开」）。"""
    sql = (_JOINED + "WHERE uc.user_id = %s AND uc.card_type_id = %s AND uc.status = 1 "
           "AND (uc.expire_at IS NULL OR uc.expire_at >= CURDATE()) "
           "ORDER BY uc.card_id LIMIT 1")
    args = (user_id, card_type_id)
    if cur is not None:
        cur.execute(sql, args)
        return cur.fetchone()
    with read_cursor() as c:
        c.execute(sql, args)
        return c.fetchone()


def count_by_user(user_id):
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM user_card WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        return row["n"] if row else 0


def get_for_update(cur, card_id):
    """在事务里锁定一张卡，防止并发扣到同一张卡上。

    ⚠️ 它只接受事务游标（必须由 uow() 提供），用法：

        with uow() as cur:
            card = user_card_repo.get_for_update(cur, card_id)
    """
    cur.execute(f"SELECT {_FIELDS} FROM user_card WHERE card_id = %s FOR UPDATE", (card_id,))
    return cur.fetchone()


def create(card_no, user_id, card_type_id, balance=0.00, remaining_times=0,
           remaining_minutes=0, expire_at=None, cur=None):
    """开一张卡，返回 card_id。"""
    sql = ("INSERT INTO user_card (card_no, user_id, card_type_id, balance, "
           "remaining_times, remaining_minutes, expire_at) VALUES (%s, %s, %s, %s, %s, %s, %s)")
    args = (card_no, user_id, card_type_id, balance, remaining_times,
            remaining_minutes, expire_at)
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


def upsert_by_type(user_id, card_type_id, kind, balance_delta, times_delta,
                   minutes_delta, expire_at, cur):
    """充值到账：同一卡种已有可用卡就累加，没有就新开一张。

    必须传事务游标 cur —— 它和「订单标记已支付」必须在同一个事务里，
    否则会出现「钱付了卡没到」。
    返回 (card_id, card_no, created)。
    """
    existing = find_active_by_type(user_id, card_type_id, cur=cur)
    if existing:
        card_id = existing["card_id"]
        if balance_delta:
            add_balance(card_id, balance_delta, cur=cur)
        if times_delta:
            add_times(card_id, times_delta, cur=cur)
        if minutes_delta:
            add_minutes(card_id, minutes_delta, cur=cur)
        return card_id, existing["card_no"], False

    card_no = generate_card_no()
    card_id = create(
        card_no, user_id, card_type_id,
        balance=balance_delta or 0.00,
        remaining_times=times_delta or 0,
        remaining_minutes=minutes_delta or 0,
        expire_at=expire_at, cur=cur,
    )
    return card_id, card_no, True


def deduct_balance(card_id, amount, cur=None):
    """扣余额。返回 1 = 成功，0 = 余额不足。

    防超扣靠 SQL 里的 balance >= %s，而不是「先查再改」——后者在并发下会算错。
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


def add_minutes(card_id, minutes, cur=None):
    """加时长（分钟）。退款 / 充值到账用。"""
    sql = ("UPDATE user_card SET remaining_minutes = remaining_minutes + %s "
           "WHERE card_id = %s")
    args = (minutes, card_id)
    if cur is not None:
        cur.execute(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, args)
        return c.rowcount


def deduct_minutes(card_id, minutes, cur=None):
    """扣时长（时长卡用，单位分钟）。返回 1 = 成功，0 = 时长不够。"""
    sql = ("UPDATE user_card SET remaining_minutes = remaining_minutes - %s "
           "WHERE card_id = %s AND remaining_minutes >= %s")
    args = (minutes, card_id, minutes)
    if cur is not None:
        cur.execute(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, args)
        return c.rowcount


def update_status(card_id, status):
    """1 正常 / 0 已冻结。"""
    with write_cursor() as cur:
        cur.execute("UPDATE user_card SET status = %s WHERE card_id = %s", (status, card_id))
        return cur.rowcount
