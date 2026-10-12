"""用户端 · 我的订单。

列出预约记录并支持取消（调 order_service.cancel，会退回权益并释放时段）。
注意：列表服务端分页，不把整表拉进 st.dataframe。
"""
import streamlit as st

from config import ORDER_CANCELLABLE, ORDER_STATUS_NAMES
from services import order_service
from services.exceptions import BizError
from ui.components import area_name, sidebar_user

user = sidebar_user()
if user.get("role") != "user":
    st.error("这页是用户端页面，请用用户账号登录。")
    st.stop()

user_id = user["user_id"]
st.title("我的订单")

PAGE_SIZE = 10
page = st.number_input("页码", min_value=1, value=1, step=1)

rows, total = order_service.list_my_orders(user_id, page=page, page_size=PAGE_SIZE)
st.caption(f"共 {total} 条记录，第 {page} 页（每页 {PAGE_SIZE} 条）")

if not rows:
    st.info("还没有预约记录，去「座位预约」下第一单吧。")
    st.stop()

st.dataframe(
    [{
        "单号": r["order_no"],
        "日期": r["reserve_date"],
        "时段": f"{str(r['start_time'])[:5]}~{str(r['end_time'])[:5]}",
        "座位": r["seat_code"],
        "区域": area_name(r["area_type"]),
        "门店": r["store_name"],
        "时长(分)": r["duration"],
        "扣费": float(r["amount"]),
        "状态": ORDER_STATUS_NAMES.get(int(r["order_status"]), r["order_status"]),
        "用卡": r["card_no"] or "—",
    } for r in rows],
    width="stretch",
    hide_index=True,
)

st.divider()
st.subheader("取消预约")

cancellable = [r for r in rows if int(r["order_status"]) in ORDER_CANCELLABLE]
if not cancellable:
    st.info("当前页没有可取消的预约（只有「待使用」「进行中」可以取消）。")
    st.stop()

options = {
    f"{r['order_no']} ｜ {r['reserve_date']} "
    f"{str(r['start_time'])[:5]}~{str(r['end_time'])[:5]} ｜ 座位 {r['seat_code']}": r
    for r in cancellable
}
picked = st.selectbox("选择要取消的预约", list(options.keys()))
target = options[picked]

if st.button("确认取消", type="secondary"):
    try:
        result = order_service.cancel(target["order_id"], user_id)
        st.success(f"已取消，单号 {target['order_no']}，退回权益 {result['refund']:.2f} 元")
        st.caption("时段已释放，可以重新预约同一时段。")
        st.rerun()
    except BizError as e:
        st.error(str(e))
