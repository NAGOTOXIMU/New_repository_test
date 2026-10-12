"""充值 / 购卡业务，事务边界最典型的地方。

支付要在一个事务里做两件事：订单改成「已支付」+ 生成或累加持卡实例。
两步同成同败，否则会出现「钱付了卡没到」。

规范要点：pay_status(0待支付 1已支付 2已退款)；卡种用 card_type_id；
资产（余额/次数/分钟）落在 user_card 上，user 表的字段是汇总冗余。
"""
from datetime import date, timedelta

import pymysql

from config import KIND_HOURS, KIND_STORED, KIND_TIMES, PAY_PAID, PAY_UNPAID
from db.uow import uow
from repository import card_type_repo, recharge_repo, user_card_repo, user_repo
from services.exceptions import BizError


def list_card_types():
    """在售卡种（用户端用）。"""
    return card_type_repo.list_online()


def create_order(user_id, card_type_id):
    """下单，状态为「待支付」。返回订单信息。"""
    ct = card_type_repo.get_by_id(card_type_id)
    if ct is None or int(ct["status"]) != 1:
        raise BizError("这个卡种当前不可购买")

    order_no = recharge_repo.generate_order_no()
    try:
        recharge_id = recharge_repo.create(order_no, user_id, card_type_id, ct["price"])
    except pymysql.err.IntegrityError:
        raise BizError("订单号重复了，请重新提交")

    return {"recharge_id": recharge_id, "order_no": order_no,
            "amount": float(ct["price"]), "card_name": ct["card_name"],
            "kind": int(ct["kind"])}


def pay(order_no):
    """支付并到账，返回卡信息。

    一个事务里：
        1) 订单改成「已支付」，同时记下持卡实例 id
        2) 已有同卡种的可用卡就累加，没有就新开一张
        3) 同步 user 表的余额/时长汇总冗余字段
    """
    order = recharge_repo.get_by_order_no(order_no)
    if order is None:
        raise BizError("订单不存在")
    if int(order["pay_status"]) == PAY_PAID:
        raise BizError("这单已经支付过了")
    if int(order["pay_status"]) != PAY_UNPAID:
        raise BizError("这单不是待支付状态，不能支付")

    ct = card_type_repo.get_by_id(order["card_type_id"])
    if ct is None:
        raise BizError("卡种已不存在，请联系管理员")

    kind = int(ct["kind"])
    value = int(ct["value"] or 0)
    expire_at = date.today() + timedelta(days=int(ct["valid_days"]))

    # 按卡种决定这次到账给什么权益
    if kind == KIND_HOURS:
        balance_delta, times_delta, minutes_delta = 0.00, 0, value
    elif kind == KIND_TIMES:
        balance_delta, times_delta, minutes_delta = 0.00, value, 0
    else:   # 储值卡
        balance_delta = float(order["amount"])
        times_delta, minutes_delta = 0, 0

    with uow() as cur:
        card_id, card_no, created = user_card_repo.upsert_by_type(
            order["user_id"], ct["card_type_id"], kind,
            balance_delta, times_delta, minutes_delta, expire_at, cur,
        )

        if recharge_repo.mark_paid(order["recharge_id"], card_id, cur=cur) == 0:
            raise BizError("订单状态刚刚变了，请刷新后重试")

        user_repo.refresh_summary(cur, order["user_id"])

    return {"order_no": order_no, "card_id": card_id, "card_no": card_no,
            "card_name": ct["card_name"], "amount": float(order["amount"]),
            "created": created}


def cancel_order(order_no):
    """取消未支付的订单。

    规范里 pay_status 只有 0待支付/1已支付/2已退款，没有「已取消」态。
    待支付订单没产生任何资产，所以直接删掉这条记录才是干净的语义
    （repository.delete_unpaid 带 pay_status=0 条件，绝不会误删已支付流水）。
    """
    order = recharge_repo.get_by_order_no(order_no)
    if order is None:
        raise BizError("订单不存在")
    if int(order["pay_status"]) == PAY_PAID:
        raise BizError("这单已支付，不能取消；如需退费请走退款流程")
    if recharge_repo.delete_unpaid(order["recharge_id"]) == 0:
        raise BizError("取消失败，订单状态刚刚变了，请刷新")
    return True


def refund_order(order_no):
    """退款：把已到账的权益收回，并把订单标成已退款(2)。

    ⚠️ 只在权益尚未消费时允许退款（余额/次数/分钟必须够扣）。
    """
    order = recharge_repo.get_by_order_no(order_no)
    if order is None:
        raise BizError("订单不存在")
    if int(order["pay_status"]) != PAY_PAID:
        raise BizError("只有已支付的订单可以退款")

    ct = card_type_repo.get_by_id(order["card_type_id"])
    if ct is None:
        raise BizError("卡种已不存在，请联系管理员")

    kind = int(ct["kind"])
    value = int(ct["value"] or 0)
    card_id = order["card_id"]
    if card_id is None:
        raise BizError("这单没有关联的卡，无法退款")

    with uow() as cur:
        if kind == KIND_HOURS:
            if not user_card_repo.deduct_minutes(card_id, value, cur=cur):
                raise BizError("卡内时长已被消费，无法原路退回")
        elif kind == KIND_TIMES:
            if not user_card_repo.deduct_times(card_id, value, cur=cur):
                raise BizError("卡内次数已被消费，无法原路退回")
        else:
            if not user_card_repo.deduct_balance(card_id, float(order["amount"]), cur=cur):
                raise BizError("卡内余额已被消费，无法原路退回")

        if recharge_repo.mark_refunded(order["recharge_id"], cur=cur) == 0:
            raise BizError("订单状态刚刚变了，请刷新后重试")

        user_repo.refresh_summary(cur, order["user_id"])

    return {"order_no": order_no, "refund": float(order["amount"])}


def list_my_recharges(user_id, page=1, page_size=20):
    """我的充值记录。返回 (数据列表, 总条数)。"""
    offset = (max(page, 1) - 1) * page_size
    return (recharge_repo.list_by_user(user_id, offset, page_size),
            recharge_repo.count_by_user(user_id))


def list_all(pay_status=None, page=1, page_size=20):
    """管理端充值订单列表。返回 (数据列表, 总条数)。"""
    offset = (max(page, 1) - 1) * page_size
    return (recharge_repo.list_paged(pay_status, offset, page_size),
            recharge_repo.count_paged(pay_status))


def list_my_cards(user_id):
    """我持有的所有卡（含已过期）。"""
    return user_card_repo.list_by_user(user_id)


def list_my_active_cards(user_id):
    """我当前可用的卡。"""
    return user_card_repo.list_active_by_user(user_id)
