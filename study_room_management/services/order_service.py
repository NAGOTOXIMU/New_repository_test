"""预约业务：下单、取消、状态流转。

本文件不写 SQL；涉及钱的操作全部走 db/uow.py 的事务。
"""
from datetime import datetime, timedelta

import pymysql

from db.uow import uow
from repository import card_type_repo, reservation_repo, seat_repo, user_card_repo
from services.exceptions import BizError

MAX_HOURS = 8      # 一次最多连选几小时


def _end_time(start_time, hours):
    """'14:00:00' 加 2 小时 -> '16:00:00'。"""
    t = datetime.strptime(str(start_time), "%H:%M:%S")
    return (t + timedelta(hours=hours)).strftime("%H:%M:%S")


def _pick_card(user_id, card_id=None):
    """选卡：传了 card_id 就用它，没传就自动取第一张可用的。"""
    cards = user_card_repo.list_active_by_user(user_id)
    if not cards:
        raise BizError("你还没有可用的会员卡，请先充值")
    if card_id is None:
        return cards[0]
    for c in cards:
        if c["card_id"] == card_id:
            return c
    raise BizError("这张卡当前不可用（可能已过期或被冻结）")


def _charge(cur, card, hours, price_per_hour):
    """按卡种扣费，返回本次实际扣掉的钱。不够用就抛 BizError。

    规则（见 docs/DESIGN.md 的 A3，可改）：
        次卡   -> 扣 1 次
        时长卡 -> 扣 hours 小时
        储值卡 -> 座位原价 × 小时数 × 卡的折扣率
    """
    ct = card_type_repo.get_by_id(card["card_type_id"])
    kind = ct["kind"] if ct else "储值"

    if kind == "次卡":
        if not user_card_repo.deduct_times(card["card_id"], 1, cur=cur):
            raise BizError("次卡剩余次数不足")
        return 0.0
    if kind == "时长卡":
        if not user_card_repo.deduct_hours(card["card_id"], hours, cur=cur):
            raise BizError("时长卡剩余时长不足")
        return 0.0

    amount = round(float(price_per_hour) * hours * float(ct["discount"]), 2)
    if not user_card_repo.deduct_balance(card["card_id"], amount, cur=cur):
        raise BizError("卡内余额不足")
    return amount


def _refund(cur, card_id, amount, hours):
    """取消预约时把钱按原路退回去。"""
    if not card_id:
        return
    card = user_card_repo.get_by_id(card_id)
    if card is None:
        return
    ct = card_type_repo.get_by_id(card["card_type_id"])
    kind = ct["kind"] if ct else "储值"
    if kind == "次卡":
        user_card_repo.add_times(card_id, 1, cur=cur)
    elif kind == "时长卡":
        user_card_repo.add_hours(card_id, hours, cur=cur)
    else:
        user_card_repo.add_balance(card_id, amount, cur=cur)


def reserve(user_id, seat_id, reserve_date, start_time, hours=1, card_id=None):
    """预约座位。成功返回 dict，失败抛 BizError。

    两道并发防线：
        1) 扣费靠 SQL 的 balance >= x 条件（原子，见 user_card_repo）
        2) 占座位靠唯一索引 uk_seat_slot——插不进去就说明被人抢了
    """
    hours = int(hours)
    if not 1 <= hours <= MAX_HOURS:
        raise BizError(f"一次最多预约 {MAX_HOURS} 小时")

    seat = seat_repo.get_by_id(seat_id)
    if seat is None:
        raise BizError("座位不存在")
    if seat["status"] != "可用":
        raise BizError("这个座位当前不可预约")

    start_time = str(start_time)
    end_time = _end_time(start_time, hours)
    if end_time <= start_time:
        raise BizError("结束时间必须晚于开始时间")

    card = _pick_card(user_id, card_id)
    order_no = reservation_repo.generate_order_no()

    try:
        with uow() as cur:
            # 锁住这张卡，防止并发扣同一张
            locked = user_card_repo.get_for_update(cur, card["card_id"])
            if locked is None or locked["status"] != "正常":
                raise BizError("这张卡当前不可用")

            amount = _charge(cur, locked, hours, seat["price_per_hour"])

            reservation_id = reservation_repo.create(
                order_no, user_id, seat_id, reserve_date, start_time, end_time,
                hours, amount, card["card_id"], cur=cur,
            )
    except pymysql.err.IntegrityError:
        raise BizError("这个时段刚刚被别人约走了，请换一个")

    return {
        "reservation_id": reservation_id,
        "order_no": order_no,
        "seat_no": seat["seat_no"],
        "reserve_date": str(reserve_date),
        "start_time": start_time,
        "end_time": end_time,
        "amount": amount,
    }


def cancel(reservation_id, user_id):
    """取消预约：释放时段 + 退款。两边在同一个事务里。"""
    res = reservation_repo.get_by_id(reservation_id)
    if res is None:
        raise BizError("预约不存在")
    if res["user_id"] != user_id:
        raise BizError("只能取消自己的预约")
    if res["status"] not in ("待使用", "使用中"):
        raise BizError(f"当前状态是「{res['status']}」，不能取消")

    with uow() as cur:
        if reservation_repo.cancel(reservation_id, cur=cur) == 0:
            raise BizError("取消失败，预约状态刚刚变了，请刷新")
        _refund(cur, res["card_id"], float(res["amount"]), res["hours"])

    return {"reservation_id": reservation_id, "refund": float(res["amount"])}


def check_in(reservation_id):
    """到店签到：待使用 -> 使用中。

    注意：这一步由谁触发还没拍板（管理员手工签到 or 定时任务），见 DESIGN.md 的 A1。
    """
    res = reservation_repo.get_by_id(reservation_id)
    if res is None:
        raise BizError("预约不存在")
    if res["status"] != "待使用":
        raise BizError(f"当前状态是「{res['status']}」，不能签到")
    reservation_repo.update_status(reservation_id, "使用中")
    return True


def finish(reservation_id):
    """结束使用：使用中 -> 已完成。"""
    res = reservation_repo.get_by_id(reservation_id)
    if res is None:
        raise BizError("预约不存在")
    if res["status"] != "使用中":
        raise BizError(f"当前状态是「{res['status']}」，不能结束")
    reservation_repo.update_status(reservation_id, "已完成")
    return True


def list_my_orders(user_id, page=1, page_size=20):
    """我的订单。返回 (数据列表, 总条数)。"""
    offset = (max(page, 1) - 1) * page_size
    return (reservation_repo.list_by_user(user_id, offset, page_size),
            reservation_repo.count_by_user(user_id))


def list_orders(store_id=None, status=None, page=1, page_size=20):
    """管理端订单列表。返回 (数据列表, 总条数)。"""
    offset = (max(page, 1) - 1) * page_size
    return (reservation_repo.list_paged(store_id, status, offset, page_size),
            reservation_repo.count_paged(store_id, status))
