"""卡种表（card_type）数据访问。

注意：下架不等于删除，已售出的卡还要能查到卡种，所以本表不做物理删除。
"""
from db.connection import read_cursor, write_cursor

_FIELDS = ("card_type_id, name, kind, price, face_value, total_times, "
           "total_hours, valid_days, discount, status")
_UPDATABLE = ("name", "kind", "price", "face_value", "total_times",
              "total_hours", "valid_days", "discount")


def get_by_id(card_type_id):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM card_type WHERE card_type_id = %s", (card_type_id,))
        return cur.fetchone()


def list_online():
    """用户端只能看到上架的卡种。"""
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM card_type WHERE status = '上架' "
                    "ORDER BY price")
        return cur.fetchall()


def list_paged(offset=0, limit=20):
    """管理端列表（含已下架）。"""
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM card_type ORDER BY card_type_id LIMIT %s OFFSET %s",
                    (limit, offset))
        return cur.fetchall()


def count():
    with read_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM card_type")
        row = cur.fetchone()
        return row["n"] if row else 0


def create(name, kind, price, face_value=None, total_times=None,
           total_hours=None, valid_days=365, discount=1.00):
    """新增卡种，返回 card_type_id。

    kind 取 '储值' / '次卡' / '时长卡'；discount 是折扣率（1.00 表示不打折）。
    """
    with write_cursor() as cur:
        cur.execute(
            "INSERT INTO card_type (name, kind, price, face_value, total_times, "
            "total_hours, valid_days, discount) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (name, kind, price, face_value, total_times, total_hours, valid_days, discount),
        )
        return cur.lastrowid


def update(card_type_id, **fields):
    """局部更新，只接受 _UPDATABLE 里的字段。"""
    updates = {k: v for k, v in fields.items() if k in _UPDATABLE}
    if not updates:
        return 0
    sets = ", ".join(f"{k} = %s" for k in updates)
    with write_cursor() as cur:
        cur.execute(f"UPDATE card_type SET {sets} WHERE card_type_id = %s",
                    list(updates.values()) + [card_type_id])
        return cur.rowcount


def update_status(card_type_id, status):
    """上架 / 下架。"""
    with write_cursor() as cur:
        cur.execute("UPDATE card_type SET status = %s WHERE card_type_id = %s",
                    (status, card_type_id))
        return cur.rowcount
