"""用户端 · 会员充值 / 购卡。

展示在售卡种 → 选卡下单 →（演示环境直接模拟支付）→ 展示新的余额。
业务调 services/recharge_service.py。
"""
import streamlit as st

from config import KIND_HOURS, KIND_NAMES, KIND_STORED, KIND_TIMES
from services import recharge_service
from services.exceptions import BizError
from ui.components import kind_name, pay_status_name, sidebar_user

user = sidebar_user()
if user.get("role") != "user":
    st.error("这页是用户端页面，请用用户账号登录。")
    st.stop()

user_id = user["user_id"]
st.title("会员充值 / 购卡")


def _value_text(ct):
    """把卡种的 kind+value 翻译成人话。"""
    kind = int(ct["kind"])
    v = int(ct["value"] or 0)
    if kind == KIND_HOURS:
        return f"{v} 分钟（{v // 60} 小时）"
    if kind == KIND_TIMES:
        return f"{v} 次"
    return "按余额扣费"


# ───────────────────────── 我持有的卡 ─────────────────────────
st.subheader("我持有的卡")
cards = recharge_service.list_my_cards(user_id)
if cards:
    st.dataframe(
        [{
            "卡号": c["card_no"],
            "卡种": c["card_name"],
            "类型": kind_name(c["kind"]),
            "余额(元)": float(c["balance"]),
            "剩余次数": c["remaining_times"],
            "剩余分钟": c["remaining_minutes"],
            "到期日": c["expire_at"],
            "状态": "正常" if int(c["status"]) == 1 else "已冻结",
        } for c in cards],
        width="stretch", hide_index=True,
    )
else:
    st.info("还没有卡，从下面挑一个卡种购买吧。")

# ───────────────────────── 在售卡种 ─────────────────────────
st.divider()
st.subheader("在售卡种")

card_types = recharge_service.list_card_types()
if not card_types:
    st.warning("管理员还没有上架任何卡种。")
    st.stop()

st.dataframe(
    [{
        "卡种": ct["card_name"],
        "类型": kind_name(ct["kind"]),
        "售价(元)": float(ct["price"]),
        "对应价值": _value_text(ct),
        "有效期(天)": ct["valid_days"],
    } for ct in card_types],
    width="stretch", hide_index=True,
)

ct_map = {f"{ct['card_name']}（{ct['price']} 元）": ct for ct in card_types}
picked = st.selectbox("选择要购买的卡种", list(ct_map.keys()))
ct = ct_map[picked]

if st.button("下单", type="primary"):
    try:
        order = recharge_service.create_order(user_id, ct["card_type_id"])
        st.session_state["pending_order_no"] = order["order_no"]
        st.success(f"下单成功，单号 {order['order_no']}，应付 {order['amount']:.2f} 元")
    except BizError as e:
        st.error(str(e))

# ───────────────────────── 模拟支付 ─────────────────────────
pending = st.session_state.get("pending_order_no")
if pending:
    st.divider()
    st.subheader("模拟支付")
    st.info(f"待支付单号：{pending}（演示环境直接点下面按钮完成支付）")
    pcol1, pcol2 = st.columns(2)
    with pcol1:
        if st.button("确认支付", type="primary"):
            try:
                result = recharge_service.pay(pending)
                action = "新开卡" if result["created"] else "累加到已有卡"
                st.success(
                    f"支付成功！{action} {result['card_no']}，"
                    f"金额 {result['amount']:.2f} 元"
                )
                st.session_state.pop("pending_order_no", None)
                st.rerun()
            except BizError as e:
                st.error(str(e))
    with pcol2:
        if st.button("取消订单"):
            try:
                recharge_service.cancel_order(pending)
                st.session_state.pop("pending_order_no", None)
                st.rerun()
            except BizError as e:
                st.error(str(e))

# ───────────────────────── 我的充值记录 ─────────────────────────
st.divider()
st.subheader("我的充值记录")
records, total = recharge_service.list_my_recharges(user_id, page=1, page_size=20)
if records:
    st.caption(f"共 {total} 条")
    st.dataframe(
        [{
            "单号": r["order_no"],
            "卡种": r["card_name"],
            "金额(元)": float(r["amount"]),
            "支付状态": pay_status_name(r["pay_status"]),
            "支付时间": r["pay_time"],
            "生成卡号": r["card_no"] or "—",
        } for r in records],
        width="stretch", hide_index=True,
    )
else:
    st.info("还没有充值记录。")
