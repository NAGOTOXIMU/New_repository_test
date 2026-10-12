"""用户表（`user`）数据访问。

规范要点：phone 是唯一登录账号；status 是 TINYINT（1 正常 / 0 禁用）；
时间列叫 create_time / update_time。
"""
from config import STATUS_OFF, STATUS_ON
from db.connection import read_cursor, write_cursor


def get_by_phone(phone):
    """按手机号查用户（含密码哈希，登录校验用）。查不到返回 None。"""
    with read_cursor() as cur:
        cur.execute(
            "SELECT user_id, phone, password_hash, nickname, status "
            "FROM `user` WHERE phone = %s",
            (phone,),
        )
        return cur.fetchone()


def get_by_id(user_id):
    """按 ID 查用户（不含密码哈希）。查不到返回 None。"""
    with read_cursor() as cur:
        cur.execute(
            "SELECT user_id, phone, nickname, balance, remaining_hours, "
            "       member_level, expire_time, create_time, status "
            "FROM `user` WHERE user_id = %s",
            (user_id,),
        )
        return cur.fetchone()


def exists_phone(phone):
    """手机号是否已被注册。"""
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM `user` WHERE phone = %s", (phone,))
        row = cur.fetchone()
        return bool(row and row["n"] > 0)


def create(phone, password_hash, nickname):
    """新增用户，返回新的 user_id。"""
    with write_cursor() as cur:
        cur.execute(
            "INSERT INTO `user` (phone, password_hash, nickname) VALUES (%s, %s, %s)",
            (phone, password_hash, nickname),
        )
        return cur.lastrowid


def update_profile(user_id, nickname):
    """改昵称，返回影响行数。"""
    with write_cursor() as cur:
        cur.execute("UPDATE `user` SET nickname = %s WHERE user_id = %s", (nickname, user_id))
        return cur.rowcount


def update_password(user_id, password_hash):
    """改密码（传入的必须是哈希值）。"""
    with write_cursor() as cur:
        cur.execute(
            "UPDATE `user` SET password_hash = %s WHERE user_id = %s",
            (password_hash, user_id),
        )
        return cur.rowcount


def update_status(user_id, status):
    """冻结 / 解冻（status 取 STATUS_ON(1) 或 STATUS_OFF(0)）。"""
    with write_cursor() as cur:
        cur.execute("UPDATE `user` SET status = %s WHERE user_id = %s", (status, user_id))
        return cur.rowcount


def add_balance(user_id, delta, cur=None):
    """汇总余额增减（user.balance 是 user_card 的冗余汇总字段）。"""
    sql = "UPDATE `user` SET balance = balance + %s WHERE user_id = %s"
    args = (delta, user_id)
    if cur is not None:
        cur.execute(sql, args)
        return cur.rowcount
    with write_cursor() as c:
        c.execute(sql, args)
        return c.rowcount


def refresh_summary(cur, user_id):
    """把 user_card 的余额/时长汇总回 user 表的冗余字段。

    必须在事务游标里调用（与开卡/扣费在同一个事务）。
    """
    cur.execute(
        "UPDATE `user` u SET "
        "  u.balance = ("
        "    SELECT IFNULL(SUM(uc.balance), 0.00) FROM user_card uc "
        "    WHERE uc.user_id = u.user_id AND uc.status = 1 "
        "      AND (uc.expire_at IS NULL OR uc.expire_at >= CURDATE())), "
        "  u.remaining_hours = ("
        "    SELECT IFNULL(FLOOR(SUM(uc.remaining_minutes) / 60), 0) FROM user_card uc "
        "    WHERE uc.user_id = u.user_id AND uc.status = 1 "
        "      AND (uc.expire_at IS NULL OR uc.expire_at >= CURDATE())) "
        "WHERE u.user_id = %s",
        (user_id,),
    )
    return cur.rowcount


def list_paged(keyword=None, offset=0, limit=20):
    """管理端分页列表（不含密码哈希）。keyword 可按手机号 / 昵称模糊搜。"""
    with read_cursor() as cur:
        if keyword:
            cur.execute(
                "SELECT user_id, phone, nickname, balance, remaining_hours, "
                "       member_level, expire_time, create_time, status "
                "FROM `user` WHERE phone LIKE %s OR nickname LIKE %s "
                "ORDER BY user_id DESC LIMIT %s OFFSET %s",
                (f"%{keyword}%", f"%{keyword}%", limit, offset),
            )
        else:
            cur.execute(
                "SELECT user_id, phone, nickname, balance, remaining_hours, "
                "       member_level, expire_time, create_time, status "
                "FROM `user` ORDER BY user_id DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )
        return cur.fetchall()


def count(keyword=None):
    """配合 list_paged 算分页总数。"""
    with read_cursor() as cur:
        if keyword:
            cur.execute(
                "SELECT COUNT(*) AS n FROM `user` WHERE phone LIKE %s OR nickname LIKE %s",
                (f"%{keyword}%", f"%{keyword}%"),
            )
        else:
            cur.execute("SELECT COUNT(*) AS n FROM `user`")
        row = cur.fetchone()
        return row["n"] if row else 0


def count_by_status(status=None):
    """按状态统计用户数（看板用）。"""
    with read_cursor() as cur:
        if status is None:
            cur.execute("SELECT COUNT(*) AS n FROM `user`")
        else:
            cur.execute("SELECT COUNT(*) AS n FROM `user` WHERE status = %s", (status,))
        row = cur.fetchone()
        return row["n"] if row else 0


def count_new_by_day(days=30):
    """按天统计新增用户（看会员增长）。"""
    with read_cursor() as cur:
        cur.execute(
            "SELECT DATE(create_time) AS day, COUNT(*) AS n FROM `user` "
            "WHERE create_time >= CURDATE() - INTERVAL %s DAY "
            "GROUP BY DATE(create_time) ORDER BY day",
            (days,),
        )
        return cur.fetchall()
