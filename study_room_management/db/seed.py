"""灌测试数据（用项目自己的密码哈希算法，保证能登录）。

用法（在项目根目录 study_room_management 下执行）：

    python -m db.seed              # 灌基础测试数据（门店/座位/卡种/用户/管理员）
    python -m db.seed --with-orders  # 再补历史充值单与预约单，供数据看板演示

为什么用它而不是直接执行 03_seed.sql：
    03_seed.sql 里的密码哈希是固定的字符串；本脚本用 services/password.py
    现算哈希，密码永远和 config 里写的一致，不会因为换了盐而登不进去。

可重复执行：全部走 INSERT ... ON DUPLICATE KEY UPDATE。
"""
import sys
from datetime import date, timedelta

from config import KIND_HOURS, KIND_STORED, KIND_TIMES
from db.connection import get_conn
from services.password import hash_password

USER_PASSWORD = "123456"
ADMIN_PASSWORD = "admin123"

STORES = [
    # store_id, store_name, address, open_time, close_time
    (1, "旗舰店·市中心馆", "杭州市西湖区文三路 100 号 3 层", "08:00:00", "22:00:00"),
    (2, "滨江分馆", "杭州市滨江区江南大道 500 号 2 层", "09:00:00", "21:00:00"),
]

SEATS = [
    # seat_id, store_id, seat_code, area_type, has_socket, status
    (1, 1, "A01", 1, 1, 1), (2, 1, "A02", 1, 1, 1), (3, 1, "A03", 1, 0, 1),
    (4, 1, "B01", 2, 1, 1), (5, 1, "B02", 2, 1, 1), (6, 1, "C01", 3, 1, 0),
    (7, 2, "A01", 1, 1, 1), (8, 2, "A02", 1, 0, 1),
    (9, 2, "B01", 2, 1, 1), (10, 2, "C01", 3, 1, 1),
]

CARD_TYPES = [
    # card_type_id, card_name, kind, price, value, valid_days, status
    # 时长卡/次卡的 value 是分钟数/次数；
    # 储值卡的 value 约定为「这张卡包含的小时数」，单价 = price ÷ value
    (1, "10 小时时长卡", KIND_HOURS, 49.00, 600, 180, 1),
    (2, "30 小时时长卡", KIND_HOURS, 129.00, 1800, 365, 1),
    (3, "20 次卡", KIND_TIMES, 99.00, 20, 180, 1),
    (4, "100 元储值卡", KIND_STORED, 100.00, 20, 365, 1),
]

USERS = [
    # user_id, phone, nickname, member_level, expire_days
    (1, "13800000001", "小林", 1, 365),
    (2, "13800000002", "小张", 0, None),
]

ADMINS = [
    # admin_id, username, real_name, phone, store_id, role_type
    (1, "admin", "系统管理员", "13900000000", None, 2),
    (2, "ops1", "王运营", "13900000001", 1, 1),
]

USER_CARDS = [
    # card_id, card_no, user_id, card_type_id, balance, remaining_times, remaining_minutes
    (1, "C20261012AAAA0001", 1, 1, 0.00, 0, 600),
    (2, "C20261012AAAA0002", 1, 3, 0.00, 20, 0),
    (3, "C20261012AAAA0003", 2, 4, 100.00, 0, 0),
]


