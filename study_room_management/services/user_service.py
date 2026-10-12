"""用户侧业务：注册、登录、资料管理。

职责：
    - 校验业务规则，失败时抛 BizError（带中文提示），由 ui 层统一捕获显示
    - 调用 repository 完成读写
    - 事务边界在本层，用 db/uow.py 的 with uow() as cur 打开

禁止：
    - 写 SQL（属于 repository/）
    - import streamlit
    - 直接操作 st.session_state（界面状态由 ui 层负责写）

预期函数（按需增删）：
    register(username, password, real_name, phone, email) -> user dict
        查重（用户名 / 手机号）→ 密码哈希 → 建用户
    login(username, password) -> user dict
        失败抛 BizError("用户名或密码错误")，不要区分"用户不存在"和"密码错"
    get_profile(user_id)
    change_password(user_id, old_password, new_password)
    freeze(user_id) / unfreeze(user_id)          管理端调用
    list_users(keyword, page) / count_users(keyword)

密码哈希方案见 docs/DESIGN.md 的 B4（bcrypt 或标准库 pbkdf2_hmac），
定下来后在这里实现，repository 只接收哈希后的字符串。

事务：注册是单表写，不需要事务。
"""
