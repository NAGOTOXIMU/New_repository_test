"""管理端 · 卡种管理。

第一行必须调用 ui.components.require_role("admin")。
功能：卡种增改、上架下架；price >= 0、discount 在 0.01~1.00（与数据库 CHECK 一致）。
"""
import pandas as pd
import streamlit as st

from services import card_type_service
from services.exceptions import BizError
from ui.components import require_role

require_role("admin")

st.title("卡种管理")

KINDS = ["储值", "次卡", "时长卡"]


def _render_kind_fields(kind, prefix="c", defaults=None):
    """根据卡种类型渲染对应的金额/次数/时长字段，返回取值 dict。"""
    defaults = defaults or {}
    result = {}
    col1, col2 = st.columns(2)
    if kind == "储值":
        with col1:
            result["face_value"] = st.number_input(
                "到账金额（元）*", min_value=0.0, step=1.0,
                value=float(defaults.get("face_value") or 0), key=f"{prefix}_face")
        result["total_times"] = None
        result["total_hours"] = None
    elif kind == "次卡":
        with col1:
            result["total_times"] = st.number_input(
                "总次数 *", min_value=1, step=1,
                value=int(defaults.get("total_times") or 1), key=f"{prefix}_times")
        result["face_value"] = None
        result["total_hours"] = None
    else:  # 时长卡
        with col1:
            result["total_hours"] = st.number_input(
                "总时长（小时）*", min_value=1, step=1,
                value=int(defaults.get("total_hours") or 1), key=f"{prefix}_hours")
        result["face_value"] = None
        result["total_times"] = None
    return result


# ───────────────────────── 卡种列表 ─────────────────────────
st.subheader("卡种列表")

col_ps, _ = st.columns([1, 3])
with col_ps:
    page_size = st.selectbox("每页", [10, 20, 50], key="ct_page_size")

page = st.session_state.get("ct_page", 1)
rows, total = card_type_service.list_card_types_paged(page, page_size)

if rows:
    df = pd.DataFrame(rows).rename(columns={
        "card_type_id": "ID",
        "name": "卡种名称",
        "kind": "类型",
        "price": "售价(元)",
        "face_value": "到账金额",
        "total_times": "总次数",
        "total_hours": "总时长(h)",
        "valid_days": "有效期(天)",
        "discount": "折扣",
        "status": "状态",
    })
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("暂无卡种")

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

# ───────────────────────── 新增卡种 ─────────────────────────
with st.expander("➕ 新增卡种", expanded=False):
    with st.form("create_ct_form"):
        c_name = st.text_input("卡种名称 *")
        c_kind = st.selectbox("卡种类型 *", KINDS, key="c_kind")
        ccol1, ccol2 = st.columns(2)
        with ccol1:
            c_price = st.number_input("售价（元）*", min_value=0.0, step=1.0, value=0.0)
        with ccol2:
            c_valid = st.number_input("有效期（天）*", min_value=1, step=1, value=365)
        c_discount = st.slider("折扣率", min_value=0.01, max_value=1.00,
                               value=1.00, step=0.01, help="1.00 = 不打折")

        extra = _render_kind_fields(c_kind, prefix="c")

        c_submit = st.form_submit_button("创建", use_container_width=True)

    if c_submit:
        try:
            cid = card_type_service.create_card_type(
                c_name, c_kind, c_price,
                face_value=extra.get("face_value"),
                total_times=extra.get("total_times"),
                total_hours=extra.get("total_hours"),
                valid_days=c_valid, discount=c_discount,
            )
            st.success(f"卡种创建成功，ID = {cid}")
            st.rerun()
        except BizError as e:
            st.error(str(e))

# ───────────────────────── 编辑 / 上下架 ─────────────────────────
st.subheader("编辑卡种")
all_rows, _ = card_type_service.list_card_types_paged(1, 1000)
if not all_rows:
    st.info("请先新增卡种")
else:
    options = {f"{r['card_type_id']} · {r['name']}（{r['kind']}）": r for r in all_rows}
    pick = st.selectbox("选择要编辑的卡种", list(options.keys()), key="edit_ct")
    ct = options[pick]

    with st.form("edit_ct_form"):
        e_name = st.text_input("卡种名称", value=ct["name"])
        e_kind = st.selectbox("卡种类型", KINDS,
                              index=KINDS.index(ct["kind"]), key="e_kind")
        ecol1, ecol2 = st.columns(2)
        with ecol1:
            e_price = st.number_input("售价（元）", min_value=0.0, step=1.0,
                                      value=float(ct["price"]))
        with ecol2:
            e_valid = st.number_input("有效期（天）", min_value=1, step=1,
                                      value=int(ct["valid_days"]))
        e_discount = st.slider("折扣率", min_value=0.01, max_value=1.00,
                               value=float(ct["discount"]), step=0.01)

        e_extra = _render_kind_fields(e_kind, prefix="e", defaults=ct)

        e_submit = st.form_submit_button("保存修改", use_container_width=True)

    if e_submit:
        try:
            card_type_service.update_card_type(
                ct["card_type_id"],
                name=e_name, kind=e_kind, price=e_price,
                face_value=e_extra.get("face_value"),
                total_times=e_extra.get("total_times"),
                total_hours=e_extra.get("total_hours"),
                valid_days=e_valid, discount=e_discount,
            )
            st.success("卡种信息已更新")
            st.rerun()
        except BizError as e:
            st.error(str(e))

    scol1, scol2 = st.columns(2)
    with scol1:
        if st.button("上架", disabled=(ct["status"] == "上架"),
                     use_container_width=True, key="ct_online"):
            try:
                card_type_service.set_card_type_status(ct["card_type_id"], "上架")
                st.success("已上架")
                st.rerun()
            except BizError as e:
                st.error(str(e))
    with scol2:
        if st.button("下架", disabled=(ct["status"] == "下架"),
                     use_container_width=True, key="ct_offline"):
            try:
                card_type_service.set_card_type_status(ct["card_type_id"], "下架")
                st.success("已下架")
                st.rerun()
            except BizError as e:
                st.error(str(e))
