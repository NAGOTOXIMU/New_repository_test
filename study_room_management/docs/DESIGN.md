# 自习室预约与会员管理系统 · 设计说明

> 文档用途：动手写代码前，全组对"怎么分层、数据长什么样、业务怎么流转"达成一致。
> 配套图：共四张（分层架构 / 预约调用链 / 业务流程与事务 / 预约状态机），另行发送，**不放进本仓库**。
> 维护约定：**这份文档和 `db/sql/01_schema.sql` 是全组公共依赖，改动前先在群里说。**

---

## 一、技术栈与分层

**Python 3.10+ + Streamlit（界面）+ PyMySQL（数据访问）+ MySQL 8.0（存储）**

```
界面层 ui/           ← 唯一认识 Streamlit 的地方
    ↓ 调用
业务层 services/     ← 业务规则 + 事务边界
    ↓ 调用
数据访问层 repository/  ← 所有 SQL 唯一的所在地
    ↓ 调用
连接与事务 db/        ← connection.py / uow.py
    ↓ pymysql · TCP 3306
MySQL 8.0
```

📊 **图：分层架构与依赖铁律**（另行发送）

### 三条铁律

1. **只能向下调用，不能越级** —— `ui` 不准直接 `import repository`，必须经过 `services`。
2. **不能反向依赖** —— `repository` 不准 `import services`；任何层都不准 `import ui`。
3. **`services/` 和 `repository/` 里绝不出现 `import streamlit`**。

> 第 3 条是"分层真假"的唯一判据。做到了，业务逻辑就能用 pytest 脱离界面测试；做不到，就只是把代码分到了不同文件夹。

### 各层职责

| 层 | 目录 | 放什么 | 不准放什么 |
|---|---|---|---|
| 界面 | `ui/` | 按钮、表单、表格、`st.session_state` | SQL、业务判断 |
| 业务 | `services/` | 校验规则、事务边界、金额计算 | SQL、`import streamlit` |
| 数据访问 | `repository/` | `SELECT / INSERT / UPDATE`，全部参数化 | 业务判断、`import streamlit` |
| 基础 | `db/` | 连接管理、`uow` 事务上下文 | 业务逻辑 |
| 横切 | `config.py` | 数据库地址、端口、常量 | 密码明文进 Git |

---

## 二、数据模型

**8 张表**（建表脚本：`db/sql/01_schema.sql`，以《数据库规范》V1.0 为基准）

> 规范原本只有 7 张表，`user_card` 是为补齐规范逻辑缺口而新增的。
> 原因与完整 DDL 见 [`数据库规范落地对照与缺口补充.md`](数据库规范落地对照与缺口补充.md) 的「缺口 1」。

| 表 | 作用 | 关键点 |
|---|---|---|
| `store` | 门店 | `open_time` / `close_time` 决定可预约时段 |
| `user` | 普通用户 | **`phone` 唯一登录账号**；`balance`/`remaining_hours` 是汇总冗余 |
| `admin` | 管理员 | `store_id` 为 NULL = 超级管理员 |
| `card_type` | 卡种字典 | `kind` 1时长卡 / 2次卡 / 3储值卡；`value` = 对应价值 |
| `seat` | 座位 | `(store_id, seat_code)` 唯一；`area_type` 1普通/2安静/3靠窗 |
| **`user_card`** | **用户持卡实例（账户）** | 余额 / 剩余次数 / 剩余分钟，**按卡归属** |
| `reservation_order` | 座位预约 | `uk_seat_slot` 唯一索引 + 座位级 `GET_LOCK` 防抢座 |
| `recharge_order` | 充值购卡订单 | `order_no` 唯一索引做幂等 |

### 四个关键设计点

1. **`user_card` 是系统的枢纽**：充值让它加，预约让它减，退款让它回。
   它是"账户状态"，`recharge_order` 是"资金流水"——**两者成对才能对账**。
   （规范里缺的就是这张；没有它，"扣费逻辑"无处落地。）
