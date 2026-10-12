# 自习室预约与会员管理系统

基于 **Python + Streamlit + MySQL** 的校园自习室预约平台，包含**用户端**、**商家管理端**、**运营数据看板**三套界面。

> 数据库以《数据库规范》V1.0 为基准，落地对照表与规范缺口补充见
> [`docs/数据库规范落地对照与缺口补充.md`](docs/数据库规范落地对照与缺口补充.md)。

---

## 一、功能总览

### 用户端（C 端）

| 模块 | 功能 |
|---|---|
| 注册 / 登录 | **手机号**注册、pbkdf2 密码哈希存储、登录态管理 |
| 门店与座位 | 浏览门店列表、查看门店座位分布与区域/插座信息 |
| 座位预约 | 选日期与时段（整点，可连选多时）、选择卡种结算、占用冲突检测 |
| 我的订单 | 查看预约记录、取消预约（自动退回权益并释放时段） |
| 会员充值 | 购买时长卡 / 次卡 / 储值卡，查看每张卡的余额、剩余次数与剩余时长 |

### 商家管理端（B 端）

| 模块 | 功能 |
|---|---|
| 门店与座位管理 | 门店维护、批量新增座位、座位状态（可用 / 维修中） |
| 卡种管理 | 卡种增改、上架下架、设置售价 / 对应价值 / 有效期 |
| 订单管理 | 预约订单与充值订单列表（按门店 / 状态筛选）、推进预约状态、退款 |
| 用户管理 | 用户列表与搜索、查看持卡与消费记录、账号禁用 / 解禁 |
| 运营看板 | 营收趋势、卡种销售分布、新增会员趋势、热门时段、座位利用率 |

---

## 二、技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 界面 | Streamlit | 纯 Python 生成网页，不写 HTML / CSS / JS |
| 业务 | Python 3.10+ | 纯函数，不依赖任何 Web 框架 |
| 数据访问 | PyMySQL + 手写 SQL | 全部参数化查询，`%s` 占位符 |
| 数据库 | MySQL 8.0 | InnoDB 引擎、utf8mb4 / utf8mb4_unicode_ci |

---

## 三、架构与目录

```
study_room_management/
├─ app.py                入口：登录态判断 + 按角色组装导航
├─ config.py             全局配置（数据库参数、业务常量、枚举取值）
├─ requirements.txt      依赖清单
├─ db/                   连接与事务工具
│  ├─ connection.py      连接获取、read_cursor / write_cursor
│  ├─ uow.py             事务上下文管理器
│  ├─ init_db.py         一键建库建表（执行 sql/ 下的脚本）
│  ├─ seed.py            灌测试数据（用项目自己的密码哈希算法）
│  └─ sql/               01_schema.sql / 02_indexes.sql / 03_seed.sql
├─ repository/           数据访问层：所有 SQL 只在这里
├─ services/             业务层：校验规则 + 事务边界
├─ ui/                   界面层：唯一认识 Streamlit 的地方
│  ├─ components.py      通用组件（身份信息、权限断言、状态名映射）
│  ├─ login.py           用户登录 / 管理员登录 / 注册
│  └─ pages/             各角色页面（user/ 与 admin/）
└─ docs/                 设计文档、接口速查、规范落地对照
```

**依赖方向（只能向下，不能反向、不能越级）**

```
ui/  →  services/  →  repository/  →  db/  →  MySQL
```

**三条铁律**

1. 只能向下调用，不能越级（`ui` 不准直接 `import repository`）
2. 不能反向依赖（`repository` 不准 `import services`；任何层不准 `import ui`）
3. `services/` 和 `repository/` 里绝不出现 `import streamlit`

> 唯一一处例外说明：`services/user_service.py` 为了校验旧密码而直接用了 `db.connection.read_cursor`（只读一条 SQL）。若严格禁止越级，可把这段挪进 `user_repo`。

---

## 四、数据模型

共 **8 张表**，建表脚本见 `db/sql/01_schema.sql`。

| 表 | 作用 | 关键点 |
|---|---|---|
| `store` | 门店 | `open_time` / `close_time` 决定可预约时段 |
| `user` | 普通用户 | **`phone` 唯一登录账号**；`balance`/`remaining_hours` 是汇总冗余 |
| `admin` | 管理员 | `store_id` 为 NULL = 超级管理员 |
| `card_type` | 卡种字典 | `kind` 1时长卡 / 2次卡 / 3储值卡；`value` 是"对应价值" |
| `seat` | 座位 | `(store_id, seat_code)` 唯一；`area_type` 1普通/2安静/3靠窗 |
| `user_card` | **用户持卡实例（账户）** | 余额 / 剩余次数 / 剩余分钟按**卡**归属 |
| `reservation_order` | 座位预约 | `uk_seat_slot` 唯一索引防抢座 |
| `recharge_order` | 充值购卡订单 | `order_no` 唯一索引做幂等 |

