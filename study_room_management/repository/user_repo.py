"""用户表（`user`）的数据访问。所有 SQL 只在本文件里。"""
from db.connection import get_conn


def get_by_username(username):
    """按用户名查用户。查到返回 dict，查不到返回 None。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, username, password, real_name, phone, email, status "
                "FROM `user` WHERE username = %s",
                (username,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def get_by_id(user_id):
    """按 ID 查用户（不带密码字段）。查到返回 dict，查不到返回 None。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, username, real_name, phone, email, status "
                "FROM `user` WHERE user_id = %s",
                (user_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def exists_username(username):
    """用户名是否已被注册。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM `user` WHERE username = %s", (username,))
            return cur.fetchone()["n"] > 0
    finally:
        conn.close()


def exists_phone(phone):
    """手机号是否已被占用。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM `user` WHERE phone = %s", (phone,))
            return cur.fetchone()["n"] > 0
    finally:
        conn.close()


def create(username, password_hash, real_name, phone, email):
    """插入一个新用户，返回新的 user_id。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO `user` (username, password, real_name, phone, email) "
                "VALUES (%s, %s, %s, %s, %s)",
                (username, password_hash, real_name, phone, email),
            )
            new_id = cur.lastrowid
        conn.commit()
        return new_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