def _seed_base(cur):
    for sid, name, addr, open_t, close_t in STORES:
        cur.execute(
            "INSERT INTO store (store_id, store_name, address, open_time, close_time, "
            "seat_count, status) VALUES (%s,%s,%s,%s,%s,0,1) "
            "ON DUPLICATE KEY UPDATE store_name=VALUES(store_name), address=VALUES(address), "
            "open_time=VALUES(open_time), close_time=VALUES(close_time), "
            # status 也要一起置回营业：否则之前被人手工停业（或被冒烟测试改成 status=0）
            # 的门店，重新灌 seed 也还是停业，用户端首页会整个看不到这家门店和它的座位。
            # 与 db/sql/03_seed.sql 的口径保持一致。
            "status=VALUES(status)",
            (sid, name, addr, open_t, close_t),
        )

    for row in SEATS:
        cur.execute(
            "INSERT INTO seat (seat_id, store_id, seat_code, area_type, has_socket, status) "
            "VALUES (%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE store_id=VALUES(store_id), seat_code=VALUES(seat_code), "
            "area_type=VALUES(area_type), has_socket=VALUES(has_socket), status=VALUES(status)",
            row,
        )

    for ctid, name, kind, price, value, days, status in CARD_TYPES:
        cur.execute(
            "INSERT INTO card_type (card_type_id, card_name, kind, price, value, "
            "valid_days, status) VALUES (%s,%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE card_name=VALUES(card_name), kind=VALUES(kind), "
            "price=VALUES(price), value=VALUES(value), valid_days=VALUES(valid_days), "
            "status=VALUES(status)",
            (ctid, name, kind, price, value, days, status),
        )

    pw_user = hash_password(USER_PASSWORD)
    for uid, phone, nickname, level, expire_days in USERS:
        expire = (date.today() + timedelta(days=expire_days)).strftime("%Y-%m-%d 23:59:59") \
            if expire_days else None
        cur.execute(
            "INSERT INTO `user` (user_id, phone, password_hash, nickname, member_level, "
            "expire_time, status) VALUES (%s,%s,%s,%s,%s,%s,1) "
            "ON DUPLICATE KEY UPDATE phone=VALUES(phone), password_hash=VALUES(password_hash), "
            "nickname=VALUES(nickname), member_level=VALUES(member_level), "
            "expire_time=VALUES(expire_time), status=1",
            (uid, phone, pw_user, nickname, level, expire),
        )

    pw_admin = hash_password(ADMIN_PASSWORD)
    for aid, username, real_name, phone, store_id, role_type in ADMINS:
        cur.execute(
            "INSERT INTO admin (admin_id, username, password_hash, real_name, phone, "
            "store_id, role_type, status) VALUES (%s,%s,%s,%s,%s,%s,%s,1) "
            "ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash), "
            "real_name=VALUES(real_name), phone=VALUES(phone), store_id=VALUES(store_id), "
            "role_type=VALUES(role_type), status=1",
            (aid, username, pw_admin, real_name, phone, store_id, role_type),
        )

    for cid, card_no, uid, ctid, balance, times, minutes in USER_CARDS:
        cur.execute(
            "INSERT INTO user_card (card_id, card_no, user_id, card_type_id, balance, "
            "remaining_times, remaining_minutes, expire_at, status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1) "
            "ON DUPLICATE KEY UPDATE card_no=VALUES(card_no), user_id=VALUES(user_id), "
            "card_type_id=VALUES(card_type_id), balance=VALUES(balance), "
            "remaining_times=VALUES(remaining_times), "
            "remaining_minutes=VALUES(remaining_minutes), expire_at=VALUES(expire_at), status=1",
            (cid, card_no, uid, ctid, balance, times, minutes,
             (date.today() + timedelta(days=180)).strftime("%Y-%m-%d")),
        )

    # 汇总冗余字段 + 门店座位数，全部按真实数据重算一遍
    cur.execute(
        "UPDATE `user` u SET "
        "  u.balance = (SELECT IFNULL(SUM(uc.balance),0.00) FROM user_card uc "
        "               WHERE uc.user_id=u.user_id AND uc.status=1 "
        "                 AND (uc.expire_at IS NULL OR uc.expire_at>=CURDATE())), "
        "  u.remaining_hours = (SELECT IFNULL(FLOOR(SUM(uc.remaining_minutes)/60),0) "
        "               FROM user_card uc WHERE uc.user_id=u.user_id AND uc.status=1 "
        "                 AND (uc.expire_at IS NULL OR uc.expire_at>=CURDATE()))"
    )
    cur.execute("UPDATE store s SET s.seat_count = "
                "(SELECT COUNT(*) FROM seat WHERE seat.store_id = s.store_id)")