**规范里没有 `user_card`** —— 这是为补齐规范逻辑缺口而新增的表，
原因见 [`docs/数据库规范落地对照与缺口补充.md`](docs/数据库规范落地对照与缺口补充.md) 的「缺口 1」。

**四个关键设计**

- `user_card` 是**账户**，`recharge_order` 是**流水**，两者成对才能对账
- 防抢座靠唯一索引 `uk_seat_slot (seat_id, reserve_date, start_time, active_flag)`
- 取消预约时把 `active_flag` 置为 `NULL`，唯一索引才会释放该时段
- `(seat_id, store_id)` 复合外键，杜绝"预约记录的门店 ≠ 座位的门店"

---

## 五、核心业务规则

| 业务 | 是否用事务 | 并发防线 |
|---|---|---|
| 注册 / 登录 | 否（单表写本身原子） | `phone` 唯一索引 |
| 充值购卡 | 是 | `order_no` 唯一索引（防按钮双击重复下单） |
| 座位预约 | 是 | `uk_seat_slot` 唯一索引 + `SELECT ... FOR UPDATE` 锁卡 |
| 取消预约 | 是 | `active_flag` 置 `NULL` 释放时段，权益原路退回 |
| 退款 | 是 | `pay_status=1 → 2` 的条件更新；权益已被消费则拒绝 |

### 计费口径

| 卡类型 | 扣减方式 |
|---|---|
| 时长卡 `kind=1` | 每次预约扣 `duration` 分钟；`value` = 总分钟数 |
| 次卡 `kind=2` | 每次预约扣 1 次；`value` = 总次数 |
| 储值卡 `kind=3` | 扣 `小时单价 × 小时数`（不足 1 小时按 1 小时取整）；小时单价 = `price ÷ value`（`value` 约定为"卡内包含的小时数"），`value=0` 时用 `config.STORED_HOUR_RATE` 兜底 |

事务一律通过 `db/uow.py` 的 `with uow() as cur:` 打开，**边界在 `services/` 层**，不在 ui 也不在 repository。

---

## 六、快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置数据库连接（密码放本地 .env，不进仓库）
copy .env.example .env
#    然后编辑 .env，把 DB_PASSWORD 改成你本机 MySQL 的密码

# 3. 建库建表 + 建索引 + 灌测试数据（一条命令搞定）
python -m db.init_db --with-seed --yes
python -m db.seed --with-orders      # 补历史订单，供数据看板演示

# 4. 启动
python -m streamlit run app.py
```

浏览器访问 `http://localhost:8501`。停止服务按 `Ctrl+C`。

### 也可以用 MySQL 客户端手工执行

```bash
mysql -u root -p < db/sql/01_schema.sql
mysql -u root -p < db/sql/02_indexes.sql
mysql -u root -p study_room_management < db/sql/03_seed.sql
```

> `db/sql/03_seed.sql` 只灌主数据（门店/座位/卡种/用户/卡/管理员）；
> 历史订单含动态日期，用 `python -m db.seed --with-orders` 灌更合适。

### 测试账号

| 角色 | 账号 | 密码 |
|---|---|---|
| 用户 | 手机号 `13800000001` / `13800000002` | `123456` |
| 超级管理员 | `admin` | `admin123` |
| 门店运营员 | `ops1` | `admin123` |

> 注意：`ui/pages/` 下的页面**不会被 Streamlit 自动发现**，必须在 `app.py` 里用 `st.Page()` 显式注册。

---

## 七、文档

| 文档 | 内容 |
|---|---|
| `docs/数据库规范落地对照与缺口补充.md` | **规范逐条对照表、5 处规范缺口补充、验收 SQL、口径变更说明** |
| `docs/DESIGN.md` | 分层设计、数据模型、业务流程、待拍板决策清单、协作约定 |
| `docs/接口速查.md` | repository / services 函数签名速查 |
| `docs/开发流程.md` | VS Code + GitHub 的拉取 / 编写 / 提交 / 推送操作 |

---

## 八、开发约定

1. `db/sql/` 和 `repository/` 是全组公共依赖 —— 改表结构前先在群里说，由一个人统一改，改完通知所有人
2. **改了表结构，必须同步更新 `docs/数据库规范落地对照与缺口补充.md`**
3. 提交前先 `git pull`，冲突处理见 `docs/开发流程.md`
4. 密码、密钥一律不进仓库（`.env` 已在 `.gitignore` 里）
5. 应用不要用 `root` 账号连数据库（正式环境另建 `app_user` 并只授必要权限）
