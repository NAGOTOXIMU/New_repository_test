"""用户表（`user`）数据访问。"""
from db.connection import read_cursor, write_cursor


def get_by_username(username):
    """按用户名查用户（含密码字段，登录校验用）。查不到返回 None。"""
    with read_cursor() as cur:
        cur.execute(
            "SELECT user_id, username, password, real_name, phone, email, status "
            "FROM `user` WHERE username = %s",
            (username,),
        )
        return cur.fetchone()


def get_by_id(user_id):
    """按 ID 查用户（不含密码）。查不到返回 None。"""
    with read_cursor() as cur:
        cur.execute(
            "SELECT user_id, username, real_name, phone, email, status "
            "FROM `user` WHERE user_id = %s",
            (user_id,),
        )
        return cur.fetchone()


def exists_username(username):
    """用户名是否已被注册。"""
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM `user` WHERE username = %s", (username,))
        row = cur.fetchone()
        return bool(row and row["n"] > 0)


def exists_phone(phone):
    """手机号是否已被占用。"""
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM `user` WHERE phone = %s", (phone,))
        row = cur.fetchone()
        return bool(row and row["n"] > 0)


def create(username, password_hash, real_name, phone, email=None):
    """新增用户，返回新的 user_id。"""
    with write_cursor() as cur:
        cur.execute(
            "INSERT INTO `user` (username, password, real_name, phone, email) "
            "VALUES (%s, %s, %s, %s, %s)",
            (username, password_hash, real_name, phone, email),
        )
        return cur.lastrowid


def update_profile(user_id, real_name, phone, email=None):
    """改姓名 / 手机号 / 邮箱，返回影响行数。"""
    with write_cursor() as cur:
        cur.execute(
            "UPDATE `user` SET real_name = %s, phone = %s, email = %s WHERE user_id = %s",
            (real_name, phone, email, user_id),
        )
        return cur.rowcount


def update_password(user_id, password_hash):
    """改密码（传入的必须是哈希值）。"""
    with write_cursor() as cur:
        cur.execute(
            "UPDATE `user` SET password = %s WHERE user_id = %s",
            (password_hash, user_id),
        )
        return cur.rowcount


def update_status(user_id, status):
    """冻结 / 解冻（status 取 '正常' 或 '冻结'）。"""
    with write_cursor() as cur:
        cur.execute("UPDATE `user` SET status = %s WHERE user_id = %s", (status, user_id))
        return cur.rowcount


def list_paged(keyword=None, offset=0, limit=20):
    """管理端分页列表（不含密码）。keyword 可按用户名 / 手机号 / 姓名模糊搜。"""
    with read_cursor() as cur:
        if keyword:
            cur.execute(
                "SELECT user_id, username, real_name, phone, email, status, created_at "
                "FROM `user` WHERE username LIKE %s OR phone LIKE %s OR real_name LIKE %s "
                "ORDER BY user_id DESC LIMIT %s OFFSET %s",
                (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit, offset),
            )
        else:
            cur.execute(
                "SELECT user_id, username, real_name, phone, email, status, created_at "
                "FROM `user` ORDER BY user_id DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )
        return cur.fetchall()


def count(keyword=None):
    """配合 list_paged 算分页总数。"""
    with read_cursor() as cur:
        if keyword:
            cur.execute(
                "SELECT COUNT(*) AS n FROM `user` "
                "WHERE username LIKE %s OR phone LIKE %s OR real_name LIKE %s",
                (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"),
            )
        else:
            cur.execute("SELECT COUNT(*) AS n FROM `user`")
        row = cur.fetchone()
        return row["n"] if row else 0


def count_new_by_day(days=30):
    """按天统计新增用户（看会员增长）。"""
    with read_cursor() as cur:
        cur.execute(
            "SELECT DATE(created_at) AS day, COUNT(*) AS n FROM `user` "
            "WHERE created_at >= CURDATE() - INTERVAL %s DAY "
            "GROUP BY DATE(created_at) ORDER BY day",
            (days,),
        )
        return cur.fetchall()
