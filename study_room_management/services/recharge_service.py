"""充值 / 购卡业务，事务边界最典型的地方。

支付要在一个事务里做两件事：订单改成「已支付」+ 生成或累加会员卡。
两步同成同败，否则会出现"钱付了卡没到"。
"""
from datetime import date, timedelta

import pymysql

from db.uow import uow
from repository import card_type_repo, recharge_repo, user_card_repo
from services.exceptions import BizError


def list_card_types():
    """在售卡种（用户端用）。"""
    return card_type_repo.list_online()


def create_order(user_id, card_type_id, pay_method="微信"):
    """下单，状态为「待支付」。返回订单信息。"""
    ct = card_type_repo.get_by_id(card_type_id)
    if ct is None or ct["status"] != "上架":
        raise BizError("这个卡种当前不可购买")

    order_no = recharge_repo.generate_order_no()
    try:
        recharge_id = recharge_repo.create(order_no, user_id, card_type_id,
                                           ct["price"], pay_method)
    except pymysql.err.IntegrityError:
        raise BizError("订单号重复了，请重新提交")

    return {"recharge_id": recharge_id, "order_no": order_no,
            "amount": float(ct["price"]), "card_type": ct["name"]}


def pay(order_no):
    """支付并到账，返回卡信息。

    一个事务里：
        1) 订单改成「已支付」，同时记下卡 id
        2) 已有同卡种的可用卡就累加，没有就新开一张
    """
    order = recharge_repo.get_by_order_no(order_no)
    if order is None:
        raise BizError("订单不存在")
    if order["status"] == "已支付":
        raise BizError("这单已经支付过了")
    if order["status"] != "待支付":
        raise BizError(f"订单状态是「{order['status']}」，不能支付")

    ct = card_type_repo.get_by_id(order["card_type_id"])

    existing = None
    for c in user_card_repo.list_active_by_user(order["user_id"]):
        if c["card_type_id"] == ct["card_type_id"]:
            existing = c
            break

    with uow() as cur:
        if existing:
            card_id = existing["card_id"]
            card_no = existing["card_no"]
            if ct["kind"] == "次卡":
                user_card_repo.add_times(card_id, ct["total_times"] or 0, cur=cur)
            elif ct["kind"] == "时长卡":
                user_card_repo.add_hours(card_id, ct["total_hours"] or 0, cur=cur)
            else:
                user_card_repo.add_balance(card_id, float(ct["face_value"] or 0), cur=cur)
        else:
            card_no = user_card_repo.generate_card_no()
            card_id = user_card_repo.create(
                card_no, order["user_id"], ct["card_type_id"],
                balance=float(ct["face_value"] or 0),
                remaining_times=ct["total_times"],
                remaining_hours=ct["total_hours"],
                expire_at=date.today() + timedelta(days=ct["valid_days"]),
                cur=cur,
            )

        if recharge_repo.mark_paid(order["recharge_id"], card_id, cur=cur) == 0:
            raise BizError("订单状态刚刚变了，请刷新后重试")

    return {"order_no": order_no, "card_id": card_id, "card_no": card_no,
            "amount": float(order["amount"])}


def cancel_order(order_no):
    """取消未支付的订单。"""
    order = recharge_repo.get_by_order_no(order_no)
    if order is None:
        raise BizError("订单不存在")
    if order["status"] != "待支付":
        raise BizError(f"订单状态是「{order['status']}」，不能取消")
    recharge_repo.cancel(order["recharge_id"])
    return True


def list_my_recharges(user_id, page=1, page_size=20):
    """我的充值记录。返回 (数据列表, 总条数)。"""
    offset = (max(page, 1) - 1) * page_size
    return (recharge_repo.list_by_user(user_id, offset, page_size),
            recharge_repo.count_by_user(user_id))


def list_all(status=None, page=1, page_size=20):
    """管理端充值订单列表。返回 (数据列表, 总条数)。"""
    offset = (max(page, 1) - 1) * page_size
    return (recharge_repo.list_paged(status, offset, page_size),
            recharge_repo.count_paged(status))
