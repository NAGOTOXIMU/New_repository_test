"""用户端 · 座位预约（核心页面）。

选门店 → 选日期时段 → 选座位 → 选卡 → 提交，调 services/order_service.reserve()。
注意：页面上显示的「可用座位」只是展示，并发安全靠数据库唯一索引 uk_seat_slot 保证。
"""
from datetime import date, time, timedelta

import streamlit as st

from config import MAX_RESERVE_MINUTES
from services import order_service, recharge_service, store_service
from services.exceptions import BizError
from ui.components import area_name, on_off, sidebar_user

user = sidebar_user()
if user.get("role") != "user":
    st.error("这页是用户端页面，请用用户账号登录。")
    st.stop()

user_id = user["user_id"]

st.title("座位预约")

stores = store_service.list_stores()
if not stores:
    st.warning("暂时没有营业中的门店。")
    st.stop()

store_map = {s["store_name"]: s for s in stores}
picked_name = st.selectbox("选择门店", list(store_map.keys()))
store = store_map[picked_name]
store_id = store["store_id"]

col1, col2, col3 = st.columns(3)
with col1:
    reserve_date = st.date_input("预约日期", value=date.today() + timedelta(days=1),
                                 min_value=date.today())
with col2:
    start_time = st.time_input("开始时间", value=time(9, 0), step=timedelta(hours=1))
with col3:
    hours = st.selectbox("时长（小时）", [1, 2, 3, 4, 6, 8], index=0)

duration = int(hours) * 60
start_str = start_time.strftime("%H:%M:%S")
end_str = order_service.make_end_time(start_str, duration)

if order_service.to_minutes(end_str) <= order_service.to_minutes(start_str):
    st.error("结束时间不能跨天，请把开始时间提前或缩短时长。")
    st.stop()

st.caption(f"时段：{reserve_date} {start_str[:5]} ~ {end_str[:5]}（{duration} 分钟，"
           f"最长 {MAX_RESERVE_MINUTES // 60} 小时）")

# —— 选座位 ——
available = store_service.find_available_seats(store_id, reserve_date, start_str, end_str)
if not available:
    st.warning("这个时段没有空闲座位了，换个时段试试。")
    st.stop()

seat_map = {}
for s in available:
    label = (f"{s['seat_code']}（{area_name(s['area_type'])}，"
             f"{on_off(s['has_socket'], '带插座', '无插座')}）")
    seat_map[label] = s
picked_seat = st.selectbox(f"空闲座位（共 {len(available)} 个）", list(seat_map.keys()))
seat = seat_map[picked_seat]

# —— 选卡 ——
cards = recharge_service.list_my_active_cards(user_id)
if not cards:
    st.warning("你还没有可用的会员卡，请先到「会员充值」页购卡。")
    st.stop()

card_map = {}
for c in cards:
    label = (f"{c['card_name']} ｜ 卡号 {c['card_no']} ｜ "
             f"余额 {c['balance']} 元 / 剩余 {c['remaining_times']} 次 / "
             f"剩余 {c['remaining_minutes']} 分钟")
    card_map[label] = c
picked_card = st.selectbox("使用哪张卡结算", list(card_map.keys()))
card = card_map[picked_card]

estimate = order_service.estimate_amount(card, duration)
if estimate > 0:
    st.info(f"预估扣费：{estimate:.2f} 元（储值卡按小时单价计算）")
else:
    st.info("本次不扣余额，按卡种扣次数或时长。")

if st.button("确认预约", type="primary"):
    try:
        result = order_service.reserve(
            user_id=user_id, seat_id=seat["seat_id"], reserve_date=reserve_date,
            start_time=start_str, duration=duration, card_id=card["card_id"],
            store_id=store_id,
        )
        st.success(
            f"预约成功！单号 {result['order_no']}，座位 {result['seat_code']}，"
            f"{result['start_time'][:5]}~{result['end_time'][:5]}，"
            f"扣费 {result['amount']:.2f} 元"
        )
        st.caption("卡内资产与余额汇总已在同一事务里更新，刷新页面即可看到最新数值。")
    except BizError as e:
        st.error(str(e))
