"""管理端 · 订单管理。

第一行必须调用 ui.components.require_role("admin")。
功能：预约订单与充值订单列表（按门店/状态/日期筛选），推进订单状态。
注意：状态由谁推进还没拍板，见 docs/DESIGN.md 的 A1。这里按「管理员手工签到」实现。
"""
from datetime import date

import pandas as pd
import streamlit as st

from services import order_service, recharge_service, store_service
from services.exceptions import BizError
from ui.components import require_role

require_role("admin")

st.title("订单管理")

RES_STATUSES = ["待使用", "使用中", "已完成", "已取消"]
RC_STATUSES = ["待支付", "已支付", "已取消", "已退款"]


def _store_options():
    """返回 {展示名: store_id}，含「全部」。"""
    rows, _ = store_service.list_stores_paged(None, 1, 1000)
    opts = {"全部门店": None}
    for s in rows:
        opts[f"{s['store_id']} · {s['name']}"] = s["store_id"]
    return opts


def _pager(total, page, page_size, key_prefix):
    total_pages = max(1, (total + page_size - 1) // page_size)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("上一页", disabled=(page <= 1), key=f"{key_prefix}_prev"):
            st.session_state[f"{key_prefix}_page"] = page - 1
            st.rerun()
    with c2:
        st.caption(f"共 {total} 条，第 {page} / {total_pages} 页")
    with c3:
        if st.button("下一页", disabled=(page >= total_pages),
                     key=f"{key_prefix}_next"):
            st.session_state[f"{key_prefix}_page"] = page + 1
            st.rerun()


tab_res, tab_rc = st.tabs(["预约订单", "充值订单"])


# ═══════════════════════════════════════════════════════════════
# 一、预约订单
# ═══════════════════════════════════════════════════════════════
with tab_res:
    st.subheader("预约订单")

    # —— 筛选 ——
    fcol1, fcol2 = st.columns(2)
    with fcol1:
        store_opts = _store_options()
        store_pick = st.selectbox("门店", list(store_opts.keys()), key="res_store")
        res_store_id = store_opts[store_pick]
    with fcol2:
        res_status = st.selectbox(
            "状态", ["全部"] + RES_STATUSES, key="res_status")
        res_status_val = None if res_status == "全部" else res_status

    dcol1, dcol2 = st.columns(2)
    with dcol1:
        res_start = st.date_input("开始日期", value=None, key="res_start")
    with dcol2:
        res_end = st.date_input("结束日期", value=None, key="res_end")

    res_page = st.session_state.get("res_page", 1)
    res_page_size = st.selectbox("每页", [10, 20, 50], key="res_page_size")

    rows, total = order_service.list_orders(
        store_id=res_store_id, status=res_status_val,
        start_date=res_start, end_date=res_end,
        page=res_page, page_size=res_page_size,
    )

    if rows:
        df = pd.DataFrame(rows).rename(columns={
            "reservation_id": "ID",
            "order_no": "预约单号",
            "store_name": "门店",
            "seat_no": "座位号",
            "zone": "区域",
            "reserve_date": "预约日期",
            "start_time": "开始",
            "end_time": "结束",
            "hours": "时长(h)",
            "amount": "金额(元)",
            "status": "状态",
        })
        # pymysql 把 TIME 列返回成 timedelta，转成 HH:MM:SS 方便阅读
        for col in ("开始", "结束"):
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda v: str(v) if v is not None else "")
        keep = ["ID", "预约单号", "门店", "座位号", "区域",
                "预约日期", "开始", "结束", "时长(h)", "金额(元)", "状态"]
        st.dataframe(df[[c for c in keep if c in df.columns]],
                     use_container_width=True, hide_index=True)
    else:
        st.info("没有符合条件的预约订单")

    _pager(total, res_page, res_page_size, "res")

    # —— 推进状态 ——
    st.divider()
    st.subheader("推进订单状态")
    if not rows:
        st.info("当前筛选结果中没有可操作的订单")
    else:
        order_opts = {
            f"{r['order_no']}（{r['store_name']} {r['seat_no']} "
            f"{r['reserve_date']} {r['status']}）": r for r in rows
        }
        res_pick = st.selectbox(
            "选择订单", list(order_opts.keys()), key="res_pick")
        res = order_opts[res_pick]
        st.write(f"当前状态：**{res['status']}**")

        acol1, acol2 = st.columns(2)
        with acol1:
            if st.button("签到（待使用 → 使用中）",
                         disabled=(res["status"] != "待使用"),
                         use_container_width=True, key="res_checkin"):
                try:
                    order_service.check_in(res["reservation_id"])
                    st.success("已签到，状态变为「使用中」")
                    st.rerun()
                except BizError as e:
                    st.error(str(e))
        with acol2:
            if st.button("结束（使用中 → 已完成）",
                         disabled=(res["status"] != "使用中"),
                         use_container_width=True, key="res_finish"):
                try:
                    order_service.finish(res["reservation_id"])
                    st.success("已结束，状态变为「已完成」")
                    st.rerun()
                except BizError as e:
                    st.error(str(e))


# ═══════════════════════════════════════════════════════════════
# 二、充值订单
# ═══════════════════════════════════════════════════════════════
with tab_rc:
    st.subheader("充值订单")

    fcol1, fcol2 = st.columns(2)
    with fcol1:
        rc_status = st.selectbox(
            "状态", ["全部"] + RC_STATUSES, key="rc_status")
        rc_status_val = None if rc_status == "全部" else rc_status
    with fcol2:
        rc_page_size = st.selectbox("每页", [10, 20, 50], key="rc_page_size")

    dcol1, dcol2 = st.columns(2)
    with dcol1:
        rc_start = st.date_input("开始日期", value=None, key="rc_start")
    with dcol2:
        rc_end = st.date_input("结束日期", value=None, key="rc_end")

    rc_page = st.session_state.get("rc_page", 1)
    rows, total = recharge_service.list_all(
        status=rc_status_val, start_date=rc_start, end_date=rc_end,
        page=rc_page, page_size=rc_page_size,
    )

    if rows:
        df = pd.DataFrame(rows).rename(columns={
            "recharge_id": "ID",
            "order_no": "充值单号",
            "card_type_name": "卡种",
            "card_type_kind": "类型",
            "amount": "金额(元)",
            "pay_method": "支付方式",
            "status": "状态",
            "paid_at": "支付时间",
            "created_at": "下单时间",
        })
        keep = ["ID", "充值单号", "卡种", "类型", "金额(元)",
                "支付方式", "状态", "下单时间", "支付时间"]
        st.dataframe(df[[c for c in keep if c in df.columns]],
                     use_container_width=True, hide_index=True)
    else:
        st.info("没有符合条件的充值订单")

    _pager(total, rc_page, rc_page_size, "rc")

    st.caption("充值订单的状态由用户支付/取消触发，管理端暂不提供手工改状态。")