2. **防抢座靠数据库 + 一把座位锁**：
   唯一索引 `uk_seat_slot (seat_id, reserve_date, start_time, end_time, active_flag)`
   —— 同一个座位、同一天、同一个时段，只能有一条有效预约。
   ⚠️ 但唯一索引**判不出「部分重叠」**（09:00~11:00 与 10:00~12:00 开始时间不同），
   所以下单流程里还有一道座位级互斥锁（`GET_LOCK('seat_slot_<seat_id>')`）：
   锁住 → 查重叠 → 插入 → 释放，同一个座位的下单被串行化，见
   `services/order_service.py: reserve()` 与 `repository/reservation_repo.py: lock_seat_slot()`。
3. **取消预约时把 `active_flag` 置为 `NULL`**：
   MySQL 的 UNIQUE 索引允许多个 NULL，于是取消后该时段能被重新预约。
   （若只改成 `order_status=4`，唯一键仍被占住，时段就永久约不了了。）
   ⚠️ 只有「取消」和「日期已过」才置 NULL。订单走到「已完成」时**不释放**时段，
   否则历史预约挡不住重复预约。
4. **`(seat_id, store_id)` 复合外键**：杜绝"预约记录的门店 ≠ 座位的门店"这种脏数据。
5. **座位是否「被占用」是算出来的，不是存出来的**：
   `seat.status` 只表示「可用 / 维修中」，跟预约无关。要判断某时刻座位有没有人，
   必须拿 `reserve_date + 时段`去 `reservation_order` 里查有效预约的重叠
   （`seat_repo.list_with_occupancy()`），时间一过就自然回到空闲，
   不需要任何定时任务去改座位表。

### 关系速查

```
store ──1:N──> seat            user ──1:N──> user_card ──N:1──> card_type
store ──1:N──> admin           user ──1:N──> recharge_order ──N:1──> card_type
                               user ──1:N──> reservation_order ──N:1──> seat
                                                              └──N:1──> user_card
```

---

## 三、四条核心业务

📊 **图：四条核心业务的事务流程**（另行发送）
📊 **图：一次座位预约的完整调用链**（另行发送）
📊 **图：预约状态流转**（另行发送）

| 业务 | 涉及表 | 需要事务吗 | 并发防线 |
|---|---|---|---|
| 注册 / 登录 | `user` | ❌ 单条 INSERT 本身原子 | `phone` 唯一索引 |
| 充值购卡 | `recharge_order` + `user_card` | ✅ | `order_no` 唯一索引（防按钮双击重复下单） |
| 座位预约 | `reservation_order` + `user_card` | ✅ | `FOR UPDATE` 锁卡 + **座位级 `GET_LOCK`** + 锁内重叠查询 + `uk_seat_slot` 唯一索引兜底 |
| 取消预约 | `reservation_order` + `user_card` | ✅ | `active_flag` 置 NULL 释放时段，权益原路退回 |
| 退款 | `recharge_order` + `user_card` | ✅ | `pay_status=1→2` 条件更新；权益已被消费则拒绝 |

**预约下单的四道防线**（`services/order_service.py: reserve()`，顺序不能乱）：

1. `SELECT ... FOR UPDATE` 锁住用户的卡 —— 防止并发扣同一张卡的余额 / 次数 / 分钟；
2. `GET_LOCK('seat_slot_<seat_id>')` 锁住这个座位 —— 把「查冲突 + 插入」串行化，
   这是唯一能挡住**部分重叠时段**的机制；锁顺序固定为「先卡后座位」，避免死锁；
3. 锁内再查一次 `seat_repo.has_active_reservation()` 的重叠 —— 有冲突就报人话错误，
   而不是等数据库抛唯一键异常；
