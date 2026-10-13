"""管理端 · 门店与座位管理。

功能：门店信息维护（搜索 + 分页）、批量新增座位、座位状态（可用 / 维修中）。
"""
from datetime import time as dtime, timedelta

import streamlit as st

from config import STATUS_OFF, STATUS_ON
from services import store_service
from services.exceptions import BizError
from ui.components import area_name, on_off, require_role, sidebar_user

require_role("admin")
sidebar_user()

st.title("门店与座位管理")


def _to_time(val):
    """pymysql 把 TIME 列返回成 timedelta，这里转回 datetime.time 给 st.time_input 用。"""
    if isinstance(val, timedelta):
        seconds = int(val.total_seconds())
        return dtime(seconds // 3600, (seconds % 3600) // 60, seconds % 60)
    if isinstance(val, str):
        parts = [int(x) for x in (val.split(":") + ["0", "0"])[:3]]
        return dtime(*parts)
    return val


def _hhmmss(t):
    """st.time_input 的值 -> 服务层要的 'HH:MM:SS' 字符串。"""
    return t.strftime("%H:%M:%S") if t is not None else None


tab_store, tab_seat = st.tabs(["门店", "座位"])

# 门店
with tab_store:
    col_kw, col_ps = st.columns([3, 1])
    with col_kw:
        keyword = st.text_input("搜索门店名 / 地址", key="store_keyword")
    with col_ps:
        page_size = st.selectbox("每页", [10, 20, 50], key="store_page_size")

    page = st.session_state.get("store_page", 1)
    stores, total = store_service.list_stores_paged(keyword or None, page, page_size)

    if stores:
        st.dataframe(
            [{
                "ID": s["store_id"],
                "门店名": s["store_name"],
                "地址": s["address"],
                "营业时间": f"{str(s['open_time'])[:5]}~{str(s['close_time'])[:5]}",
                "座位数": s["seat_count"],
                "状态": on_off(s["status"], "营业中", "停业"),
            } for s in stores],
            width="stretch", hide_index=True,
        )
    else:
        st.info("没有匹配的门店。")

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
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("新增门店")
        with st.form("new_store"):
            n_name = st.text_input("门店名称")
            n_addr = st.text_input("地址")
            tcol1, tcol2 = st.columns(2)
            with tcol1:
                n_open = st.time_input("开门时间", value=dtime(8, 0))
            with tcol2:
                n_close = st.time_input("关门时间", value=dtime(22, 0))
            if st.form_submit_button("创建"):
                try:
                    sid = store_service.create_store(n_name, n_addr,
                                                     _hhmmss(n_open), _hhmmss(n_close))
                    st.success(f"门店创建成功，store_id={sid}")
                    st.rerun()
                except BizError as e:
                    st.error(str(e))

    with col2:
        st.subheader("修改门店 / 切换营业状态")
        # 下拉要能选到任何一家门店，所以单独取一份全量列表，不受上面的分页影响
        all_stores, _ = store_service.list_stores_paged(None, 1, 1000)
        if all_stores:
            smap = {f"{s['store_id']} - {s['store_name']}": s for s in all_stores}
            picked = st.selectbox("选择门店", list(smap.keys()), key="store_edit")
            target = smap[picked]
            new_status = st.radio(
                "营业状态", [STATUS_ON, STATUS_OFF],
                index=0 if int(target["status"]) == STATUS_ON else 1,
                format_func=lambda v: "营业中" if v == STATUS_ON else "停业",
                horizontal=True, key="store_status",
            )
            if st.button("保存营业状态"):
                try:
                    store_service.set_store_status(target["store_id"], new_status)
                    st.success("已更新")
                    st.rerun()
                except BizError as e:
                    st.error(str(e))

            with st.form("edit_store"):
                e_name = st.text_input("门店名称", value=target["store_name"])
                e_addr = st.text_input("地址", value=target["address"])
                ecol1, ecol2 = st.columns(2)
                with ecol1:
                    e_open = st.time_input("开门时间", value=_to_time(target["open_time"]))
                with ecol2:
                    e_close = st.time_input("关门时间", value=_to_time(target["close_time"]))
                if st.form_submit_button("保存门店信息"):
                    # 数据库有 chk_store_time CHECK(close_time > open_time)，
                    # 提前用界面上的 time 值比一次，给一句人话提示（服务层只校验新增）
                    if e_close <= e_open:
                        st.error("关门时间必须晚于开门时间")
                    else:
                        try:
                            store_service.update_store(
                                target["store_id"], store_name=e_name, address=e_addr,
                                open_time=_hhmmss(e_open), close_time=_hhmmss(e_close))
                            st.success("已更新")
                            st.rerun()
                        except BizError as e:
                            st.error(str(e))
        else:
            st.info("先创建一家门店。")

# 座位
with tab_seat:
    stores = store_service.list_stores_paged(None, 1, 1000)[0]
    if not stores:
        st.info("先创建一家门店。")
        st.stop()

    smap = {f"{s['store_id']} - {s['store_name']}": s for s in stores}
    picked = st.selectbox("选择门店", list(smap.keys()), key="seat_store")
    store = smap[picked]
    store_id = store["store_id"]

    with st.form("batch_seat"):
        st.write("批量新增座位")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            prefix = st.text_input("编号前缀", value="A")
        with c2:
            count = st.number_input("数量", min_value=1, max_value=200, value=10)
        with c3:
            area = st.selectbox("区域", [1, 2, 3],
                                format_func=lambda v: area_name(v))
        with c4:
            socket = st.selectbox("带插座", [1, 0],
                                  format_func=lambda v: on_off(v, "是", "否"))
        if st.form_submit_button("批量新增"):
            try:
                n = store_service.batch_add_seats(store_id, prefix, int(count), area, socket)
                st.success(f"新增 {n} 个座位")
                st.rerun()
            except BizError as e:
                st.error(str(e))

    seats = store_service.list_seats(store_id)
    if not seats:
        st.info("这家门店还没有座位。")
    else:
        st.dataframe(
            [{
                "ID": s["seat_id"],
                "编号": s["seat_code"],
                "区域": area_name(s["area_type"]),
                "带插座": on_off(s["has_socket"], "是", "否"),
                "状态": on_off(s["status"], "可用", "维修中"),
            } for s in seats],
            width="stretch", hide_index=True,
        )

        st.divider()
        st.subheader("切换座位状态")
        seat_map = {f"{s['seat_code']}（{area_name(s['area_type'])}）": s for s in seats}
        picked_seat = st.selectbox("选择座位", list(seat_map.keys()), key="seat_pick")
        seat = seat_map[picked_seat]
        new_seat_status = st.radio(
            "座位状态", [STATUS_ON, STATUS_OFF],
            index=0 if int(seat["status"]) == STATUS_ON else 1,
            format_func=lambda v: "可用" if v == STATUS_ON else "维修中",
            horizontal=True, key="seat_status",
        )
        if st.button("保存座位状态"):
            try:
                store_service.set_seat_status(seat["seat_id"], new_seat_status)
                st.success("已更新")
                st.rerun()
            except BizError as e:
                st.error(str(e))
