"""统计与报表（只读），给数据看板用。

返回的都是普通数据（dict / list），画图交给 ui 层。
"""
from datetime import date, datetime, timedelta

from repository import recharge_repo, reservation_repo, seat_repo, store_repo, user_repo


def _days_ago(days):
    return str(date.today() - timedelta(days=days)), str(date.today())


def _hours_between(open_time, close_time):
    """营业时长（小时）。"""
    o = datetime.strptime(str(open_time), "%H:%M:%S")
    c = datetime.strptime(str(close_time), "%H:%M:%S")
    return max((c - o).seconds // 3600, 1)


def overview(days=30):
    """看板顶部的一组汇总数字。"""
    start, end = _days_ago(days)
    stores = store_repo.list_all()
    return {
        "门店数": len(stores),
        "座位数": sum(seat_repo.count_by_store(s["store_id"]) for s in stores),
        "用户数": user_repo.count(),
        "充值金额": float(recharge_repo.sum_amount(start, end)),
        "预约总数": reservation_repo.count_between(start, end),
        "待使用": reservation_repo.count_by_status("待使用"),
        "已完成": reservation_repo.count_by_status("已完成"),
        "已取消": reservation_repo.count_by_status("已取消"),
    }


def revenue_by_day(days=30):
    """近 N 天每天的营收，画折线图用。"""
    start, end = _days_ago(days)
    return recharge_repo.revenue_by_day(start, end)


def card_type_distribution():
    """各卡种卖了多少张，画饼图用。"""
    return recharge_repo.count_by_card_type()


def member_growth(days=30):
    """近 N 天每天新增会员。"""
    return user_repo.count_new_by_day(days)


def hot_hours(store_id=None, days=30):
    """热门预约时段（按开始的小时统计）。"""
    return reservation_repo.count_by_hour(store_id, days)


def seat_utilization(store_id, days=30):
    """座位利用率：已预约的时段数 ÷（可用座位数 × 天数 × 营业小时数）。"""
    store = store_repo.get_by_id(store_id)
    if store is None:
        return 0.0
    seats = seat_repo.count_by_store(store_id, status="可用")
    if seats == 0:
        return 0.0
    capacity = seats * max(days, 1) * _hours_between(store["open_time"], store["close_time"])
    start, end = _days_ago(days)
    booked = reservation_repo.count_between(start, end, store_id)
    return round(booked / capacity, 4) if capacity else 0.0
