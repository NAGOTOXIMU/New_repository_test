"""管理端 · 卡种管理。

功能：卡种新增、改价、上架下架。
校验与数据库 CHECK 约束一致：price >= 0、value >= 0、valid_days > 0、kind ∈ {1,2,3}。
"""
import streamlit as st

from config import KIND_HOURS, KIND_NAMES, KIND_STORED, KIND_TIMES, STATUS_OFF, STATUS_ON
from repository import card_type_repo
from services.exceptions import BizError
from ui.components import kind_name, on_off, require_role, sidebar_user

require_role("admin")
sidebar_user()

st.title("卡种管理")

st.caption("时长卡的「对应价值」填**分钟数**；次卡填**次数**；储值卡填 0（余额由充值金额决定）。")

rows = card_type_repo.list_paged(offset=0, limit=200)
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

st.divider()
col1, col2 = st.columns(2)

with col1:
    st.subheader("新增卡种")
    with st.form("new_card_type"):
        n_name = st.text_input("卡种名称")
        n_kind = st.selectbox("卡类型", [KIND_HOURS, KIND_TIMES, KIND_STORED],
                              format_func=lambda v: KIND_NAMES[v])
        n_price = st.number_input("售价（元）", min_value=0.0, value=49.0, step=1.0)
        n_value = st.number_input("对应价值（时长卡=分钟 / 次卡=次数 / 储值卡=0）",
                                  min_value=0, value=600, step=10)
        n_days = st.number_input("有效期（天）", min_value=1, value=180, step=1)
        if st.form_submit_button("创建"):
            if not n_name.strip():
                st.error("卡种名称不能为空")
            elif n_days <= 0:
                st.error("有效期必须大于 0")
            else:
                try:
                    ctid = card_type_repo.create(n_name.strip(), n_kind, n_price,
                                                 int(n_value), int(n_days))
                    st.success(f"卡种创建成功，card_type_id={ctid}")
                    st.rerun()
                except Exception as e:
                    st.error(f"创建失败：{e}")

with col2:
    st.subheader("修改 / 上下架")
    if not rows:
        st.info("还没有卡种。")
    else:
        cmap = {f"{r['card_type_id']} - {r['card_name']}": r for r in rows}
        picked = st.selectbox("选择卡种", list(cmap.keys()))
        target = cmap[picked]
        ctid = target["card_type_id"]

        new_status = st.radio(
            "上架状态", [STATUS_ON, STATUS_OFF],
            index=0 if int(target["status"]) == STATUS_ON else 1,
            format_func=lambda v: "上架" if v == STATUS_ON else "下架",
            horizontal=True,
        )
        if st.button("保存上架状态"):
            card_type_repo.update_status(ctid, new_status)
            st.success("已更新")
            st.rerun()

        with st.form("edit_card_type"):
            e_name = st.text_input("卡种名称", value=target["card_name"])
            e_price = st.number_input("售价（元）", min_value=0.0,
                                      value=float(target["price"]), step=1.0)
            e_value = st.number_input("对应价值", min_value=0,
                                      value=int(target["value"]), step=10)
            e_days = st.number_input("有效期（天）", min_value=1,
                                     value=int(target["valid_days"]), step=1)
            if st.form_submit_button("保存修改"):
                try:
                    card_type_repo.update(ctid, card_name=e_name, price=e_price,
                                          value=int(e_value), valid_days=int(e_days))
                    st.success("已更新")
                    st.rerun()
                except Exception as e:
                    st.error(f"更新失败：{e}")
