"""管理端 · 运营数据看板。

营业统计、座位分析、会员分析，全部走 services/stats_service.py（只读）。
"""
import streamlit as st

from services import stats_service, store_service
from ui.components import kind_name, require_role, sidebar_user, sync_time_status_once

require_role("admin")
sidebar_user()
# 看板的「待使用 / 已完成」计数依赖订单状态，先按当前时间推一把（60 秒节流）
sync_time_status_once()

st.title("运营数据看板")

days = st.slider("统计区间（天）", min_value=7, max_value=180, value=30, step=1)

overview = stats_service.overview(days)
row1 = st.columns(4)
row1[0].metric("门店数", overview["门店数"])
row1[1].metric("座位数", overview["座位数"])
row1[2].metric("用户数", overview["用户数"])
row1[3].metric(f"充值金额（{days} 天）", f"{overview['充值金额']:.2f} 元")

row2 = st.columns(4)
row2[0].metric(f"退款金额（{days} 天）", f"{overview['退款金额']:.2f} 元")
row2[1].metric(f"预约总数（{days} 天）", overview["预约总数"])
row2[2].metric("待使用", overview["待使用"])
row2[3].metric("已完成", overview["已完成"])

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("每日营收")
    revenue = stats_service.revenue_by_day(days)
    if revenue:
        st.bar_chart(
            {str(r["day"]): float(r["amount"]) for r in revenue},
            x_label="日期", y_label="营收(元)",
        )
    else:
        st.info("区间内还没有已支付的充值订单。")

    st.subheader("卡种销售分布")
    dist = stats_service.card_type_distribution()
    if dist:
        st.dataframe(
            [{
                "卡种": d["card_name"],
                "类型": kind_name(d["kind"]),
                "销量": d["n"],
                "金额(元)": float(d["amount"]),
            } for d in dist],
            width="stretch", hide_index=True,
        )
    else:
        st.info("还没有卡种销售记录。")

with col2:
    st.subheader("新增会员趋势")
    growth = stats_service.member_growth(days)
    if growth:
        st.line_chart({str(g["day"]): g["n"] for g in growth},
                      x_label="日期", y_label="新增用户")
    else:
        st.info("区间内没有新增用户。")

    st.subheader("各门店预约量")
    by_store = stats_service.reservations_by_store(days)
    if by_store:
        st.dataframe(
            [{"门店": b["store_name"], "预约数": b["n"]} for b in by_store],
            width="stretch", hide_index=True,
        )

st.divider()
st.subheader("热门预约时段")
stores = store_service.list_stores_paged(page=1, page_size=100)[0]
smap = {"全部门店": None}
smap.update({s["store_name"]: s["store_id"] for s in stores})
picked = st.selectbox("门店", list(smap.keys()))
hot = stats_service.hot_hours(smap[picked], days)
if hot:
    st.bar_chart({f"{int(h['hour']):02d}:00": h["n"] for h in hot},
                 x_label="开始时段", y_label="预约数")
else:
    st.info("区间内没有预约记录。")

st.divider()
st.subheader("座位利用率")
if stores:
    util_rows = []
    for s in stores:
        util_rows.append({
            "门店": s["store_name"],
            # 注意：这是「没在维修」的座位数（seat.status=1），不是此刻空闲数；
            # 此刻空闲数要按当前时刻的有效预约算，见 store_service.count_free_now()
            "可用座位（不含维修）": store_service.count_seats(s["store_id"], status=1),
            "利用率": f"{stats_service.seat_utilization(s['store_id'], days) * 100:.2f}%",
        })
    st.dataframe(util_rows, width="stretch", hide_index=True)
