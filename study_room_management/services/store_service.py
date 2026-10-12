"""门店与座位的管理业务。"""
import pymysql

from repository import seat_repo, store_repo
from services.exceptions import BizError


def list_stores():
    """用户端：只返回营业中的门店。"""
    return store_repo.list_all(status="营业")


def get_store(store_id):
    """查一家门店，不存在就抛 BizError。"""
    store = store_repo.get_by_id(store_id)
    if store is None:
        raise BizError("门店不存在")
    return store


def list_stores_paged(keyword=None, page=1, page_size=20):
    """管理端门店列表。返回 (列表, 总数)。"""
    offset = (max(page, 1) - 1) * page_size
    return (store_repo.list_paged(keyword, offset, page_size),
            store_repo.count(keyword))


def create_store(name, address, phone=None, open_time="08:00:00", close_time="22:00:00"):
    """新建门店，返回 store_id。"""
    name = (name or "").strip()
    address = (address or "").strip()
    if not name or not address:
        raise BizError("门店名和地址都不能为空")
    try:
        return store_repo.create(name, address, phone, open_time, close_time)
    except pymysql.err.IntegrityError:
        raise BizError("已经有同名门店了")


def update_store(store_id, **fields):
    """改门店信息，例：update_store(1, name="新名字", phone="0571-1234")。"""
    get_store(store_id)
    return store_repo.update(store_id, **fields)


def set_store_status(store_id, status):
    """营业 / 停业。"""
    if status not in ("营业", "停业"):
        raise BizError("门店状态只能是「营业」或「停业」")
    get_store(store_id)
    return store_repo.update_status(store_id, status)


def list_seats(store_id, status=None):
    """某门店的座位，status 传 '可用' 可只看能用的。"""
    return seat_repo.list_by_store(store_id, status)


def batch_add_seats(store_id, prefix, count, zone=None, price_per_hour=0):
    """批量新增座位：prefix='A', count=20 就生成 A01 ~ A20。返回成功条数。"""
    get_store(store_id)
    prefix = (prefix or "").strip().upper()
    count = int(count)
    if not prefix:
        raise BizError("请填座位编号的前缀，比如 A")
    if not 1 <= count <= 200:
        raise BizError("一次最多新增 200 个座位")

    seats = [(f"{prefix}{i:02d}", zone, price_per_hour) for i in range(1, count + 1)]
    try:
        return seat_repo.batch_create(store_id, seats)
    except pymysql.err.IntegrityError:
        raise BizError(f"{prefix}01 起有编号重复了，换个前缀，或者先删掉已有座位")


def set_seat_status(seat_id, status):
    """可用 / 维修 / 停用。"""
    if status not in ("可用", "维修", "停用"):
        raise BizError("座位状态只能是「可用」「维修」「停用」")
    if seat_repo.get_by_id(seat_id) is None:
        raise BizError("座位不存在")
    return seat_repo.update_status(seat_id, status)


def find_available_seats(store_id, reserve_date, start_time, end_time):
    """某门店某时段还空着的座位（预约页直接用）。"""
    return seat_repo.list_available(store_id, reserve_date, start_time, end_time)


def count_seats(store_id, status=None):
    return seat_repo.count_by_store(store_id, status)
