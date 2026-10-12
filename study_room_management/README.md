# 自习室预约与会员管理系统

基于 **Python + Streamlit + MySQL** 的校园自习室预约平台，包含**用户端**、**商家管理端**、**运营数据看板**三套界面。

---

## 一、功能总览

### 用户端（C 端）

| 模块 | 功能 |
|---|---|
| 注册 / 登录 | 手机号注册、密码哈希存储、登录态管理 |
| 门店与座位 | 浏览门店列表、查看门店座位分布与价格 |
| 座位预约 | 选日期与时段（整点，可连选多时）、选择卡种结算、占用冲突检测 |
| 我的订单 | 查看预约记录、取消预约（自动退款并释放时段） |
| 会员充值 | 购买储值卡 / 次卡 / 时长卡，查看卡内余额与剩余次数 |

### 商家管理端（B 端）

| 模块 | 功能 |
|---|---|
| 门店与座位管理 | 门店信息维护、批量新增座位、座位状态（可用 / 维修 / 停用） |
| 卡种管理 | 卡种上架下架、设置售价 / 面值 / 有效期 / 折扣率 |
| 订单管理 | 查看预约订单与充值订单、推进订单状态 |
| 用户管理 | 用户列表、查看持仓与消费记录、账号冻结 / 解冻 |

### 运营数据看板

| 模块 | 功能 |
|---|---|
| 营业统计 | 日 / 月营收、充值金额、退款金额 |
| 座位分析 | 座位利用率、热门时段分布 |
| 会员分析 | 新增会员趋势、卡种销售分布 |

---

## 二、技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 界面 | Streamlit | 纯 Python 生成网页，不写 HTML / CSS / JS |
| 业务 | Python 3.14 | 纯函数，不依赖任何 Web 框架 |
| 数据访问 | PyMySQL + 手写 SQL | 全部参数化查询，`%s` 占位符 |
| 数据库 | MySQL 8.0 | InnoDB 引擎、utf8mb4 字符集 |

---

## 三、架构与目录

```
study_room_management/
├─ app.py                入口：登录态判断 + st.navigation 组装导航
├─ config.py             全局配置（数据库参数、业务常量）
├─ requirements.txt      依赖清单
├─ db/                   连接与事务工具
│  ├─ connection.py      连接获取（带缓存）
│  ├─ uow.py             事务上下文管理器
│  └─ sql/               建表 / 索引 / 测试数据脚本
├─ repository/           数据访问层：所有 SQL 只在这里
├─ services/             业务层：校验规则 + 事务边界
├─ ui/                   界面层：唯一认识 Streamlit 的地方
│  ├─ components.py      通用组件（权限断言、分页表格、错误提示）
│  ├─ login.py           登录 / 注册页
│  └─ pages/             各角色页面
└─ docs/                 设计文档与开发流程
```

**依赖方向（只能向下，不能反向、不能越级）**

```
ui/  →  services/  →  repository/  →  db/  →  MySQL
```

**三条铁律**

1. 只能向下调用，不能越级（`ui` 不准直接 `import repository`）
2. 不能反向依赖（`repository` 不准 `import services`；任何层不准 `import ui`）
3. `services/` 和 `repository/` 里绝不出现 `import streamlit`

---

## 四、数据模型

共 **8 张表**，建表脚本见 `db/sql/01_schema.sql`。

| 表 | 作用 |
|---|---|
| `store` | 门店 |
| `user` | 普通用户 |
| `admin` | 管理员 |
| `card_type` | 卡种字典 |
| `seat` | 座位 |
| `user_card` | 用户持有的卡（余额 / 剩余次数 / 有效期） |
| `reservation` | 座位预约 |
| `recharge` | 充值购卡订单 |

**三个关键设计**

- `user_card` 是**账户**，`recharge` 是**流水**，两者成对才能对账
- 防抢座靠唯一索引 `uk_seat_slot (seat_id, reserve_date, start_time, active_flag)`
- 取消预约时把 `active_flag` 置为 `NULL`，唯一索引才会释放该时段

---

## 五、核心业务规则

| 业务 | 是否用事务 | 并发防线 |
|---|---|---|
| 注册 / 登录 | 否（单表写本身原子） | 用户名 / 手机号唯一索引 |
| 充值购卡 | 是 | `order_no` 唯一索引（防按钮双击重复下单） |
| 座位预约 | 是 | `SELECT ... FOR UPDATE` 行锁 + `uk_seat_slot` 唯一索引 |
| 取消预约 | 是 | `active_flag` 置 `NULL` 释放时段 |

事务一律通过 `db/uow.py` 的 `with uow() as cur:` 打开，**边界在 `services/` 层**，不在 ui 也不在 repository。

---

## 六、快速开始

```bash
# 1. 建库建表（用 MySQL 客户端执行；sql 文件里会先建 study_room 库）
mysql -u root -p < db/sql/01_schema.sql

# 2. 灌入测试数据（可选，便于演示）
mysql -u root -p study_room < db/sql/03_seed.sql

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置数据库连接（密码放本地 .env，不进仓库）
copy .env.example .env
#    然后编辑 .env，把 DB_PASSWORD 改成你本机 MySQL 的密码

# 5. 启动
python -m streamlit run app.py
```

浏览器访问 `http://localhost:8501`。停止服务按 `Ctrl+C`。

> 注意：`ui/pages/` 下的页面**不会被 Streamlit 自动发现**，必须在 `app.py` 里用 `st.Page()` 显式注册。

---

## 七、文档

| 文档 | 内容 |
|---|---|
| `docs/DESIGN.md` | 分层设计、数据模型、业务流程、**待拍板决策清单**、协作约定 |
| `docs/开发流程.md` | VS Code + GitHub 的拉取 / 编写 / 提交 / 推送操作 |

---

## 八、开发约定

1. `db/sql/` 和 `repository/` 是全组公共依赖 —— 改表结构前先在群里说，由一个人统一改，改完通知所有人
2. 提交前先 `git pull`，冲突处理见 `docs/开发流程.md`
3. 密码、密钥一律不进仓库
4. 应用不要用 `root` 账号连数据库（正式环境另建 `app_user` 并只授必要权限）
