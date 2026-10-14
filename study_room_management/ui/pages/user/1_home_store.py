"""用户端首页：门店列表 + 本店座位一览。

界面照 design-preview 的「门店与座位」页：页标题 + 副标题 → 当前门店面板（带营业状态标签）
→ 指标卡 → 座位一览面板（带维修中标签 + 表格）。

座位状态的口径（重要）：
    这里显示的是「此刻」的真实占用情况 —— 座位被预约了就要显示「使用中」，
    不能只读 seat.status（那只是维修中/可用）。
    判断依据是 reserve_date=今天 且 时段包含当前时刻 的有效预约，
    见 services/store_service.seat_overview()。
"""
import streamlit as st

from config import STATUS_ON
from services import order_service, store_service
from ui.components import area_name, on_off, sidebar_user, sync_time_status_once

sidebar_user()
# 先把「到点该进行中 / 时段过了该完成」的订单推一把，再看座位占用，
# 保证首页显示的占用情况和其他页面一致（60 秒内只同步一次）
sync_time_status_once()

stores = store_service.list_stores()
if not stores:
    st.warning("暂时没有营业中的门店，请联系管理员。")
    st.stop()


def _hm(value):
    """营业时间显示成 08:00（MySQL 的 TIME 取出来是 timedelta，str() 是 8:00:00）。"""
    if hasattr(value, "total_seconds"):          # timedelta
        total = int(value.total_seconds())
        return f"{total // 3600:02d}:{total % 3600 // 60:02d}"
    return value.strftime("%H:%M") if hasattr(value, "strftime") else str(value)[:5]


# 座位状态标签：使用中 / 未营业(维修或休息) 用暖色，空闲用绿色
_STATE_PILL = {
    "free": ("mint", "空闲"),
    "occupied": ("peach", "使用中"),
    "repairing": ("peach", "维修中"),
    "closed": ("muted", "未营业"),
}


st.markdown('<div class="page-title serif">门店与座位</div>', unsafe_allow_html=True)
st.markdown('<div class="page-sub">选择门店后，到「座位预约」页挑时段下单。</div>',
            unsafe_allow_html=True)

# —— 当前门店 ——
store_map = {f"{s['store_name']}（{s['address']}）": s for s in stores}
with st.container(key="panel_store"):
    st.markdown(
        '<div class="panel-head">'
        '<span class="panel-title"><span class="emoji">📍</span>当前门店</span>'
        '<span class="pill mint">营业中</span></div>', unsafe_allow_html=True)
    picked = st.selectbox("选择门店", list(store_map.keys()), label_visibility="collapsed")
store = store_map[picked]

# —— 此刻的占用情况：按「今天 + 当前时刻」查有效预约 ——
now_date, now_str, _ = order_service.current_slot()
seats = store_service.seat_overview(store["store_id"], now_date, now_str, now_str)

seat_total = int(store["seat_count"] or len(seats))
seat_free = sum(1 for s in seats if s["seat_state"] == "free")
seat_busy = sum(1 for s in seats if s["seat_state"] == "occupied")
repairing = sum(1 for s in seats if int(s["status"]) != STATUS_ON)

# 门店休息时段（现在不在营业时间内）就整体标成「未营业」
try:
    _open = order_service.to_minutes(store["open_time"])
    _close = order_service.to_minutes(store["close_time"])
except (TypeError, ValueError):
    _open, _close = 0, 24 * 60
if not (_open <= order_service.to_minutes(now_str) < _close):
    for s in seats:
        if s["seat_state"] == "free":
            s["seat_state"] = "closed"

# —— 指标卡 ——
st.markdown(
    '<div class="metrics">'
    f'<div class="metric"><div class="metric-label">营业时间</div>'
    f'<div class="metric-value">{_hm(store["open_time"])}<small>–</small>'
    f'{_hm(store["close_time"])}</div></div>'
    f'<div class="metric"><div class="metric-label">座位总数</div>'
    f'<div class="metric-value">{seat_total}<small>个</small></div></div>'
    f'<div class="metric"><div class="metric-label">使用中（此刻）</div>'
    f'<div class="metric-value">{seat_busy}<small>个</small></div></div>'
    f'<div class="metric"><div class="metric-label">空闲（此刻）</div>'
    f'<div class="metric-value">{seat_free}<small>个</small></div></div>'
    '</div>', unsafe_allow_html=True)

st.caption(f"座位状态按此刻（{now_date} {now_str[:5]}）的有效预约实时计算："
           "被预约的座位显示「使用中」，取消预约或时段过后自动回到「空闲」。")

# —— 座位一览 ——
pill_html = f'<span class="pill peach">{repairing} 个维修中</span>' if repairing else ""

with st.container(key="panel_seats"):
    st.markdown(
        '<div class="panel-head">'
        '<span class="panel-title"><span class="emoji">💺</span>座位一览</span>'
        f'{pill_html}</div>', unsafe_allow_html=True)
    if not seats:
        st.info("这家门店还没有录入座位。")
    else:
        rows = ""
        for s in seats:
            pill_class, state_text = _STATE_PILL.get(s["seat_state"], ("muted", "未知"))
            rows += (f'<tr><td class="code">{s["seat_code"]}</td>'
                     f'<td>{area_name(s["area_type"])}</td>'
                     f'<td>{on_off(s["has_socket"], "有", "无")}</td>'
                     f'<td><span class="pill {pill_class}">{state_text}</span></td></tr>')
        st.markdown(
            '<div class="table-wrap"><table><thead><tr>'
            '<th>座位编号</th><th>区域</th><th>插座</th><th>此刻状态</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
