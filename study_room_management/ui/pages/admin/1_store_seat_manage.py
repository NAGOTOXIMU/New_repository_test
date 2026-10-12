"""管理端 · 门店与座位管理。

第一行必须调用 ui.components.require_role("admin")。
功能：门店信息维护、批量新增座位、座位状态（可用 / 维修 / 停用）。
"""
from datetime import time as dtime, timedelta

import pandas as pd
import streamlit as st

from services import store_service
from services.exceptions import BizError
from ui.components import require_role

require_role("admin")


def _to_time(val):
    """pymysql 把 TIME 列返回成 timedelta，这里转回 datetime.time 给 st.time_input 用。"""
    if isinstance(val, timedelta):
        s = int(val.total_seconds())
        return dtime(s // 3600, (s % 3600) // 60, s % 60)
    return val

st.title("门店与座位管理")

tab_store, tab_seat = st.tabs(["门店管理", "座位管理"])


# ═══════════════════════════════════════════════════════════════
# 一、门店管理：列表（搜索 + 分页）、新增、编辑、营业/停业切换
# ═══════════════════════════════════════════════════════════════
with tab_store:
    st.subheader("门店列表")

    col_kw, col_ps = st.columns([3, 1])
    with col_kw:
        keyword = st.text_input("搜索门店名 / 地址", key="store_keyword")
    with col_ps:
        page_size = st.selectbox("每页", [10, 20, 50], key="store_page_size")

    page = st.session_state.get("store_page", 1)
    stores, total = store_service.list_stores_paged(keyword, page, page_size)

    if stores:
        df = pd.DataFrame(stores).rename(columns={
            "store_id": "ID",
            "name": "门店名",
            "address": "地址",
            "phone": "电话",
            "open_time": "开门时间",
            "close_time": "关门时间",
            "status": "状态",
        })
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无门店")

    # —— 分页 ——
    total_pages = max(1, (total + page_size - 1) // page_size)
    pcol1, pcol2, pcol3 = st.columns([1, 2, 1])
    with pcol1:
        if st.button("上一页", disabled=(page <= 1), key="store_prev"):
            st.session_state["store_page"] = page - 1
            st.rerun()
    with pcol2:
        st.caption(f"共 {total} 条，第 {page} / {total_pages} 页")
    with pcol3:
        if st.button("下一页", disabled=(page >= total_pages), key="store_next"):
            st.session_state["store_page"] = page + 1
            st.rerun()

    st.divider()

    # —— 新增门店 ——
    with st.expander("➕ 新增门店", expanded=False):
        with st.form("create_store_form"):
            c_name = st.text_input("门店名 *")
            c_address = st.text_input("地址 *")
            c_phone = st.text_input("联系电话")
            ccol1, ccol2 = st.columns(2)
            with ccol1:
                c_open = st.time_input("开门时间", value=dtime(8, 0))
            with ccol2:
                c_close = st.time_input("关门时间", value=dtime(22, 0))
            c_submit = st.form_submit_button("创建", use_container_width=True)

        if c_submit:
            try:
                sid = store_service.create_store(
                    c_name, c_address, c_phone or None,
                    c_open.strftime("%H:%M:%S"),
                    c_close.strftime("%H:%M:%S"),
                )
                st.success(f"门店创建成功，ID = {sid}")
                st.rerun()
            except BizError as e:
                st.error(str(e))

    # —— 编辑 / 状态切换 ——
    st.subheader("编辑门店")
    all_stores, _ = store_service.list_stores_paged(None, 1, 1000)
    if not all_stores:
        st.info("请先新增门店")
    else:
        options = {f"{s['store_id']} · {s['name']}": s for s in all_stores}
        pick = st.selectbox("选择要编辑的门店", list(options.keys()), key="edit_store")
        store = options[pick]

        with st.form("edit_store_form"):
            e_name = st.text_input("门店名", value=store["name"])
            e_address = st.text_input("地址", value=store["address"])
            e_phone = st.text_input("电话", value=store["phone"] or "")
            ecol1, ecol2 = st.columns(2)
            with ecol1:
                e_open = st.time_input("开门时间", value=_to_time(store["open_time"]))
            with ecol2:
                e_close = st.time_input("关门时间", value=_to_time(store["close_time"]))
            e_submit = st.form_submit_button("保存修改", use_container_width=True)

        if e_submit:
            try:
                store_service.update_store(
                    store["store_id"],
                    name=e_name,
                    address=e_address,
                    phone=e_phone or None,
                    open_time=e_open.strftime("%H:%M:%S"),
                    close_time=e_close.strftime("%H:%M:%S"),
                )
                st.success("门店信息已更新")
                st.rerun()
            except BizError as e:
                st.error(str(e))

        scol1, scol2 = st.columns(2)
        with scol1:
            if st.button("设为营业", disabled=(store["status"] == "营业"),
                         use_container_width=True, key="store_open"):
                try:
                    store_service.set_store_status(store["store_id"], "营业")
                    st.success("已设为营业")
                    st.rerun()
                except BizError as e:
                    st.error(str(e))
        with scol2:
            if st.button("设为停业", disabled=(store["status"] == "停业"),
                         use_container_width=True, key="store_close"):
                try:
                    store_service.set_store_status(store["store_id"], "停业")
                    st.success("已设为停业")
                    st.rerun()
                except BizError as e:
                    st.error(str(e))


# ═══════════════════════════════════════════════════════════════
# 二、座位管理：选门店、统计、列表（状态筛选）、批量新增、状态修改
# ═══════════════════════════════════════════════════════════════
with tab_seat:
    st.subheader("座位管理")

    all_stores, _ = store_service.list_stores_paged(None, 1, 1000)
    if not all_stores:
        st.warning("请先在「门店管理」中创建门店")
    else:
        s_options = {f"{s['store_id']} · {s['name']}": s for s in all_stores}
        s_pick = st.selectbox("选择门店", list(s_options.keys()), key="seat_store")
        store = s_options[s_pick]
        sid = store["store_id"]

        # —— 统计 ——
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("总座位", store_service.count_seats(sid))
        m2.metric("可用", store_service.count_seats(sid, "可用"))
        m3.metric("维修", store_service.count_seats(sid, "维修"))
        m4.metric("停用", store_service.count_seats(sid, "停用"))

        # —— 列表 ——
        status_filter = st.selectbox(
            "状态筛选", ["全部", "可用", "维修", "停用"], key="seat_status_filter"
        )
        filter_status = None if status_filter == "全部" else status_filter
        seats = store_service.list_seats(sid, filter_status)

        if seats:
            sdf = pd.DataFrame(seats).rename(columns={
                "seat_id": "ID",
                "store_id": "门店ID",
                "seat_no": "座位号",
                "zone": "区域",
                "price_per_hour": "单价(元/小时)",
                "status": "状态",
            })
            st.dataframe(sdf, use_container_width=True, hide_index=True)
        else:
            st.info("该门店暂无符合条件的座位")

        # —— 批量新增 ——
        with st.expander("➕ 批量新增座位", expanded=False):
            with st.form("batch_seat_form"):
                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    prefix = st.text_input("编号前缀", value="A", help="如 A，将生成 A01、A02…")
                with bcol2:
                    count = st.number_input("数量", min_value=1, max_value=200, value=10)
                zone = st.text_input("区域（可选）", help="如 静音区 / 讨论区")
                price = st.number_input("单价（元/小时）", min_value=0.0, value=0.0, step=0.5)
                b_submit = st.form_submit_button("批量新增", use_container_width=True)

            if b_submit:
                try:
                    n = store_service.batch_add_seats(
                        sid, prefix, count, zone or None, float(price)
                    )
                    st.success(f"成功新增 {n} 个座位")
                    st.rerun()
                except BizError as e:
                    st.error(str(e))

        # —— 单个座位状态修改 ——
        st.subheader("修改座位状态")
        if not seats:
            st.info("没有可选座位")
        else:
            seat_options = {
                f"{s['seat_no']}（{s['zone'] or '无区域'}）": s for s in seats
            }
            seat_pick = st.selectbox(
                "选择座位", list(seat_options.keys()), key="seat_pick"
            )
            seat = seat_options[seat_pick]
            st.write(f"当前状态：**{seat['status']}**")

            acol1, acol2, acol3 = st.columns(3)
            with acol1:
                if st.button("设为可用", disabled=(seat["status"] == "可用"),
                             use_container_width=True, key="seat_avail"):
                    try:
                        store_service.set_seat_status(seat["seat_id"], "可用")
                        st.success("已设为可用")
                        st.rerun()
                    except BizError as e:
                        st.error(str(e))
            with acol2:
                if st.button("设为维修", disabled=(seat["status"] == "维修"),
                             use_container_width=True, key="seat_repair"):
                    try:
                        store_service.set_seat_status(seat["seat_id"], "维修")
                        st.success("已设为维修")
                        st.rerun()
                    except BizError as e:
                        st.error(str(e))
            with acol3:
                if st.button("设为停用", disabled=(seat["status"] == "停用"),
                             use_container_width=True, key="seat_disable"):
                    try:
                        store_service.set_seat_status(seat["seat_id"], "停用")
                        st.success("已设为停用")
                        st.rerun()
                    except BizError as e:
                        st.error(str(e))
