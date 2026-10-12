# 自习室预约与会员管理系统 · 设计说明

> 文档用途：动手写代码前，全组对"怎么分层、数据长什么样、业务怎么流转"达成一致。
> 配套图：见 [`diagrams/`](diagrams/) 目录（四个 HTML，用浏览器打开即可交互查看）。
> 维护约定：**这份文档和 `db/sql/01_schema.sql` 是全组公共依赖，改动前先在群里说。**

---

## 一、技术栈与分层

**Python 3.14 + Streamlit（界面）+ PyMySQL（数据访问）+ MySQL 8.0（存储）**

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

📊 **图：[分层架构与依赖铁律](diagrams/01-分层架构.html)**

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

**8 张表**（建表脚本：`db/sql/01_schema.sql`）

| 表 | 作用 | 关键点 |
|---|---|---|
| `store` | 门店 | `open_time` / `close_time` 决定可预约时段 |
| `user` | 普通用户 | `username` / `phone` 唯一；密码只存哈希 |
| `admin` | 管理员 | `store_id` 为 NULL = 超级管理员 |
| `card_type` | 卡种字典 | `kind` 区分储值 / 次卡 / 时长卡 |
| `seat` | 座位 | `(store_id, seat_no)` 唯一 |
| **`user_card`** | **用户持有的卡（账户）** | 余额 / 剩余次数 / 有效期 |
| `reservation` | 座位预约 | `uk_seat_slot` 唯一索引防抢座 |
| `recharge` | 充值购卡订单 | `order_no` 唯一索引做幂等 |

### 三个关键设计点

1. **`user_card` 是系统的枢纽**：充值让它加，预约让它减，退款让它回。
   它是"账户状态"，`recharge` 是"资金流水"——**两者成对才能对账**。
   （原方案只有 7 张表，缺的就是这张；没有它，"扣费逻辑"无处落地。）
2. **防抢座靠数据库，不靠代码判断**：
   唯一索引 `uk_seat_slot (seat_id, reserve_date, start_time, active_flag)`
   —— 同一个座位、同一天、同一个开始时间，只能有一条有效预约。
3. **取消预约时把 `active_flag` 置为 `NULL`**：
   MySQL 的 UNIQUE 索引允许多个 NULL，于是取消后该时段能被重新预约。
   （若只改成 `status='已取消'`，唯一键仍被占住，时段就永久约不了了。）

### 关系速查

```
store ──1:N──> seat          user ──1:N──> user_card ──N:1──> card_type
store ──1:N──> admin         user ──1:N──> recharge  ──N:1──> card_type
                             user ──1:N──> reservation ──N:1──> seat
                                                     └──N:1──> user_card
```

---

## 三、四条核心业务

📊 **图：[四条核心业务的事务流程](diagrams/03-业务流程与事务.html)**
📊 **图：[一次座位预约的完整调用链](diagrams/02-预约调用链.html)**
📊 **图：[预约状态流转](diagrams/04-预约状态机.html)**

| 业务 | 涉及表 | 需要事务吗 | 并发防线 |
|---|---|---|---|
| 注册 / 登录 | `user` | ❌ 单条 INSERT 本身原子 | 用户名 / 手机号唯一索引 |
| 充值购卡 | `recharge` + `user_card` | ✅ | `order_no` 唯一索引（防按钮双击重复下单） |
| 座位预约 | `reservation` + `user_card` | ✅ | `FOR UPDATE` 行锁 + `uk_seat_slot` 唯一索引 |
| 取消预约 | `reservation` + `user_card` | ✅ | `active_flag` 置 NULL 释放时段 |

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

## 五、⚠️ 待拍板的设计决策

> 下面这些**现在还是模糊的**。A 类不定，对应模块的代码就没法开工；B 类可以先按"当前假设"走，但要知道自己选了什么。

### A 类 · 不定就没法写代码（建议本周内开会定完）

