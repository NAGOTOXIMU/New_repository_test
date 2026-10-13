"""管理端 · 卡种管理。

功能：卡种新增、改价、上架下架、分页浏览。
校验与数据库 CHECK 约束一致：price >= 0、value >= 0、valid_days > 0、kind ∈ {1,2,3}。
校验逻辑统一放在 services/card_type_service.py，本页只收集输入 + 显示结果。
"""
import streamlit as st

from config import KIND_HOURS, KIND_NAMES, KIND_STORED, KIND_TIMES, STATUS_OFF, STATUS_ON
from services import card_type_service
from services.exceptions import BizError
from ui.components import flash, kind_name, on_off, require_role, sidebar_user

require_role("admin")
sidebar_user()
flash()

st.title("卡种管理")

st.caption("「对应价值」按卡种填：时长卡=分钟数；次卡=次数；"
           "储值卡=卡内小时数（用来换算小时单价，填 0 表示不指定）。")

KIND_OPTIONS = [KIND_HOURS, KIND_TIMES, KIND_STORED]

# 卡种列表（含已下架）
st.subheader("卡种列表")

col_ps, _ = st.columns([1, 3])
with col_ps:
    page_size = st.selectbox("每页", [10, 20, 50], key="ct_page_size")

page = st.session_state.get("ct_page", 1)
rows, total = card_type_service.list_card_types_paged(page, page_size)

if rows:
    st.dataframe(
        [{
            "ID": r["card_type_id"],
            "卡种名": r["card_name"],
            "类型": kind_name(r["kind"]),
            "售价(元)": float(r["price"]),
            "对应价值": r["value"],
            "有效期(天)": r["valid_days"],
            "上架状态": on_off(r["status"], "上架", "下架"),
        } for r in rows],
        width="stretch", hide_index=True,
    )
else:
    st.info("还没有卡种。")

# —— 分页 ——
total_pages = max(1, (total + page_size - 1) // page_size)
pcol1, pcol2, pcol3 = st.columns([1, 2, 1])
with pcol1:
    if st.button("上一页", disabled=(page <= 1), key="ct_prev"):
        st.session_state["ct_page"] = page - 1
        st.rerun()
with pcol2:
    st.caption(f"共 {total} 条，第 {page} / {total_pages} 页")
with pcol3:
    if st.button("下一页", disabled=(page >= total_pages), key="ct_next"):
        st.session_state["ct_page"] = page + 1
        st.rerun()

st.divider()
col1, col2 = st.columns(2)

# 新增卡种
with col1:
    st.subheader("新增卡种")
    # 卡类型放在 form 外面，切换时才能立刻把「对应价值」的提示语换掉
    n_kind = st.selectbox("卡类型", KIND_OPTIONS,
                          format_func=lambda v: KIND_NAMES[v], key="ct_new_kind")
    with st.form("new_card_type"):
        n_name = st.text_input("卡种名称")
        n_price = st.number_input("售价（元）", min_value=0.0, value=49.0, step=1.0)
        n_value = st.number_input(card_type_service.describe_value(n_kind),
                                  min_value=0, value=600, step=10,
                                  help="时长卡填分钟数（600 = 10 小时）；"
                                       "次卡填次数；储值卡填卡内小时数")
        n_days = st.number_input("有效期（天）", min_value=1, value=180, step=1)
        if st.form_submit_button("创建"):
            try:
                ctid = card_type_service.create_card_type(
                    n_name, n_kind, n_price, int(n_value), int(n_days))
                flash(f"卡种创建成功，card_type_id={ctid}")
                st.rerun()
            except BizError as e:
                st.error(str(e))

# 修改 / 上下架
with col2:
    st.subheader("修改 / 上下架")
    all_rows, _ = card_type_service.list_card_types_paged(1, 1000)
    if not all_rows:
        st.info("还没有卡种。")
    else:
        cmap = {f"{r['card_type_id']} - {r['card_name']}": r for r in all_rows}
        picked = st.selectbox("选择卡种", list(cmap.keys()), key="ct_edit")
        target = cmap[picked]
        ctid = target["card_type_id"]

        new_status = st.radio(
            "上架状态", [STATUS_ON, STATUS_OFF],
            index=0 if int(target["status"]) == STATUS_ON else 1,
            format_func=lambda v: "上架" if v == STATUS_ON else "下架",
            horizontal=True, key="ct_status",
        )
        if st.button("保存上架状态"):
            try:
                card_type_service.set_card_type_status(ctid, new_status)
                flash("已更新")
                st.rerun()
            except BizError as e:
                st.error(str(e))

        with st.form("edit_card_type"):
            e_name = st.text_input("卡种名称", value=target["card_name"])
            e_price = st.number_input("售价（元）", min_value=0.0,
                                      value=float(target["price"]), step=1.0)
            e_value = st.number_input(card_type_service.describe_value(target["kind"]),
                                      min_value=0, value=int(target["value"]), step=10,
                                      key="e_value")
            e_days = st.number_input("有效期（天）", min_value=1,
                                     value=int(target["valid_days"]), step=1)
            if st.form_submit_button("保存修改"):
                try:
                    card_type_service.update_card_type(
                        ctid, card_name=e_name, price=e_price,
                        value=int(e_value), valid_days=int(e_days))
                    flash("已更新")
                    st.rerun()
                except BizError as e:
                    st.error(str(e))
