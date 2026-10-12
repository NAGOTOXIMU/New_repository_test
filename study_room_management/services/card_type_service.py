"""卡种管理业务（管理端）。"""
import pymysql

from repository import card_type_repo
from services.exceptions import BizError

_KINDS = ("储值", "次卡", "时长卡")
_STATUSES = ("上架", "下架")


def list_card_types_paged(page=1, page_size=20):
    """管理端卡种列表（含已下架）。返回 (列表, 总数)。"""
    offset = (max(page, 1) - 1) * page_size
    return card_type_repo.list_paged(offset, page_size), card_type_repo.count()


def get_card_type(card_type_id):
    """查一个卡种，不存在抛 BizError。"""
    ct = card_type_repo.get_by_id(card_type_id)
    if ct is None:
        raise BizError("卡种不存在")
    return ct


def _validate(name, kind, price, discount, valid_days,
              face_value=None, total_times=None, total_hours=None):
    """通用字段校验，与数据库 CHECK 约束保持一致。"""
    name = (name or "").strip()
    if not name:
        raise BizError("卡种名称不能为空")
    if kind not in _KINDS:
        raise BizError(f"卡种类型只能是 {_KINDS} 之一")
    if price is None or float(price) < 0:
        raise BizError("售价 price 必须 >= 0")
    if discount is None or not (0.01 <= float(discount) <= 1.00):
        raise BizError("折扣 discount 必须在 0.01 ~ 1.00 之间")
    if valid_days is None or int(valid_days) <= 0:
        raise BizError("有效期 valid_days 必须 > 0")

    if kind == "储值":
        if face_value is None or float(face_value) < 0:
            raise BizError("储值卡必须填写到账金额 face_value（>= 0）")
    elif kind == "次卡":
        if total_times is None or int(total_times) <= 0:
            raise BizError("次卡必须填写总次数 total_times（> 0）")
    elif kind == "时长卡":
        if total_hours is None or int(total_hours) <= 0:
            raise BizError("时长卡必须填写总时长 total_hours（> 0）")

    return {
        "name": name,
        "kind": kind,
        "price": float(price),
        "face_value": float(face_value) if face_value is not None else None,
        "total_times": int(total_times) if total_times is not None else None,
        "total_hours": int(total_hours) if total_hours is not None else None,
        "valid_days": int(valid_days),
        "discount": float(discount),
    }


def create_card_type(name, kind, price, face_value=None, total_times=None,
                     total_hours=None, valid_days=365, discount=1.00):
    """新建卡种，返回 card_type_id。"""
    data = _validate(name, kind, price, discount, valid_days,
                     face_value, total_times, total_hours)
    try:
        return card_type_repo.create(**data)
    except pymysql.err.IntegrityError:
        raise BizError("已经有同名卡种了")


def update_card_type(card_type_id, **fields):
    """改卡种信息。只接受卡种相关字段，自动做校验。"""
    ct = get_card_type(card_type_id)

    # 用库里已有值兜底，保证校验时字段齐全
    merged = {
        "name": fields.get("name", ct["name"]),
        "kind": fields.get("kind", ct["kind"]),
        "price": fields.get("price", ct["price"]),
        "face_value": fields.get("face_value", ct["face_value"]),
        "total_times": fields.get("total_times", ct["total_times"]),
        "total_hours": fields.get("total_hours", ct["total_hours"]),
        "valid_days": fields.get("valid_days", ct["valid_days"]),
        "discount": fields.get("discount", ct["discount"]),
    }
    data = _validate(**merged)

    # 只把调用方实际传进来的字段交给 repo 更新
    updates = {k: data[k] for k in fields if k in data}
    if not updates:
        return 0
    return card_type_repo.update(card_type_id, **updates)


def set_card_type_status(card_type_id, status):
    """上架 / 下架。"""
    if status not in _STATUSES:
        raise BizError("卡种状态只能是「上架」或「下架」")
    get_card_type(card_type_id)
    return card_type_repo.update_status(card_type_id, status)
