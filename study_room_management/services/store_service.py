"""门店与座位的管理业务。

规范要点：门店名是 store_name；座位编号是 seat_code；区域是 area_type(TINYINT)；
状态一律 TINYINT（1 启用 / 0 停用）。
"""
import pymysql

from config import STATUS_OFF, STATUS_ON
from db.uow import uow
from repository import seat_repo, store_repo
from services.exceptions import BizError


# ---------------------------------------------------------------------------
# 门店
# ---------------------------------------------------------------------------
def list_stores():
    """用户端：只返回营业中的门店。"""
    return store_repo.list_all(status=STATUS_ON)


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


def create_store(store_name, address, open_time="08:00:00", close_time="22:00:00"):
    """新建门店，返回 store_id。"""
    store_name = (store_name or "").strip()
    address = (address or "").strip()
    if not store_name or not address:
        raise BizError("门店名和地址都不能为空")
    if str(close_time) <= str(open_time):
        raise BizError("关门时间必须晚于开门时间")
    try:
        return store_repo.create(store_name, address, open_time, close_time)
    except pymysql.err.IntegrityError:
        raise BizError("已经有同名门店了")


def update_store(store_id, **fields):
    """改门店信息，例：update_store(1, store_name="新名字")。"""
    get_store(store_id)
    try:
        return store_repo.update(store_id, **fields)
    except pymysql.err.IntegrityError:
        raise BizError("已经有同名门店了")


def set_store_status(store_id, status):
    """营业(1) / 停业(0)。"""
    if status not in (STATUS_ON, STATUS_OFF):
        raise BizError("门店状态只能是 1（营业）或 0（停业）")
    get_store(store_id)
    return store_repo.update_status(store_id, status)


# ---------------------------------------------------------------------------
# 座位
# ---------------------------------------------------------------------------
def list_seats(store_id, status=None):
    """某门店的座位，status 传 1 可只看能用的。"""
    return seat_repo.list_by_store(store_id, status)


def count_seats(store_id, status=None):
    return seat_repo.count_by_store(store_id, status)


def batch_add_seats(store_id, prefix, count, area_type=1, has_socket=1):
    """批量新增座位：prefix='A', count=20 就生成 A01 ~ A20。返回成功条数。"""
    get_store(store_id)
    prefix = (prefix or "").strip().upper()
    try:
        count = int(count)
    except (TypeError, ValueError):
        raise BizError("数量必须是整数")
    if not prefix:
        raise BizError("请填座位编号的前缀，比如 A")
    if not 1 <= count <= 200:
        raise BizError("一次最多新增 200 个座位")
    if area_type not in (1, 2, 3):
        raise BizError("区域类型只能是 1 普通区 / 2 安静区 / 3 靠窗区")
    if has_socket not in (0, 1):
        raise BizError("是否带插座只能是 1 或 0")

    seats = [(f"{prefix}{i:02d}", area_type, has_socket) for i in range(1, count + 1)]
    try:
        # 座位和门店的 seat_count 冗余字段要一起改，所以放在同一个事务里
        with uow() as cur:
            created = seat_repo.batch_create(store_id, seats, cur=cur)
            store_repo.sync_seat_count(store_id, cur=cur)
        return created
    except pymysql.err.IntegrityError:
        raise BizError(f"{prefix}01 起有编号重复了，换个前缀，或者先删掉已有座位")


def create_seat(store_id, seat_code, area_type=1, has_socket=1):
    """新增单个座位。"""
    get_store(store_id)
    seat_code = (seat_code or "").strip().upper()
    if not seat_code:
        raise BizError("座位编号不能为空")
    if area_type not in (1, 2, 3):
        raise BizError("区域类型只能是 1 普通区 / 2 安静区 / 3 靠窗区")
    if has_socket not in (0, 1):
        raise BizError("是否带插座只能是 1 或 0")
    try:
        with uow() as cur:
            seat_id = seat_repo.create(store_id, seat_code, area_type, has_socket, cur=cur)
            store_repo.sync_seat_count(store_id, cur=cur)
        return seat_id
    except pymysql.err.IntegrityError:
        raise BizError(f"这家门店已经有座位 {seat_code} 了")


def set_seat_status(seat_id, status):
    """座位状态：1 可用 / 0 维修中。"""
    if status not in (STATUS_ON, STATUS_OFF):
        raise BizError("座位状态只能是 1（可用）或 0（维修中）")
    if seat_repo.get_by_id(seat_id) is None:
        raise BizError("座位不存在")
    return seat_repo.update_status(seat_id, status)


def update_seat(seat_id, **fields):
    """局部改座位（seat_code / area_type / has_socket / status）。"""
    if seat_repo.get_by_id(seat_id) is None:
        raise BizError("座位不存在")
    try:
        return seat_repo.update(seat_id, **fields)
    except pymysql.err.IntegrityError:
        raise BizError("这家门店已经有同编号的座位了")


def find_available_seats(store_id, reserve_date, start_time, end_time):
    """某门店某时段还空着的座位（预约页直接用）。"""
    return seat_repo.list_available(store_id, reserve_date, start_time, end_time)
