"""数据库连接获取。

职责：
    - 提供统一的连接入口 get_conn()，参数从 config.py 读取
    - 连接缓存：Streamlit 每次交互都会从头重跑整个脚本，
      若每次新建连接会把 MySQL 连接数撑爆（默认上限 151），
      所以这里用 @st.cache_resource 缓存（不是 cache_data——连接对象不可序列化）
    - 提供关连接、连通性自检的辅助函数

为什么 db/ 可以 import streamlit：
    三条铁律禁止的是 services/ 和 repository/ 引入 streamlit；
    db/ 作为基础设施层，为了缓存连接对象必须用它，这是唯一的例外。

不做什么：
    - 不写任何 SQL（SQL 属于 repository/）
    - 不写业务判断（属于 services/）

注意：游标必须用 with 关闭；跨多表的事务统一交给 uow.py 管理。
"""
