"""管理端 · 用户管理。

功能：用户列表、查看持卡与消费记录、冻结 / 解冻账号。
"""
import streamlit as st

from config import MEMBER_LEVEL_NAMES, STATUS_OFF, STATUS_ON
from services import user_service
from services.exceptions import BizError
from ui.components import order_status_name, pay_status_name, require_role, sidebar_user

require_role("admin")
sidebar_user()

st.title("用户管理")

c1, c2 = st.columns([2, 1])
with c1:
    keyword = st.text_input("搜索（手机号 / 昵称）")
with c2:
    page = st.number_input("页码", min_value=1, value=1, step=1)

rows, total = user_service.list_users_paged(keyword or None, page=page, page_size=10)
st.caption(f"共 {total} 位用户，第 {page} 页")

if not rows:
    st.info("没有符合条件的用户。")
    st.stop()

st.dataframe(
    [{
        "ID": u["user_id"],
        "手机号": u["phone"],
        "昵称": u["nickname"],
        "余额(元)": float(u["balance"]),
        "剩余时长(小时)": u["remaining_hours"],
        "会员等级": MEMBER_LEVEL_NAMES.get(int(u["member_level"]), "普通用户"),
        "到期时间": u["expire_time"],
        "注册时间": u["create_time"],
        "状态": "正常" if int(u["status"]) == STATUS_ON else "已禁用",
    } for u in rows],
    width="stretch", hide_index=True,
)

st.divider()
umap = {f"{u['user_id']} - {u['nickname']}（{u['phone']}）": u for u in rows}
picked = st.selectbox("选择用户", list(umap.keys()))
target = umap[picked]
user_id = target["user_id"]

st.subheader("账号状态")
new_status = st.radio(
    "状态", [STATUS_ON, STATUS_OFF],
    index=0 if int(target["status"]) == STATUS_ON else 1,
    format_func=lambda v: "正常" if v == STATUS_ON else "禁用",
    horizontal=True,
)
if st.button("保存账号状态"):
    try:
        user_service.set_status(user_id, new_status)
        st.success("已更新")
        st.rerun()
    except BizError as e:
        st.error(str(e))

st.divider()
# 用户身上挂了持卡/预约/充值三张表，取数逻辑收在 user_service.get_user_detail() 里
detail = user_service.get_user_detail(user_id)

col1, col2 = st.columns(2)

with col1:
    st.subheader("持卡情况")
    cards = detail["cards"]
    if not cards:
        st.info("该用户还没有卡。")
    else:
        st.dataframe(
            [{
                "卡号": c["card_no"],
                "卡种": c["card_name"],
                "余额(元)": float(c["balance"]),
                "剩余次数": c["remaining_times"],
                "剩余分钟": c["remaining_minutes"],
                "到期日": c["expire_at"],
                "状态": "正常" if int(c["status"]) == 1 else "已冻结",
            } for c in cards],
            width="stretch", hide_index=True,
        )

with col2:
    st.subheader("最近预约记录")
    orders = detail["orders"]
    if not orders:
        st.info("该用户还没有预约记录。")
    else:
        st.caption(f"共 {detail['order_total']} 条")
        st.dataframe(
            [{
                "单号": r["order_no"],
                "日期": r["reserve_date"],
                "座位": r["seat_code"],
                "门店": r["store_name"],
                "扣费": float(r["amount"]),
                "状态": order_status_name(r["order_status"]),
            } for r in orders],
            width="stretch", hide_index=True,
        )

# 充值记录单独一行放，避免列太挤
st.subheader("充值记录")
records = detail["recharges"]
if not records:
    st.info("该用户还没有充值记录。")
else:
    st.caption(f"共 {detail['recharge_total']} 条")
    st.dataframe(
        [{
            "单号": r["order_no"],
            "卡种": r["card_name"],
            "金额(元)": float(r["amount"]),
            "支付状态": pay_status_name(r["pay_status"]),
            "支付时间": r["pay_time"],
        } for r in records],
        width="stretch", hide_index=True,
    )
