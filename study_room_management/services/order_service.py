"""预约业务：下单、取消、状态流转。

本文件不写 SQL；涉及钱的操作全部走 db/uow.py 的事务。

计费口径（规范里座位表没有价格列，所以按「卡」计费）：
    kind=1 时长卡 → 扣 duration 分钟（不足 1 分钟按 1 分钟）
    kind=2 次卡   → 每次预约扣 1 次
    kind=3 储值卡 → 按小时单价 × 时长，向上取整到整小时
                    小时单价 = card_type.price ÷ (card_type.value/60)，
                    即「售价 ÷ 卡原价小时数」，例如 100 元储值卡 value=0 时
                    退回该卡种售价；规范未给储值单价时的兜底规则见下方 _hourly_rate。
"""
from datetime import date, datetime

import pymysql

from config import (KIND_HOURS, KIND_STORED, KIND_TIMES, MAX_RESERVE_MINUTES,
                    ORDER_DONE, ORDER_ONGOING, ORDER_PENDING,
                    RESERVE_STEP_MINUTES, STORED_HOUR_RATE)
from db.uow import uow
from repository import (card_type_repo, reservation_repo, seat_repo, user_card_repo,
                        user_repo)
from services.exceptions import BizError


# 时间工具：库里 start_time/end_time 是 TIME，duration 是分钟
def to_minutes(hhmmss) -> int:
    """'14:00:00' -> 840（分钟）。"""
    t = datetime.strptime(str(hhmmss)[:8], "%H:%M:%S")
    return t.hour * 60 + t.minute


def to_time_str(minutes: int) -> str:
    """840 -> '14:00:00'。超过 24 点按当天最大 23:59 截断。"""
    minutes = min(int(minutes), 23 * 60 + 59)
    return f"{minutes // 60:02d}:{minutes % 60:02d}:00"


def make_end_time(start_time, duration_minutes: int) -> str:
    """开始时间 + 时长 -> 结束时间字符串。"""
    return to_time_str(to_minutes(start_time) + int(duration_minutes))


def current_slot():
    """当前时刻的查询时段 (date, start_time, end_time)，格式与库里一致。

    「这个座位现在被占用了吗」= 有没有一条有效预约满足
    start_time <= 现在 < end_time。直接把当前时刻当查询区间用即可：
    对区间重叠判定来说，「区间包含某一点」就是「与那个点重叠」，
    所以首页/看板不需要另外写一套 SQL。

    示例：现在 14:30 → (date(今天), '14:30:00', '14:30:00')，
    14:00~16:00 的预约会命中（start < 14:30 且 end > 14:30），
    而 09:00~11:00 的历史预约不会命中。
    """
    now = datetime.now()
    hhmmss = now.strftime("%H:%M:%S")
    return now.date(), hhmmss, hhmmss


def normalize_duration(duration) -> int:
    """校验并规整时长（分钟）：必须是整小时、在 1~8 小时之间。"""
    try:
        duration = int(duration)
    except (TypeError, ValueError):
        raise BizError("时长必须是整数分钟")
    if duration < 60 or duration > MAX_RESERVE_MINUTES:
        raise BizError(f"一次可预约 1~{MAX_RESERVE_MINUTES // 60} 小时")
    if duration % RESERVE_STEP_MINUTES != 0:
        raise BizError("时长必须是整小时")
    return duration


# 选卡与计费
def _pick_card(user_id, card_id=None):
    """选卡：传了 card_id 就用它，没传就自动取第一张可用的。"""
    cards = user_card_repo.list_active_by_user(user_id)
    if not cards:
        raise BizError("你还没有可用的会员卡，请先购卡充值")
    if card_id is None:
        return cards[0]
    for c in cards:
        if c["card_id"] == card_id:
            return c
    raise BizError("这张卡当前不可用（可能已过期或被冻结）")


def _hourly_rate(ct) -> float:
    """储值卡的小时单价（元/小时）。

    规范里 card_type 没有「储值卡单价」列，所以约定：
      1) value > 0 → 把 value 当作「这张卡包含的小时数」，单价 = price ÷ value
         （例：100 元的储值卡 value=20，就是 5 元/小时）
      2) value = 0 → 用 config.STORED_HOUR_RATE 兜底
    管理员要调价，在卡种管理里把 value 填成小时数即可，不用改代码。
    """
    value = int(ct.get("value") or 0)
    if value > 0:
        return round(float(ct["price"]) / value, 2)
    return float(STORED_HOUR_RATE)