4. `uk_seat_slot` 唯一索引兜底完全相同的时段（例如客户端重复提交），
   撞了会 `IntegrityError`，转成「这个时段刚刚被别人约走了」。


**计费口径**（规范里座位表没有价格列，所以按「卡」计费）：

| 卡类型 | 扣减方式 |
|---|---|
| 时长卡 `kind=1` | 每次预约扣 `duration` 分钟；`value` = 总分钟数 |
| 次卡 `kind=2` | 每次预约扣 1 次；`value` = 总次数 |
| 储值卡 `kind=3` | 扣 `小时单价 × 小时数`（不足 1 小时按 1 小时取整）；小时单价 = `price ÷ value`（`value` 约定为"卡内包含的小时数"），`value=0` 时用 `config.STORED_HOUR_RATE` 兜底 |

**通用规则**：事务边界一律在 `services/` 层，用 `db/uow.py` 的上下文管理器包住：
进去 `BEGIN`，正常结束 `COMMIT`，抛异常自动 `ROLLBACK`。任一步失败，余额不会被扣、时段不会被占。

---

## 四、开发顺序

| 阶段 | 做什么 | 完成标志 |
|---|---|---|
| **0** | 冻结 `db/sql/01_schema.sql` | 8 张表建好，全组确认 |
| **1** | 打通一条最细的垂直切片：**登录** | 网页上能登进去（ui → service → repo → 数据库全走通） |
| **2** | 补基础设施：`config.py`、`db/connection.py`、`db/uow.py`、`ui/components.py`、`app.py`（`st.navigation`） | 新页面能挂进导航、能连库、能开事务 |
| **3** | 按功能并行开发，每人一条垂直切片 | 顺序：注册登录 → 充值购卡 → 座位预约 → 我的订单 → 管理端 → 数据看板 |
| **4** | 收尾：`02_indexes.sql`（用 `EXPLAIN` 验证）、`03_seed.sql`、README | 演示数据齐、索引有效 |

> ⚠️ 第 1 阶段的"只做登录"很关键：它本身最简单，却能一次性暴露**所有架构风险**（导入路径、`st.navigation`、连接配置）。比写完 500 行再发现问题便宜得多。

> ⚠️ `ui/pages/` 下的页面**必须用 `st.navigation()` 显式注册**才会显示——Streamlit 的自动多页机制只认与入口同级的扁平 `pages/` 目录，不会递归 `ui/pages/user/` 这类子目录。每个管理端页面第一行还要调 `require_role("admin")`，因为**导航里隐藏 ≠ 权限控制**（URL 可以直接输）。

---

## 五、✅ 已拍板的设计决策

> 这一节原来叫「⚠️ 待拍板的设计决策」。**A/B 两类已经全部定完并落地到代码**，
> 下面是最终裁决，改成"已定"以免后人再纠结。

### A 类 · 已定（影响代码结构）

| # | 问题 | 最终裁决 | 落地位置 |
|---|---|---|---|
| **A1** | 「待使用」→「进行中」谁推进？ | **① 定时任务自动推进**：项目没有常驻调度器，所以做成「打开页面时同步 + 60 秒节流」——预约时段一开始，`sync_time_status()` 把当天该时段的「待使用」置「进行中」，时段结束后置「已完成」。**② 管理员手工签到**保留，用于提前开始或纠错。**③ `expire_overdue()`** 继续负责日期已过的批量置「已过期」 | `repository/reservation_repo.py: sync_time_status()` / `expire_overdue()`；`ui/components.py: sync_time_status_once()`；页面 `user/1_home_store.py`、`user/3_my_orders.py`、`admin/3_order_manage.py`、`admin/5_dashboard.py` |
| **A2** | 超时未到怎么算？ | 预约日期过了仍未使用的，由 `expire_overdue()` 置 `order_status=5` 并**释放时段**；**当天时段已过**的则由 `sync_time_status()` 置「已完成(3)」（日期还没过，叫"过期"不合适，且**不释放时段**）；两种情况都不额外扣费（费用在预约时已扣，取消才退） | `repository/reservation_repo.py: expire_overdue()` / `sync_time_status()` |
| **A3** | 扣费规则？ | **按卡种计费**（规范里座位表没有价格列）：时长卡扣分钟、次卡扣 1 次、储值卡扣 `小时单价 × 小时数` | `services/order_service.py: _charge()` / `_hourly_rate()`，口径见 `docs/数据库规范落地对照与缺口补充.md` 缺口 4 |
| **A4** | 多张卡用哪张？ | **① 用户在预约页手选**（下拉框列出所有可用卡），未指定时自动取第一张可用卡 | `services/order_service.py: _pick_card()`，页面 `user/2_seat_reservation.py` |
| **A5** | 同一用户同一时段能约几个座位？ | **允许多个**（一个用户可以给自己和朋友各占一个座位）。若要限制为 1 个，需再加唯一约束 `uk_user_slot (user_id, reserve_date, start_time, active_flag)` | 当前未加约束 |

