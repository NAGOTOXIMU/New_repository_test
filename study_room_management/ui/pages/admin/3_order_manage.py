"""管理端 · 订单管理。

功能：预约订单与充值订单列表（按门店/状态/日期区间筛选）、推进预约状态、退款。
注意：状态推进口径见 docs/DESIGN.md 的 A1（暂定由管理员手工操作）。
"""
import streamlit as st

from config import (ORDER_DONE, ORDER_ONGOING, ORDER_PENDING, ORDER_STATUS_NAMES,
                    PAY_PAID, PAY_STATUS_NAMES)
from services import order_service, recharge_service, store_service
from services.exceptions import BizError
from ui.components import flash, order_status_name, pay_status_name, require_role, sidebar_user

require_role("admin")
sidebar_user()
flash()

admin = st.session_state.get("user") or {}
# 普通运营员只看自己门店；超管（store_id 为 NULL）看全部
locked_store_id = admin.get("store_id")

st.title("订单管理")
if locked_store_id:
    st.caption(f"你负责的门店 ID：{locked_store_id}（只能看到本店订单）")
else:
    st.caption("你是超级管理员，可以查看全部门店订单。")

tab_res, tab_recharge = st.tabs(["预约订单", "充值订单"])

# 预约订单
with tab_res:
    if st.button("把过期未使用的预约标记为「已过期」并释放时段"):
        try:
            n = order_service.expire_overdue()
            flash(f"已处理 {n} 条过期预约")
            st.rerun()
        except BizError as e:
            st.error(str(e))

    c1, c2, c3 = st.columns(3)
    with c1:
        if locked_store_id:
            store_id = locked_store_id
            st.text_input("门店", value=f"ID {locked_store_id}", disabled=True)
        else:
            stores = store_service.list_stores_paged(page=1, page_size=100)[0]
            smap = {"全部门店": None}
            smap.update({s["store_name"]: s["store_id"] for s in stores})
            picked_store = st.selectbox("门店", list(smap.keys()))
            store_id = smap[picked_store]
    with c2:
        smap = {"全部状态": None}
        smap.update({v: k for k, v in ORDER_STATUS_NAMES.items()})
        picked_status = st.selectbox("订单状态", list(smap.keys()))
        order_status = smap[picked_status]
    with c3:
        page = st.number_input("页码", min_value=1, value=1, step=1, key="res_page")

    d1, d2 = st.columns(2)
    with d1:
        res_start = st.date_input("预约日期从", value=None, key="res_start")
    with d2:
        res_end = st.date_input("预约日期到", value=None, key="res_end")

    rows, total = order_service.list_orders(
        store_id, order_status, start_date=res_start, end_date=res_end,
        page=page, page_size=10)
    st.caption(f"共 {total} 条，第 {page} 页（日期筛的是预约日期 reserve_date）")

    if not rows:
        st.info("没有符合条件的预约订单。")
    else:
        st.dataframe(
            [{
                "单号": r["order_no"],
                "日期": r["reserve_date"],
                "时段": f"{str(r['start_time'])[:5]}~{str(r['end_time'])[:5]}",
                "座位": r["seat_code"],
                "门店": r["store_name"],
                "用户ID": r["user_id"],
                "时长(分)": r["duration"],
                "扣费": float(r["amount"]),
                "状态": order_status_name(r["order_status"]),
                "用卡": r["card_no"] or "—",
            } for r in rows],
            width="stretch", hide_index=True,
        )

        st.divider()
        st.subheader("推进预约状态")
        rmap = {f"{r['order_no']}（{order_status_name(r['order_status'])}）": r for r in rows}
        picked = st.selectbox("选择订单", list(rmap.keys()), key="res_pick")
        target = rmap[picked]
        cur_status = int(target["order_status"])

        b1, b2 = st.columns(2)
        with b1:
            if st.button("签到（待使用 → 进行中）",
                         disabled=cur_status != ORDER_PENDING):
                try:
                    order_service.check_in(target["order_id"])
                    flash("已签到")
                    st.rerun()
                except BizError as e:
                    st.error(str(e))
        with b2:
            if st.button("结束（进行中 → 已完成）",
                         disabled=cur_status != ORDER_ONGOING):
                try:
                    order_service.finish(target["order_id"])
                    flash("已完成")
                    st.rerun()
                except BizError as e:
                    st.error(str(e))

# 充值订单
with tab_recharge:
    c1, c2 = st.columns(2)
    with c1:
        pmap = {"全部状态": None}
        pmap.update({v: k for k, v in PAY_STATUS_NAMES.items()})
        picked_pay = st.selectbox("支付状态", list(pmap.keys()))
        pay_status = pmap[picked_pay]
    with c2:
        r_page = st.number_input("页码 ", min_value=1, value=1, step=1, key="rc_page")

    d1, d2 = st.columns(2)
    with d1:
        rc_start = st.date_input("下单日期从", value=None, key="rc_start")
    with d2:
        rc_end = st.date_input("下单日期到", value=None, key="rc_end")

    rows, total = recharge_service.list_all(
        pay_status, start_date=rc_start, end_date=rc_end, page=r_page, page_size=10)
    st.caption(f"共 {total} 条，第 {r_page} 页（日期筛的是下单时间 create_time）")

    if not rows:
        st.info("没有符合条件的充值订单。")
    else:
        st.dataframe(
            [{
                "单号": r["order_no"],
                "用户手机号": r["phone"],
                "昵称": r["nickname"],
                "卡种": r["card_name"],
                "金额": float(r["amount"]),
                "支付状态": pay_status_name(r["pay_status"]),
                "支付时间": r["pay_time"],
                "生成卡号": r["card_no"] or "—",
            } for r in rows],
            width="stretch", hide_index=True,
        )

        st.divider()
        st.subheader("退款")
        st.caption("只有「已支付」且卡内权益尚未被消费的订单可以原路退回。")
        rmap = {f"{r['order_no']}（{pay_status_name(r['pay_status'])}，"
                f"{float(r['amount']):.2f} 元）": r for r in rows
                if int(r["pay_status"]) == PAY_PAID}
        if not rmap:
            st.info("当前页没有可退款的订单。")
        else:
            picked = st.selectbox("选择订单", list(rmap.keys()), key="rc_pick")
            target = rmap[picked]
            if st.button("确认退款"):
                try:
                    result = recharge_service.refund_order(target["order_no"])
                    flash(f"已退款 {result['refund']:.2f} 元")
                    st.rerun()
                except BizError as e:
                    st.error(str(e))
