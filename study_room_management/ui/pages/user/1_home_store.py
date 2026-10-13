"""用户端首页：门店列表 + 本店座位一览。"""
import streamlit as st

from config import STATUS_ON
from services import store_service
from ui.components import area_name, on_off, sidebar_user

sidebar_user()

st.title("门店与座位")

stores = store_service.list_stores()
if not stores:
    st.warning("暂时没有营业中的门店，请联系管理员。")
    st.stop()

store_map = {f"{s['store_name']}（{s['address']}）": s for s in stores}
picked = st.selectbox("选择门店", list(store_map.keys()))
store = store_map[picked]

col1, col2, col3 = st.columns(3)
def _hm(value):
    """营业时间显示成 08:00（MySQL 的 TIME 取出来是 timedelta，str() 是 8:00:00）。"""
    if hasattr(value, "total_seconds"):          # timedelta
        total = int(value.total_seconds())
        return f"{total // 3600:02d}:{total % 3600 // 60:02d}"
    return value.strftime("%H:%M") if hasattr(value, "strftime") else str(value)[:5]


col1.metric("营业时间", f"{_hm(store['open_time'])} - {_hm(store['close_time'])}")
col2.metric("座位总数", store["seat_count"])
col3.metric("可用座位", store_service.count_seats(store["store_id"], status=STATUS_ON))

st.divider()
st.subheader("座位一览")

seats = store_service.list_seats(store["store_id"])
if not seats:
    st.info("这家门店还没有录入座位。")
else:
    st.dataframe(
        [{
            "座位编号": s["seat_code"],
            "区域": area_name(s["area_type"]),
            "带插座": on_off(s["has_socket"], "是", "否"),
            "状态": on_off(s["status"], "可用", "维修中"),
        } for s in seats],
        width="stretch",
        hide_index=True,
    )

st.caption("选好门店后，到「座位预约」页挑时段下单。")
