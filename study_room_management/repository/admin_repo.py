"""管理员表（admin）数据访问。

注意：store_id 为 NULL 表示超级管理员，非 NULL 表示只负责那一个门店。
"""
from db.connection import read_cursor, write_cursor

_FIELDS = "admin_id, username, password, real_name, phone, store_id, status, created_at"
_SAFE_FIELDS = "admin_id, username, real_name, phone, store_id, status, created_at"


def get_by_id(admin_id):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_SAFE_FIELDS} FROM admin WHERE admin_id = %s", (admin_id,))
        return cur.fetchone()


def get_by_username(username):
    """管理员登录用（含密码哈希字段）。"""
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM admin WHERE username = %s", (username,))
        return cur.fetchone()


def exists_username(username):
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM admin WHERE username = %s", (username,))
        return cur.fetchone()["n"] > 0


def create(username, password_hash, real_name, phone=None, store_id=None):
    """新增管理员，返回 admin_id。store_id 传 None 就是超级管理员。"""
    with write_cursor() as cur:
        cur.execute(
            "INSERT INTO admin (username, password, real_name, phone, store_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (username, password_hash, real_name, phone, store_id),
        )
        return cur.lastrowid


def list_paged(offset=0, limit=20):
    with read_cursor() as cur:
        cur.execute(
            "SELECT a.admin_id, a.username, a.real_name, a.phone, a.store_id, "
            "       a.status, a.created_at, s.name AS store_name "
            "FROM admin a LEFT JOIN store s ON a.store_id = s.store_id "
            "ORDER BY a.admin_id LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return cur.fetchall()


def count():
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM admin")
        return cur.fetchone()["n"]


def update_profile(admin_id, real_name=None, phone=None, store_id=None):
    """改资料。只更新传进来的字段（None 表示不改）。"""
    sets, params = [], []
    if real_name is not None:
        sets.append("real_name = %s")
        params.append(real_name)
    if phone is not None:
        sets.append("phone = %s")
        params.append(phone)
    if store_id is not None:
        sets.append("store_id = %s")
        params.append(store_id)
    if not sets:
        return 0
    with write_cursor() as cur:
        cur.execute(f"UPDATE admin SET {', '.join(sets)} WHERE admin_id = %s",
                    params + [admin_id])
        return cur.rowcount


def update_status(admin_id, status):
    """正常 / 停用。"""
    with write_cursor() as cur:
        cur.execute("UPDATE admin SET status = %s WHERE admin_id = %s", (status, admin_id))
        return cur.rowcount
