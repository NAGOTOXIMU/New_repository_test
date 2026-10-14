"""用户端首页：门店列表 + 本店座位一览。

界面照 design-preview 的「门店与座位」页：页标题 + 副标题 → 当前门店面板（带营业状态标签）
→ 指标卡 → 座位一览面板（带维修中标签 + 表格）。
"""
import streamlit as st

from config import STATUS_ON
from services import store_service
from ui.components import area_name, on_off, sidebar_user

sidebar_user()

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

seat_total = store["seat_count"]
seat_free = store_service.count_seats(store["store_id"], status=STATUS_ON)

# —— 指标卡 ——
st.markdown(
    '<div class="metrics">'
    f'<div class="metric"><div class="metric-label">营业时间</div>'
    f'<div class="metric-value">{_hm(store["open_time"])}<small>–</small>'
    f'{_hm(store["close_time"])}</div></div>'
    f'<div class="metric"><div class="metric-label">座位总数</div>'
    f'<div class="metric-value">{seat_total}<small>个</small></div></div>'
    f'<div class="metric"><div class="metric-label">可用座位</div>'
    f'<div class="metric-value">{seat_free}<small>个</small></div></div>'
    '</div>', unsafe_allow_html=True)

# —— 座位一览 ——
seats = store_service.list_seats(store["store_id"])
repairing = sum(1 for s in seats if int(s["status"]) != STATUS_ON)
pill_html = f'<span class="pill peach">{repairing} 个维修中</span>' if repairing else ""

with st.container(key="panel_seats"):
    st.markdown(
        '<div class="panel-head">'
        '<span class="panel-title"><span class="emoji">💺</span>座位一览</span>'
        f'{pill_html}</div>', unsafe_allow_html=True)
    if not seats:
        st.info("这家门店还没有录入座位。")
    else:
        rows = "".join(
            f'<tr><td class="code">{s["seat_code"]}</td>'
            f'<td>{area_name(s["area_type"])}</td>'
            f'<td>{on_off(s["has_socket"], "有", "无")}</td>'
            f'<td><span class="pill {"mint" if int(s["status"]) == STATUS_ON else "peach"}">'
            f'{on_off(s["status"], "可用", "维修中")}</span></td></tr>'
            for s in seats)
        st.markdown(
            '<div class="table-wrap"><table><thead><tr>'
            '<th>座位编号</th><th>区域</th><th>插座</th><th>状态</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
