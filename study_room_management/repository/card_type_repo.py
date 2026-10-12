"""卡种表（card_type）数据访问 —— 「卖什么卡」的字典。

规范要点：主键 card_type_id；卡类型列叫 kind(1时长卡 2次卡 3储值卡)；
value 是「对应价值」（时长卡=分钟数，次卡=次数，储值卡=0）；
status 是 TINYINT（1 上架 / 0 下架）。

注意：下架不等于删除，已售出的卡还要能查到卡种，所以本表不做物理删除。
"""
from db.connection import read_cursor, write_cursor

_FIELDS = ("card_type_id, card_name, kind, price, value, valid_days, status, create_time")
_UPDATABLE = ("card_name", "kind", "price", "value", "valid_days")


def get_by_id(card_type_id):
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM card_type WHERE card_type_id = %s",
                    (card_type_id,))
        return cur.fetchone()


def list_online():
    """用户端只能看到上架的卡种。"""
    with read_cursor() as cur:
        cur.execute(f"SELECT {_FIELDS} FROM card_type WHERE status = 1 ORDER BY price")
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


def create(card_name, kind, price, value=0, valid_days=365):
    """新增卡种，返回 card_type_id。

    kind 取 1(时长卡) / 2(次卡) / 3(储值卡)。
    时长卡的 value 传分钟数，次卡传次数，储值卡传 0。
    card_name 撞唯一索引会抛 IntegrityError。
    """
    with write_cursor() as cur:
        cur.execute(
            "INSERT INTO card_type (card_name, kind, price, value, valid_days) "
            "VALUES (%s, %s, %s, %s, %s)",
            (card_name, kind, price, value, valid_days),
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
    """上架(1) / 下架(0)。"""
    with write_cursor() as cur:
        cur.execute("UPDATE card_type SET status = %s WHERE card_type_id = %s",
                    (status, card_type_id))
        return cur.rowcount
