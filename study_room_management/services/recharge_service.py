"""充值 / 购卡业务 —— 事务边界最典型的例子。

职责：
    - 校验业务规则，失败时抛 BizError（带中文提示），由 ui 层统一捕获显示
    - 调用 repository 完成读写
    - 事务边界在本层，用 db/uow.py 的 with uow() as cur 打开

禁止：
    - 写 SQL（属于 repository/）
    - import streamlit
    - 直接操作 st.session_state（界面状态由 ui 层负责写）

预期函数（按需增删）：
    create_order(user_id, card_type_id, pay_method) -> order dict
        order_no 由本层生成（建议：时间戳 + 用户ID + 随机串）
    pay(order_no) -> 支付并到账，返回新的卡信息
        ⚠️ 在【一个事务】里做两件事：订单改「已支付」+ 生成/更新 user_card
        两步必须同成同败，否则会出现"钱付了卡没到"
    cancel_order(order_no)
    list_my_recharges(user_id, page)
    list_all(status, page)              管理端

幂等：order_no 有唯一索引，捕获 IntegrityError → 返回已存在的订单，
      用于挡住按钮双击 / 页面刷新造成的重复提交。

卡的面值、次数、有效期、折扣怎么算见 DESIGN.md 的 A3，定完在这里实现，
不要在 repository 里算。
"""