### B 类 · 已定（当前假设即最终口径）

| # | 事项 | 最终口径 |
|---|---|---|
| **B1** | 时段粒度 | **整点、最短 1 小时、最长 8 小时**（`duration` 以分钟存，必须是 60 的整数倍，`normalize_duration()` 强校验） |
| **B2** | 管理员是否分店隔离 | **是**：`admin.store_id` 为 NULL = 超管看全部；非 NULL 只看本店（`admin/3_order_manage.py` 已按此过滤） |
| **B3** | 是否真实对接支付 | **演示时模拟**：点「确认支付」直接调 `recharge_service.pay()` 把订单改成已支付并开卡 |
| **B4** | 密码哈希用什么 | **标准库 `hashlib.pbkdf2_hmac`（sha256，10 万次迭代 + 每密码随机盐）**，零依赖，见 `services/password.py`。用户密码最少 6 位 |
| **B5** | 管理员建表方式 | **独立 `admin` 表**，与用户表分开，各有独立登录入口 |
| **B6** | 一个用户能否持多张卡 | **能**（`user_card` 独立表，`user_id` 一对多）；同一卡种下已有可用卡时，重复购买会**累加**到那张卡上 |
| **B7** | 登录标识 | **用户用 `phone` 登录**（规范规定 phone 是唯一登录账号）；**管理员用 `username` 登录** |

### C 类 · 原"还没建的东西"现状

| 事项 | 现状 |
|---|---|
| `ui/pages/stats/` 目录 | ✅ 改为 `ui/pages/admin/5_dashboard.py`，已接入 `stats_service` |
| `.gitignore` | ✅ 已含 `.env` |
| `README.md` | ✅ 已重写（建库、跑起来、模块边界、测试账号） |
| `tests/` | ⚠️ 仍未建正式 pytest 用例；但已有一轮 60 项端到端验证脚本跑通全部核心业务 |
| 统一异常 | ✅ `services/exceptions.py` 的 `BizError`，ui 统一 `except BizError` 显示红字 |
| 状态常量 | ✅ 集中在 `config.py`（`ORDER_*` / `PAY_*` / `KIND_*` / `STATUS_*` / `ROLE_*`），代码中不再出现魔法数字或中文字符串 |

---

## 六、协作约定

1. **`db/sql/` 和 `repository/` 是全组公共依赖**。谁要改表结构，先在群里说，由**一个人**统一改，改完通知所有人。
2. `main` 分支保持可运行；功能开发在 `feature/xxx` 分支上做。
3. 提交前先 `git pull`，看到冲突按 [`开发流程.md`](开发流程.md) 处理。
4. **密码、密钥一律不进仓库**（`config.py` 里的密码后续要改成读环境变量或 `.env`）。
5. 数据库账号不要用 `root` 跑应用（正式一点可以建 `app_user` 并只授必要的权限）。
