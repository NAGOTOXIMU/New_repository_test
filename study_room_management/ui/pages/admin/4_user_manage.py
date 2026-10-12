"""管理端 · 用户管理。

第一行必须调用 ui.components.require_role("admin")。
功能：用户列表、查看持仓与消费记录、冻结 / 解冻账号。
"""
from datetime import timedelta

import pandas as pd
import streamlit as st

from services import user_service
from services.exceptions import BizError
from ui.components import require_role

require_role("admin")

st.title("用户管理")


def _to_str(v):
    """pymysql 把 TIME 列返回成 timedelta，Decimal 的 to_string 也走 str。"""
    if isinstance(v, timedelta):
        s = int(v.total_seconds())
        h, m, sec = s // 3600, (s % 3600) // 60, s % 60
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return str(v) if v is not None else ""


# ───────────────────────── 用户列表 ─────────────────────────
st.subheader("用户列表")

col_kw, col_ps = st.columns([3, 1])
with col_kw:
    keyword = st.text_input("搜索用户名 / 手机号 / 姓名", key="u_keyword")
with col_ps:
    page_size = st.selectbox("每页", [10, 20, 50], key="u_page_size")

page = st.session_state.get("u_page", 1)
rows, total = user_service.list_users_paged(keyword, page, page_size)

if rows:
    df = pd.DataFrame(rows).rename(columns={
        "user_id": "ID",
        "username": "用户名",
        "real_name": "姓名",
        "phone": "手机号",
        "email": "邮箱",
        "status": "状态",
        "created_at": "注册时间",
    })
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("暂无用户")

total_pages = max(1, (total + page_size - 1) // page_size)
pcol1, pcol2, pcol3 = st.columns([1, 2, 1])
with pcol1:
    if st.button("上一页", disabled=(page <= 1), key="u_prev"):
        st.session_state["u_page"] = page - 1
        st.rerun()
with pcol2:
    st.caption(f"共 {total} 条，第 {page} / {total_pages} 页")
with pcol3:
    if st.button("下一页", disabled=(page >= total_pages), key="u_next"):
        st.session_state["u_page"] = page + 1
        st.rerun()

st.divider()

# ───────────────────────── 详情与操作 ─────────────────────────
st.subheader("查看详情 / 冻结账号")
all_rows, _ = user_service.list_users_paged(None, 1, 1000)
if not all_rows:
    st.info("请先有用户")
else:
    options = {
        f"{r['user_id']} · {r['username']}（{r['real_name']}）": r
        for r in all_rows
    }
    pick = st.selectbox("选择用户", list(options.keys()), key="u_pick")
    user = options[pick]
    st.write(f"当前状态：**{user['status']}**  注册时间：{user['created_at']}")

    try:
        detail = user_service.get_user_detail(user["user_id"])
    except BizError as e:
        st.error(str(e))
        detail = None

    if detail:
        # —— 持仓 ——
        st.markdown("**📎 持仓的卡**")
        cards = detail["cards"]
        if cards:
            cdf = pd.DataFrame(cards).rename(columns={
                "card_id": "ID",
                "card_no": "卡号",
                "user_id": "用户ID",
                "card_type_id": "卡种ID",
                "balance": "余额",
                "remaining_times": "剩余次数",
                "remaining_hours": "剩余时长(h)",
                "expire_at": "到期日",
                "status": "状态",
            })
            for col in ("余额", "剩余次数", "剩余时长(h)"):
                if col in cdf.columns:
                    cdf[col] = cdf[col].apply(_to_str)
            st.dataframe(cdf, use_container_width=True, hide_index=True)
        else:
            st.caption("该用户没有卡")

        # —— 最近预约 ——
        st.markdown("**📋 最近 10 条预约**")
        ress = detail["reservations"]
        if ress:
            rdf = pd.DataFrame(ress).rename(columns={
                "order_no": "预约单号",
                "store_name": "门店",
                "seat_no": "座位号",
                "reserve_date": "预约日期",
                "start_time": "开始",
                "end_time": "结束",
                "amount": "金额(元)",
                "status": "状态",
            })
            for col in ("开始", "结束"):
                if col in rdf.columns:
                    rdf[col] = rdf[col].apply(_to_str)
            keep = [c for c in ["预约单号", "门店", "座位号", "预约日期",
                                "开始", "结束", "金额(元)", "状态"] if c in rdf.columns]
            st.dataframe(rdf[keep], use_container_width=True, hide_index=True)
        else:
            st.caption("该用户没有预约记录")

        # —— 最近充值 ——
        st.markdown("**💰 最近 10 条充值 / 购卡**")
        rcs = detail["recharges"]
        if rcs:
            rcdf = pd.DataFrame(rcs).rename(columns={
                "order_no": "充值单号",
                "card_type_name": "卡种",
                "amount": "金额(元)",
                "pay_method": "支付方式",
                "status": "状态",
                "created_at": "下单时间",
            })
            keep = [c for c in ["充值单号", "卡种", "金额(元)", "支付方式",
                                "状态", "下单时间"] if c in rcdf.columns]
            st.dataframe(rcdf[keep], use_container_width=True, hide_index=True)
        else:
            st.caption("该用户没有充值记录")

    # —— 冻结 / 解冻 ——
    st.divider()
    scol1, scol2 = st.columns(2)
    with scol1:
        if st.button("解冻", disabled=(user["status"] == "正常"),
                     use_container_width=True, key="u_unfreeze"):
            try:
                user_service.set_user_status(user["user_id"], "正常")
                st.success("已解冻")
                st.rerun()
            except BizError as e:
                st.error(str(e))
    with scol2:
        if st.button("冻结", disabled=(user["status"] == "冻结"),
                     use_container_width=True, key="u_freeze"):
            try:
                user_service.set_user_status(user["user_id"], "冻结")
                st.success("已冻结")
                st.rerun()
            except BizError as e:
                st.error(str(e))
