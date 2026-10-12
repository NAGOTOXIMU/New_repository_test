"""统计与报表业务（只读）。

职责：
    - 校验业务规则，失败时抛 BizError（带中文提示），由 ui 层统一捕获显示
    - 调用 repository 完成读写
    - 事务边界在本层，用 db/uow.py 的 with uow() as cur 打开

禁止：
    - 写 SQL（属于 repository/）
    - import streamlit
    - 直接操作 st.session_state（界面状态由 ui 层负责写）

预期函数（按需增删）：
    daily_revenue(start_date, end_date) -> list[dict]
    monthly_revenue(year) -> list[dict]
    seat_utilization(store_id, start_date, end_date)
    hot_time_slots(store_id, days)        各时段预约量
    member_growth(days)                   每日新增会员
    card_type_distribution()              各卡种销售占比

返回普通数据结构（dict / list / DataFrame）给 ui 层画图，
不要把 st 的图表对象返回出去。

提示：复杂聚合（GROUP BY / 窗口函数 / 多表 JOIN）适合直接写原生 SQL，
      不必强行套 ORM。这类查询最能体现数据库能力，写完记得用 EXPLAIN 看执行计划。
"""