def _seed_orders(cur):
    # 全部用固定主键，ON DUPLICATE KEY UPDATE 才能真正命中同一行，
    # 否则每次执行都会因为自增 ID 不同而插出新行，表会越长越大。
    orders = [
        # recharge_id, order_no, uid, card_type_id, card_id, amount, pay_status
        (1, "RC20261001SEED0001", 1, 1, 1, 49.00, 1),
        (2, "RC20261002SEED0002", 1, 3, 2, 99.00, 1),
        (3, "RC20261003SEED0003", 2, 4, 3, 100.00, 1),
    ]
    for rid, order_no, uid, ctid, card_id, amount, pay_status in orders:
        cur.execute(
            "INSERT INTO recharge_order (recharge_id, order_no, user_id, card_type_id, "
            "card_id, amount, pay_status, pay_time) VALUES (%s,%s,%s,%s,%s,%s,%s,NOW()) "
            "ON DUPLICATE KEY UPDATE order_no=VALUES(order_no), user_id=VALUES(user_id), "
            "card_type_id=VALUES(card_type_id), card_id=VALUES(card_id), "
            "amount=VALUES(amount), pay_status=VALUES(pay_status)",
            (rid, order_no, uid, ctid, card_id, amount, pay_status),
        )

    today = date.today()
    reservations = [
        # order_id, order_no, uid, seat_id, store_id, card_id, 距今天数(负=未来),
        # start, end, 分钟, 金额, 状态, active
        (1, "RSEED0001", 1, 1, 1, 1, 7, "09:00:00", "12:00:00", 180, 0.00, 3, 1),
        (2, "RSEED0002", 2, 7, 2, 3, 6, "14:00:00", "16:00:00", 120, 10.00, 3, 1),
        (3, "RSEED0003", 1, 4, 1, 2, 5, "10:00:00", "11:00:00", 60, 0.00, 3, 1),
        (4, "RSEED0004", 2, 8, 2, None, 4, "15:00:00", "17:00:00", 120, 0.00, 4, None),
        (5, "RSEED0005", 1, 2, 1, 1, -1, "13:00:00", "15:00:00", 120, 0.00, 1, 1),
    ]
    for (oid, order_no, uid, seat_id, store_id, card_id, day_offset, start, end,
         minutes, amount, ostatus, active) in reservations:
        cur.execute(
            "INSERT INTO reservation_order (order_id, order_no, user_id, seat_id, store_id, "
            "card_id, reserve_date, start_time, end_time, duration, amount, order_status, "
            "active_flag) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE order_no=VALUES(order_no), user_id=VALUES(user_id), "
            "seat_id=VALUES(seat_id), store_id=VALUES(store_id), card_id=VALUES(card_id), "
            "reserve_date=VALUES(reserve_date), start_time=VALUES(start_time), "
            "end_time=VALUES(end_time), duration=VALUES(duration), amount=VALUES(amount), "
            "order_status=VALUES(order_status), active_flag=VALUES(active_flag)",
            (oid, order_no, uid, seat_id, store_id, card_id,
             today + timedelta(days=day_offset), start, end, minutes, amount, ostatus, active),
        )

    # 清掉旧版脚本（03_seed.sql）留下的、不在上面清单里的种子行，保证可重复执行后数量稳定
    cur.execute(
        "DELETE FROM recharge_order WHERE order_no LIKE 'RC%%SEED%%' "
        "AND order_no NOT IN (%s, %s, %s)",
        ("RC20261001SEED0001", "RC20261002SEED0002", "RC20261003SEED0003"),
    )
    cur.execute(
        "DELETE FROM reservation_order WHERE (order_no LIKE 'R%%SEED%%' "
        "OR order_no LIKE 'R2026%%SEED%%') AND order_no NOT IN (%s, %s, %s, %s, %s)",
        ("RSEED0001", "RSEED0002", "RSEED0003", "RSEED0004", "RSEED0005"),
    )


def main() -> int:
    # Windows 控制台默认 GBK，直接 print 中文/表情会乱码或抛 UnicodeEncodeError
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    with_orders = "--with-orders" in sys.argv[1:]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            _seed_base(cur)
            if with_orders:
                _seed_orders(cur)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT 'store' t, COUNT(*) n FROM store UNION ALL "
                "SELECT 'seat', COUNT(*) FROM seat UNION ALL "
                "SELECT 'card_type', COUNT(*) FROM card_type UNION ALL "
                "SELECT 'user', COUNT(*) FROM `user` UNION ALL "
                "SELECT 'user_card', COUNT(*) FROM user_card UNION ALL "
                "SELECT 'admin', COUNT(*) FROM admin UNION ALL "
                "SELECT 'recharge_order', COUNT(*) FROM recharge_order UNION ALL "
                "SELECT 'reservation_order', COUNT(*) FROM reservation_order"
            )
            counts = cur.fetchall()
    finally:
        conn.close()

    print("测试数据灌入完成：")
    for row in counts:
        print(f"   {row['t']:<18} {row['n']}")
    print(f"\n用户登录：手机号 13800000001 / 13800000002，密码 {USER_PASSWORD}")
    print(f"管理员登录：admin / ops1，密码 {ADMIN_PASSWORD}")
    if not with_orders:
        print("\n提示：加 --with-orders 可以再补历史充值单与预约单，供数据看板演示。")
    return 0

if __name__ == "__main__":
    sys.exit(main())
