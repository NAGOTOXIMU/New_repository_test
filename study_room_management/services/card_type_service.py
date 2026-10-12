"""卡种管理业务（管理端）。本文件不写 SQL，只做校验和调用 repository。

规范口径：卡类型列是 kind(TINYINT，1时长卡 2次卡 3储值卡)；
「对应价值」统一放在 value 一列：时长卡=分钟数，次卡=次数，储值卡=卡内小时数；
上架状态是 status(TINYINT，1上架 0下架)。

校验口径与数据库 CHECK 约束保持一致：price >= 0、value >= 0、valid_days > 0、
kind ∈ {1,2,3}。改了这里的规则，必须同步 db/sql/01_schema.sql。
"""
import pymysql

from config import (KIND_HOURS, KIND_NAMES, KIND_STORED, KIND_TIMES, STATUS_OFF,
                    STATUS_ON)
from repository import card_type_repo
from services.exceptions import BizError

_KINDS = (KIND_HOURS, KIND_TIMES, KIND_STORED)
_STATUSES = (STATUS_ON, STATUS_OFF)


def list_card_types_paged(page=1, page_size=20):
    """管理端卡种列表（含已下架）。返回 (数据列表, 总条数)。"""
    offset = (max(page, 1) - 1) * page_size
    return card_type_repo.list_paged(offset, page_size), card_type_repo.count()


def get_card_type(card_type_id):
    """查一个卡种，不存在就抛 BizError。"""
    ct = card_type_repo.get_by_id(card_type_id)
    if ct is None:
        raise BizError("卡种不存在")
    return ct


def _validate(card_name, kind, price, value, valid_days):
    """通用字段校验，与数据库 CHECK 约束保持一致。返回规整后的 dict。"""
    card_name = (card_name or "").strip()
    if not card_name:
        raise BizError("卡种名称不能为空")

    try:
        kind = int(kind)
    except (TypeError, ValueError):
        raise BizError("卡种类型只能是 1（时长卡）/ 2（次卡）/ 3（储值卡）")
    if kind not in _KINDS:
        raise BizError("卡种类型只能是 1（时长卡）/ 2（次卡）/ 3（储值卡）")

    try:
        price = float(price)
    except (TypeError, ValueError):
        raise BizError("售价必须是数字")
    if price < 0:
        raise BizError("售价 price 必须 >= 0")

    try:
        value = int(value or 0)
    except (TypeError, ValueError):
        raise BizError("对应价值必须是整数")
    if value < 0:
        raise BizError("对应价值 value 必须 >= 0")

    try:
        valid_days = int(valid_days)
    except (TypeError, ValueError):
        raise BizError("有效期必须是整数天")
    if valid_days <= 0:
        raise BizError("有效期 valid_days 必须 > 0")

    # 价值列的语义按卡种区分：时长卡是分钟、次卡是次数，都得有正数才卖得出去
    if kind == KIND_HOURS and value <= 0:
        raise BizError("时长卡必须填写总分钟数（value > 0）")
    if kind == KIND_TIMES and value <= 0:
        raise BizError("次卡必须填写总次数（value > 0）")
    # 储值卡：value 是「这张卡包含的小时数」，用来推导小时单价；
    # 填 0 表示不指定，计费时回落到 config.STORED_HOUR_RATE。

    return {"card_name": card_name, "kind": kind, "price": price,
            "value": value, "valid_days": valid_days}


def _check_price_sanity(data):
    """储值卡的小时单价 = 售价 ÷ 卡内小时数，明显不合理时提前拦下来。"""
    if data["kind"] != KIND_STORED or data["value"] <= 0:
        return
    hourly = data["price"] / data["value"]
    if hourly > 100:
        raise BizError(f"储值卡换算出来的小时单价是 {hourly:.2f} 元/小时，"
                       f"明显偏高，请检查售价和卡内小时数")


def create_card_type(card_name, kind, price, value=0, valid_days=365):
    """新建卡种，返回 card_type_id。"""
    data = _validate(card_name, kind, price, value, valid_days)
    _check_price_sanity(data)
    try:
        return card_type_repo.create(**data)
    except pymysql.err.IntegrityError:
        raise BizError("已经有同名卡种了")


def update_card_type(card_type_id, **fields):
    """改卡种信息。只接受卡种相关字段，自动做校验。返回影响行数。"""
    ct = get_card_type(card_type_id)

    # 用库里已有值兜底，保证校验时字段齐全
    merged = {
        "card_name": fields.get("card_name", ct["card_name"]),
        "kind": fields.get("kind", ct["kind"]),
        "price": fields.get("price", ct["price"]),
        "value": fields.get("value", ct["value"]),
        "valid_days": fields.get("valid_days", ct["valid_days"]),
    }
    data = _validate(**merged)
    _check_price_sanity(data)

    # 只把调用方实际传进来的字段交给 repo 更新
    updates = {k: data[k] for k in fields if k in data}
    if not updates:
        return 0
    try:
        return card_type_repo.update(card_type_id, **updates)
    except pymysql.err.IntegrityError:
        raise BizError("已经有同名卡种了")


def set_card_type_status(card_type_id, status):
    """上架(1) / 下架(0)。下架不等于删除，已售出的卡还能查到卡种。"""
    if status not in _STATUSES:
        raise BizError("卡种状态只能是 1（上架）或 0（下架）")
    get_card_type(card_type_id)
    return card_type_repo.update_status(card_type_id, status)


def describe_value(kind):
    """给界面层用的提示语：这个卡种的「对应价值」该填什么。"""
    if kind == KIND_HOURS:
        return "对应价值（分钟数）"
    if kind == KIND_TIMES:
        return "对应价值（次数）"
    return "对应价值（卡内小时数，填 0 表示不指定）"


def kind_display(kind):
    """kind 数字 -> 中文名。"""
    return KIND_NAMES.get(int(kind), "未知")
