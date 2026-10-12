"""管理员表（admin）数据访问。

规范要点：密码列叫 password_hash（不是 password）；时间列叫 create_time；
角色列 role_type(1普通运营员 2超级管理员)；status 是 TINYINT(1正常 0禁用)。

store_id 为 NULL 表示超级管理员（可管理所有门店），非 NULL 表示只负责那一个门店。
"""
from db.connection import read_cursor, write_cursor

_FIELDS = ("admin_id, username, password_hash, real_name, phone, store_id, "
           "role_type, create_time, status")
_SAFE_FIELDS = ("admin_id, username, real_name, phone, store_id, role_type, "
                "create_time, status")


def get_by_id(admin_id):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_SAFE_FIELDS} FROM admin WHERE admin_id = %s", (admin_id,))
        return cur.fetchone()


def get_by_id_with_hash(admin_id):
    """含密码哈希的单条查询（改密码校验旧密码用）。"""
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM admin WHERE admin_id = %s", (admin_id,))
        return cur.fetchone()


def get_by_username(username):
    """管理员登录用（含密码哈希字段）。"""
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM admin WHERE username = %s", (username,))
        return cur.fetchone()


def exists_username(username):
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM admin WHERE username = %s", (username,))
        row = cur.fetchone()
        return bool(row and row["n"] > 0)


def create(username, password_hash, real_name, phone=None, store_id=None, role_type=1):
    """新增管理员，返回 admin_id。store_id 传 None 就是超级管理员。"""
    with write_cursor() as cur:
        cur.execute(
            "INSERT INTO admin (username, password_hash, real_name, phone, store_id, role_type) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (username, password_hash, real_name, phone, store_id, role_type),
        )
        return cur.lastrowid


def list_paged(offset=0, limit=20):
    with read_cursor() as cur:
        cur.execute(
            "SELECT a.admin_id, a.username, a.real_name, a.phone, a.store_id, "
            "       a.role_type, a.create_time, a.status, s.store_name "
            "FROM admin a LEFT JOIN store s ON a.store_id = s.store_id "
            "ORDER BY a.admin_id LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return cur.fetchall()


def count():
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM admin")
        row = cur.fetchone()
        return row["n"] if row else 0


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


def update_password(admin_id, password_hash):
    """改密码（传入的必须是哈希值）。"""
    with write_cursor() as cur:
        cur.execute("UPDATE admin SET password_hash = %s WHERE admin_id = %s",
                    (password_hash, admin_id))
        return cur.rowcount


def update_status(admin_id, status):
    """1 正常 / 0 禁用。"""
    with write_cursor() as cur:
        cur.execute("UPDATE admin SET status = %s WHERE admin_id = %s", (status, admin_id))
        return cur.rowcount