def estimate_amount(card, duration_minutes):
    """预估这次预约要花多少钱（储值卡才有金额，其余返回 0）。"""
    if not card:
        return 0.0
    ct = card_type_repo.get_by_id(card["card_type_id"])
    if ct is None or int(ct["kind"]) != KIND_STORED:
        return 0.0
    hours = max(1, -(-int(duration_minutes) // 60))     # 向上取整到整小时
    return round(_hourly_rate(ct) * hours, 2)


def _charge(cur, card, duration_minutes):
    """按卡种扣费，返回本次实际扣掉的钱。不够用就抛 BizError。

    扣减全部走「带条件的原子 UPDATE」，并发下不会扣穿。
    """
    ct = card_type_repo.get_by_id(card["card_type_id"])
    if ct is None:
        raise BizError("卡种已不存在，请联系管理员")
    kind = int(ct["kind"])
    card_id = card["card_id"]
    duration_minutes = max(1, int(duration_minutes))

    if kind == KIND_TIMES:
        if not user_card_repo.deduct_times(card_id, 1, cur=cur):
            raise BizError("次卡剩余次数不足")
        return 0.0

    if kind == KIND_HOURS:
        if not user_card_repo.deduct_minutes(card_id, duration_minutes, cur=cur):
            raise BizError("时长卡剩余时长不足")
        return 0.0

    # 储值卡
    hours = max(1, -(-duration_minutes // 60))
    amount = round(_hourly_rate(ct) * hours, 2)
    if amount > 0 and not user_card_repo.deduct_balance(card_id, amount, cur=cur):
        raise BizError(f"卡内余额不足，本次需要 {amount:.2f} 元")
    return amount


def _refund(cur, card_id, amount, duration_minutes, user_id):
    """取消预约时把权益按原路退回。"""
    if not card_id:
        return
    card = user_card_repo.get_for_update(cur, card_id)
    if card is None:
        return
    ct = card_type_repo.get_by_id(card["card_type_id"])
    if ct is None:
        return
    kind = int(ct["kind"])

    if kind == KIND_TIMES:
        user_card_repo.add_times(card_id, 1, cur=cur)
    elif kind == KIND_HOURS:
        user_card_repo.add_minutes(card_id, max(1, int(duration_minutes)), cur=cur)
    elif float(amount) > 0:
        user_card_repo.add_balance(card_id, float(amount), cur=cur)

    # 卡内资产变了，同步 user 表的汇总冗余字段
    user_repo.refresh_summary(cur, user_id)


# 对外业务
def reserve(user_id, seat_id, reserve_date, start_time, duration, card_id=None,
            store_id=None):
    """预约座位。成功返回 dict，失败抛 BizError。

    四道并发防线（顺序不能乱，见 docs/DESIGN.md「预约下单的四道防线」）：
        1) 扣费靠 SQL 的 balance >= x / remaining_* >= x 条件（原子，见 user_card_repo）
        2) FOR UPDATE 锁卡 —— 并发下不会扣穿同一张卡
        3) GET_LOCK 锁座位 —— 把「查重叠 + 插入」串行化，这是唯一能挡住
           **部分重叠时段**（09:00~11:00 与 10:00~12:00）的机制
        4) uk_seat_slot 唯一索引兜底完全相同 / 同开始时间的时段
    """
    duration = normalize_duration(duration)

    seat = seat_repo.get_by_id(seat_id)
    if seat is None:
        raise BizError("座位不存在")
    if int(seat["status"]) != 1:
        raise BizError("这个座位当前不可预约")

    # 门店以座位实际所属门店为准，杜绝前端传错
    real_store_id = int(seat["store_id"])
    if store_id is not None and int(store_id) != real_store_id:
        raise BizError("座位与门店不匹配，请重新选择")

    try:
        reserve_date = datetime.strptime(str(reserve_date), "%Y-%m-%d").date()
    except ValueError:
        raise BizError("预约日期格式不正确")
    if reserve_date < date.today():
        raise BizError("不能预约过去的日期")

    start_time = str(start_time)
    end_time = make_end_time(start_time, duration)
    if to_minutes(end_time) <= to_minutes(start_time):
        raise BizError("结束时间必须晚于开始时间，且不能跨天")

    card = _pick_card(user_id, card_id)
    order_no = reservation_repo.generate_order_no()

    # GET_LOCK 是「连接级」锁：必须用**同一条连接**释放，不能另开一条连接去 unlock。
    # 所以这里在事务正常走完之后、uow 关连接之前，用同一个 cur 直接解锁。
    # 抛异常的分支不用管：uow 会关闭那条连接，连接级锁随连接一起释放。
    try:
        with uow() as cur:
            # 锁住这张卡，防止并发扣同一张
            locked = user_card_repo.get_for_update(cur, card["card_id"])
            if locked is None or int(locked["status"]) != 1:
                raise BizError("这张卡当前不可用")
            if locked["expire_at"] is not None and locked["expire_at"] < date.today():
                raise BizError("这张卡已过期")

            # 再锁座位：把「同一个座位的时段冲突检查 + 插入」串行化。
            # 顺序固定为「先卡后座位」，和其他事务保持一致，避免交叉死锁。
            if not reservation_repo.lock_seat_slot(seat_id, cur):
                raise BizError("有人正在预约这个座位，请稍后重试")

            # 拿到锁之后再查重叠，这次查的结果在锁释放前都有效。
            # 唯一索引只挡「完全相同的时段」，挡不住部分重叠，所以这一查是必需的。
            if seat_repo.has_active_reservation(cur, seat_id, reserve_date,
                                                start_time, end_time):
                raise BizError("这个时段已经被预约了，请换一个时段或座位")

            amount = _charge(cur, locked, duration)

            order_id = reservation_repo.create(
                order_no, user_id, seat_id, real_store_id, reserve_date,
                start_time, end_time, duration, amount,
                card_id=card["card_id"], cur=cur,
            )

            # 扣完卡内资产，同步 user 表汇总
            user_repo.refresh_summary(cur, user_id)

            # 事务最后一步、也是同一条连接：把座位锁还回去
            reservation_repo.unlock_seat_slot(seat_id, cur)
    except pymysql.err.IntegrityError as e:
        # uk_seat_slot 撞了 = 这个时段刚被别人约走（正常抢座之外的最后一道兜底）
        if "uk_seat_slot" in str(e):
            raise BizError("这个时段刚刚被别人约走了，请换一个")
        raise BizError("下单失败，请重试")

    return {
        "order_id": order_id,
        "order_no": order_no,
        "seat_id": seat_id,
        "seat_code": seat["seat_code"],
        "store_id": real_store_id,
        "reserve_date": str(reserve_date),
        "start_time": start_time,
        "end_time": end_time,
        "duration": duration,
        "amount": float(amount),
        "card_id": card["card_id"],
    }


def cancel(order_id, user_id):
    """取消预约：释放时段 + 退回权益。两边在同一个事务里。"""
    res = reservation_repo.get_by_id(order_id)
    if res is None:
        raise BizError("预约不存在")
    if res["user_id"] != user_id:
        raise BizError("只能取消自己的预约")
    if int(res["order_status"]) not in (ORDER_PENDING, ORDER_ONGOING):
        raise BizError("当前状态不允许取消（只有待使用/进行中可以取消）")

    with uow() as cur:
        if reservation_repo.cancel(order_id, cur=cur) == 0:
            raise BizError("取消失败，预约状态刚刚变了，请刷新")
        _refund(cur, res["card_id"], float(res["amount"]), res["duration"], user_id)

    return {"order_id": order_id, "refund": float(res["amount"])}


def check_in(order_id, user_id=None):
    """到店签到：待使用(1) -> 进行中(2)。

    现在这一步**平时不需要人工点了**：到了预约开始时间，页面打开时
    sync_time_status() 会自动把订单推进到「进行中」。
    本函数保留下来作为「提前到店、手动提前开始」的入口，也方便管理端纠错。

    注意：一旦订单已经被自动流转成「进行中」或「已完成」，再点签到会提示
    「只有待使用的预约可以签到」，这是预期行为。
    """
    res = reservation_repo.get_by_id(order_id)
    if res is None:
        raise BizError("预约不存在")
    if user_id is not None and res["user_id"] != user_id:
        raise BizError("只能操作自己的预约")
    if int(res["order_status"]) != ORDER_PENDING:
        raise BizError("只有「待使用」的预约可以签到")
    reservation_repo.update_status(order_id, ORDER_ONGOING)
    return True


def finish(order_id):
    """结束使用：进行中(2) -> 已完成(3)。"""
    res = reservation_repo.get_by_id(order_id)
    if res is None:
        raise BizError("预约不存在")
    if int(res["order_status"]) != ORDER_ONGOING:
        raise BizError("只有「进行中」的预约可以结束")
    reservation_repo.update_status(order_id, ORDER_DONE)
    return True


def expire_overdue():
    """把过期未使用的预约标成已过期(5)并释放时段。返回更新行数。"""
    return reservation_repo.expire_overdue()


def sync_time_status():
    """按当前时间自动推进订单状态，返回 (新变进行中, 新变已完成) 条数。

    这个项目没有常驻定时任务（Streamlit 进程只在有人访问时活着），所以
    「到点自动变进行中」用「打开页面时顺手推一把」的方式实现：
    用户端首页/我的订单、管理端订单管理/看板每次渲染时调一次，
    由 ui/components.py 的 sync_time_status_once() 做 60 秒节流，
    不会每点一次按钮都写一次库。

    失败不能影响页面渲染：调用方用 try/except 包住（见 components 里的封装）。
    """
    return reservation_repo.sync_time_status()


def list_my_orders(user_id, page=1, page_size=20):
    """我的订单。返回 (数据列表, 总条数)。"""
    offset = (max(page, 1) - 1) * page_size
    return (reservation_repo.list_by_user(user_id, offset, page_size),
            reservation_repo.count_by_user(user_id))


def list_orders(store_id=None, order_status=None, start_date=None, end_date=None,
                page=1, page_size=20):
    """管理端订单列表。返回 (数据列表, 总条数)。

    start_date / end_date 是预约日期闭区间，用于「按日期区间筛订单」。
    """
    offset = (max(page, 1) - 1) * page_size
    return (reservation_repo.list_paged(store_id, order_status, start_date,
                                        end_date, offset, page_size),
            reservation_repo.count_paged(store_id, order_status, start_date,
                                         end_date))