| # | 问题 | 可选方案 | 影响 |
|---|---|---|---|
| **A1** | 「待使用」→「使用中」**谁推进**？ | ① 管理员在管理端手工签到<br>② 定时任务到点自动改状态<br>③ 不存状态，用 `NOW()` 与 `start_time/end_time` 比较算出来 | 选①要写管理端签到页；选②要写调度程序；选③可简化 `status` 字段 |
| **A2** | **超时未到**怎么算、扣不扣费？ | 迟到 30 分钟作废？整段作废？全额扣 / 部分扣 / 不扣？ | 决定"已失效"状态要不要、退款逻辑怎么写 |
| **A3** | **扣费规则**？ | ① 按小时 × `seat.price_per_hour` × `card_type.discount`<br>② 次卡按次扣（一次预约 = 1 次）<br>③ 时长卡扣剩余小时数 | 决定 `reservation.amount` 怎么算、service 里的计算函数签名 |
| **A4** | 用户有多张卡时**用哪张**？ | ① 预约时用户手选<br>② 系统按优先级自动选（先扣次卡，再扣余额） | 决定 ui 要不要加下拉框、`reserve()` 的参数 |
| **A5** | 同一用户同一时段**能约几个座位**？ | 只能 1 个 / 允许多个 | 若只能 1 个，需再加一条唯一约束 `uk_user_slot (user_id, reserve_date, start_time, active_flag)` |

### B 类 · 可先按当前假设走，但需知道选了它

| # | 事项 | 当前假设 | 若要改 |
|---|---|---|---|
| **B1** | 时段粒度 | **整点、最短 1 小时**（`start_time` 是 `TIME`） | 支持半小时：不用改表，写入时保证是 `xx:30:00` 即可；支持任意时间点：唯一索引判重会失效，需换方案 |
| **B2** | 管理员是否分店隔离 | `admin.store_id` 为 NULL = 超管，非 NULL = 只管本店 | 需要在 repository 查询里加门店过滤条件，否则管理员能看到别家店的数据 |
| **B3** | 是否真实对接支付 | **演示时模拟**（直接把订单改成已支付） | 真实对接要接微信/支付宝沙箱，工作量大 |
| **B4** | 密码哈希用什么 | 未定 | `bcrypt` 包（需加依赖）或标准库 `hashlib.pbkdf2_hmac`（零依赖）。定了要同步 `requirements.txt` |
| **B5** | 管理员建表方式 | **独立 `admin` 表**（沿用现有 `admin_repo.py`） | 也可改成 `user.role` 字段，省一套登录逻辑；但 `admin_repo.py` 就没必要了 |
| **B6** | 一个用户能否持多张卡 | **能**（`user_card` 独立表） | 若只想一人一卡可简化，但不建议——次卡与储值卡并存是常见需求 |

### C 类 · 还没建的东西

| 事项 | 现状 | 建议 |
|---|---|---|
| `ui/pages/stats/` 目录 | **不存在**（但 `services/stats_service.py` 已建） | 补目录，否则数据看板页面没地方放 |
| `.gitignore` | 缺 `.env` | 加一行，避免以后数据库密码被提交 |
| `README.md` | **0 字节** | 补上：怎么建库、怎么跑、模块边界、改表要通知谁 |
| `tests/` | 不存在 | 至少给 `services/` 写几个用例（如"余额不足时预约应失败"）。分层的最大好处就是能脱离界面测业务 |
| 统一异常 | 未定义 | 建议加 `core/exceptions.py`，定义 `BizError`，ui 统一 `except BizError` 显示红字 |
| 状态常量 | 散落 | 订单/预约状态集中定义，或直接用数据库 `ENUM` + Python `Enum` |

---

## 六、协作约定

1. **`db/sql/` 和 `repository/` 是全组公共依赖**。谁要改表结构，先在群里说，由**一个人**统一改，改完通知所有人。
2. `main` 分支保持可运行；功能开发在 `feature/xxx` 分支上做。
3. 提交前先 `git pull`，看到冲突按 [`开发流程.md`](开发流程.md) 处理。
4. **密码、密钥一律不进仓库**（`config.py` 里的密码后续要改成读环境变量或 `.env`）。
5. 数据库账号不要用 `root` 跑应用（正式一点可以建 `app_user` 并只授必要的权限）。
