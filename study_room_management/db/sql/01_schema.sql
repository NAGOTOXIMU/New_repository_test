--  共享自习室门店运营与会员管理系统 —— 建表脚本
--  文件    : db/sql/01_schema.sql
--  基准    : 《数据库规范》V1.0（study_room_management）
--  环境    : MySQL 8.0+ / InnoDB / utf8mb4 / utf8mb4_unicode_ci
--
--  表清单（8 张，按外键依赖顺序创建）：
--    store → user → admin → card_type → seat → user_card → reservation_order
--    → recharge_order
--
--  ⚠️ 与《数据库规范》的两处必要补充（原因见 db/sql/README.md「规范缺口补充」）：
--   1) 新增 user_card 用户持卡实例表
--      规范里 user_card 缺失，导致 card_type 的三种卡（时长卡/次卡/储值卡）
--      无处落账：user.balance / user.remaining_hours 只能表达「每用户一份」，
--      用户同时持多张卡时无法区分哪张卡有多少钱/多少次/多少分钟，
--      card_type.value 也没有表可以承接扣减。
--   2) reservation_order 增加 active_flag 与 uk_seat_slot 唯一约束
--      规范第 11 张图要求「条件判断 + 原子插入避免同一时段同座位重复预约」，
--      但只靠「先查再插」在并发下无法原子；必须由数据库唯一索引兜底。
--      取消预约时把 active_flag 置为 NULL，MySQL 唯一索引允许多个 NULL，
--      于是该时段被真正释放，用户可以重新预约。
--      ⚠️ V1.1 起唯一键补上了 end_time，并且业务层还加了座位级互斥锁，
--         原因和升级步骤见 db/sql/04_migrate_uk_seat_slot.sql。
--         已经建过库的机器必须执行那个迁移脚本，否则仍然是旧键。
--
--  维护者：全组公共依赖 —— 改表前必须在群里说，由一个人统一改，改完同步所有人

CREATE DATABASE IF NOT EXISTS study_room_management
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE study_room_management;

-- 按依赖倒序删除，保证脚本可重复执行
DROP TABLE IF EXISTS recharge_order;
DROP TABLE IF EXISTS reservation_order;
DROP TABLE IF EXISTS user_card;
DROP TABLE IF EXISTS seat;
DROP TABLE IF EXISTS card_type;
DROP TABLE IF EXISTS admin;
DROP TABLE IF EXISTS `user`;
DROP TABLE IF EXISTS store;


-- 1. 门店表 store
CREATE TABLE store (
  store_id    INT AUTO_INCREMENT PRIMARY KEY COMMENT '门店唯一ID',
  store_name  VARCHAR(100) NOT NULL COMMENT '门店名称',
  address     VARCHAR(255) NOT NULL COMMENT '门店地址',
  open_time   TIME NOT NULL COMMENT '每日开门时间',
  close_time  TIME NOT NULL COMMENT '每日关门时间',
  seat_count  INT NOT NULL DEFAULT 0 COMMENT '门店座位总数',
  status      TINYINT NOT NULL DEFAULT 1 COMMENT '营业状态：1营业中 0停业',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
              ON UPDATE CURRENT_TIMESTAMP COMMENT '最后修改时间',
  UNIQUE KEY uk_store_name (store_name),
  KEY idx_store_status (status),
  CONSTRAINT chk_store_seat_count CHECK (seat_count >= 0),
  CONSTRAINT chk_store_time       CHECK (close_time > open_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='自习室门店表';


-- 2. 用户表 user
--    phone 是唯一登录账号（规范规定）。
--    password_hash 存 pbkdf2 哈希，严禁存明文。
CREATE TABLE `user` (
  user_id       INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户唯一ID',
  phone         VARCHAR(20) NOT NULL COMMENT '手机号，唯一登录账号',
  password_hash VARCHAR(255) NOT NULL COMMENT '登录密码哈希，严禁存明文',
  nickname      VARCHAR(50) NOT NULL COMMENT '用户昵称',
  balance       DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '储值余额汇总（单位：元）',
  remaining_hours INT NOT NULL DEFAULT 0 COMMENT '剩余可用时长汇总（单位：分钟）',
  member_level  TINYINT NOT NULL DEFAULT 0 COMMENT '会员等级：0普通用户 1月卡会员 2季卡会员',
  expire_time   DATETIME NULL COMMENT '会员到期时间，NULL=未开通',
  create_time   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
  update_time   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP COMMENT '最后修改时间',
  status        TINYINT NOT NULL DEFAULT 1 COMMENT '账号状态：1正常 0禁用',
  UNIQUE KEY uk_user_phone (phone),
  CONSTRAINT chk_user_balance CHECK (balance >= 0),
  CONSTRAINT chk_user_hours   CHECK (remaining_hours >= 0),
  CONSTRAINT chk_user_status  CHECK (status IN (0,1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户会员表';


-- 3. 管理员表 admin
--    store_id 为 NULL 表示超级管理员（可管理所有门店）。
CREATE TABLE admin (
  admin_id      INT AUTO_INCREMENT PRIMARY KEY COMMENT '管理员唯一ID',
  username      VARCHAR(30) NOT NULL COMMENT '登录账号',
  password_hash VARCHAR(100) NOT NULL COMMENT '加密存储的密码',
  real_name     VARCHAR(50) NOT NULL COMMENT '姓名',
  phone         VARCHAR(20) NULL COMMENT '联系手机号',
  store_id      INT NULL COMMENT '负责的门店ID，NULL=超级管理员',
  role_type     TINYINT NOT NULL DEFAULT 1 COMMENT '角色类型：1普通运营员 2超级管理员',
  create_time   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '账号创建时间',
  status        TINYINT NOT NULL DEFAULT 1 COMMENT '账号状态：1正常 0禁用',
  UNIQUE KEY uk_admin_username (username),
  KEY idx_admin_store (store_id),
  KEY idx_admin_status (status),
  CONSTRAINT fk_admin_store FOREIGN KEY (store_id) REFERENCES store(store_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT chk_admin_role   CHECK (role_type IN (1,2)),
  CONSTRAINT chk_admin_status CHECK (status IN (0,1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='后台管理员表';


-- 4. 会员卡种表 card_type（字典表：卖什么卡）
--    kind=1 时长卡：value=分钟数   2 次卡：value=次数   3 储值卡
CREATE TABLE card_type (
  card_type_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '卡种唯一ID',
  card_name    VARCHAR(50) NOT NULL COMMENT '卡种名称，如日卡、月卡',
  kind         TINYINT NOT NULL COMMENT '卡类型：1时长卡 2次卡 3储值卡',
  price        DECIMAL(10,2) NOT NULL COMMENT '售价（单位：元）',
  value        INT NOT NULL DEFAULT 0 COMMENT '对应价值：时长卡为分钟数，次卡为次数，储值卡为0',
  valid_days   INT NOT NULL DEFAULT 365 COMMENT '有效期天数',
  status       TINYINT NOT NULL DEFAULT 1 COMMENT '上架状态：1上架 0下架',
  create_time  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
               ON UPDATE CURRENT_TIMESTAMP COMMENT '最后修改时间',
  UNIQUE KEY uk_cardtype_name (card_name),
  CONSTRAINT chk_cardtype_kind   CHECK (kind IN (1,2,3)),
  CONSTRAINT chk_cardtype_price  CHECK (price >= 0),
  CONSTRAINT chk_cardtype_value  CHECK (value >= 0),
  CONSTRAINT chk_cardtype_days   CHECK (valid_days > 0),
  CONSTRAINT chk_cardtype_status CHECK (status IN (0,1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会员卡产品配置表';


-- 5. 座位表 seat
--    area_type：1普通区 2安静区 3靠窗区
CREATE TABLE seat (
  seat_id    INT AUTO_INCREMENT PRIMARY KEY COMMENT '座位唯一ID',
  store_id   INT NOT NULL COMMENT '所属门店ID（外键）',
  seat_code  VARCHAR(20) NOT NULL COMMENT '座位编号，如A01、B05',
  area_type  TINYINT NOT NULL DEFAULT 1 COMMENT '区域类型：1普通区 2安静区 3靠窗区',
  has_socket TINYINT NOT NULL DEFAULT 1 COMMENT '是否带插座：1是 0否',
  status     TINYINT NOT NULL DEFAULT 1 COMMENT '座位状态：1可用 0维修中',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
              ON UPDATE CURRENT_TIMESTAMP COMMENT '最后修改时间',
  -- 同一门店内座位编号不允许重复
  UNIQUE KEY uk_seat_store_code (store_id, seat_code),
  -- 供 reservation_order 的复合外键 (seat_id, store_id) 使用，
  -- 从数据库层面保证「预约记录的门店 == 座位的门店」
  UNIQUE KEY uk_seat_id_store (seat_id, store_id),
  KEY idx_seat_store_status (store_id, status),
  CONSTRAINT fk_seat_store    FOREIGN KEY (store_id) REFERENCES store(store_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT chk_seat_area    CHECK (area_type IN (1,2,3)),
  CONSTRAINT chk_seat_socket  CHECK (has_socket IN (0,1)),
  CONSTRAINT chk_seat_status  CHECK (status IN (0,1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='座位信息表';


-- 6. 用户持卡实例表 user_card（规范缺口补充，核心账务表）
--
--    card_type 是「卖什么卡」的字典，user_card 是「用户实际持有的那张卡」，
--    余额 / 剩余次数 / 剩余分钟都挂在 user_card 上，才能按卡归属、按卡扣减。
--    user.balance / user.remaining_hours 是这张表的汇总冗余，便于列表页快速展示。
CREATE TABLE user_card (
  card_id           INT AUTO_INCREMENT PRIMARY KEY COMMENT '持卡实例ID',
  card_no           VARCHAR(32) NOT NULL COMMENT '卡号（业务唯一号）',
  user_id           INT NOT NULL COMMENT '持卡人ID（外键）',
  card_type_id      INT NOT NULL COMMENT '卡种ID（外键）',
  balance           DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '该卡储值余额（储值卡用，单位：元）',
  remaining_times   INT NOT NULL DEFAULT 0 COMMENT '该卡剩余次数（次卡用）',
  remaining_minutes INT NOT NULL DEFAULT 0 COMMENT '该卡剩余时长（时长卡用，单位：分钟）',
  expire_at         DATE NULL COMMENT '该卡到期日，NULL=永不过期',
  status            TINYINT NOT NULL DEFAULT 1 COMMENT '卡状态：1正常 0已冻结',
  create_time       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '开卡时间',
  update_time       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP COMMENT '最后修改时间',
  UNIQUE KEY uk_card_no (card_no),
  KEY idx_uc_user_type (user_id, card_type_id),
  KEY idx_uc_user_status_expire (user_id, status, expire_at),
  CONSTRAINT fk_uc_user FOREIGN KEY (user_id) REFERENCES `user`(user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_uc_type FOREIGN KEY (card_type_id) REFERENCES card_type(card_type_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT chk_uc_balance CHECK (balance >= 0),
  CONSTRAINT chk_uc_times   CHECK (remaining_times >= 0),
  CONSTRAINT chk_uc_minutes CHECK (remaining_minutes >= 0),
  CONSTRAINT chk_uc_status  CHECK (status IN (0,1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户持卡实例表（账户：余额/次数/时长）';


-- 7. 预约订单表 reservation_order（核心：座位 × 日期的时段占用）
--    order_status：1待使用 2进行中 3已完成 4已取消 5已过期
--    duration 单位：分钟
--
--    防重复预约靠 uk_seat_slot：
--      同一座位 + 同一日期 + 同一开始时间 + 同一结束时间，最多只能有一条「有效」预约。
--      ⚠️ 唯一索引只能精确去重，挡不住「部分重叠」（09:00~11:00 与 10:00~12:00
--         开始时间不同，唯一键判不出冲突）。所以真正防重叠有两道：
--         ① 服务层：order_service.reserve() 先取座位级咨询锁（GET_LOCK），
--            再查重叠，查完才插入 —— 同座位同时段的下单被串行化，见
--            repository/reservation_repo.lock_seat_slot() + seat_repo.has_active_reservation()
--         ② 数据库层：uk_seat_slot 兜底完全相同的时段（含客户端的重复提交）
--    取消时把 active_flag 置为 NULL —— MySQL 唯一索引允许多个 NULL，
--    于是「已取消」的记录不再占用时段，用户还能重新预约同一时段。
--    （普通方案做不到：改成 order_status=4 后唯一键仍被占住。）
CREATE TABLE reservation_order (
  order_id     INT AUTO_INCREMENT PRIMARY KEY COMMENT '预约订单唯一ID',
  order_no     VARCHAR(32) NOT NULL COMMENT '预约单号（幂等键）',
  user_id      INT NOT NULL COMMENT '预约用户ID（外键）',
  seat_id      INT NOT NULL COMMENT '预约座位ID（外键）',
  store_id     INT NOT NULL COMMENT '所属门店ID（外键）',
  card_id      INT NULL COMMENT '本次消费使用的持卡实例ID，NULL=免费/未扣费',
  reserve_date DATE NOT NULL COMMENT '预约日期',
  start_time   TIME NOT NULL COMMENT '预约开始时间',
  end_time     TIME NOT NULL COMMENT '预约结束时间',
  duration     INT NOT NULL COMMENT '预约时长（单位：分钟）',
  amount       DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '本次扣费金额',
  order_status TINYINT NOT NULL DEFAULT 1 COMMENT '订单状态：1待使用 2进行中 3已完成 4已取消 5已过期',
  active_flag  TINYINT NULL DEFAULT 1 COMMENT '1=占用时段；取消时置NULL以释放唯一索引',
  create_time  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '下单时间',
  update_time  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
               ON UPDATE CURRENT_TIMESTAMP COMMENT '最后修改时间',
  UNIQUE KEY uk_reservation_no (order_no),
  -- 防重复预约的唯一约束（并发安全的兜底防线；end_time 必须一起进键，
  -- 否则「同座位同开始时间但时长不同」的两条预约会被当成同一条而互相挡住）
  UNIQUE KEY uk_seat_slot (seat_id, reserve_date, start_time, end_time, active_flag),
  KEY idx_res_store_date (store_id, reserve_date, seat_id),
  KEY idx_res_user_status (user_id, order_status),
  -- 状态自动流转要按「日期 + 状态 + 开始时间」扫，见 reservation_repo.sync_time_status()。
  -- 列顺序取 (reserve_date, order_status, start_time)：前缀 (reserve_date, order_status)
  -- 正好覆盖原来 idx_res_date_status 的用法，所以两个索引合并成了一个。
  KEY idx_res_date_status (reserve_date, order_status, start_time),
  KEY idx_res_card (card_id),
  CONSTRAINT fk_res_user  FOREIGN KEY (user_id) REFERENCES `user`(user_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  -- 复合外键：门店必须确实是这个座位的门店，杜绝冗余字段写错
  CONSTRAINT fk_res_seat  FOREIGN KEY (seat_id, store_id) REFERENCES seat(seat_id, store_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_res_store FOREIGN KEY (store_id) REFERENCES store(store_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_res_card  FOREIGN KEY (card_id) REFERENCES user_card(card_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT chk_res_time     CHECK (end_time > start_time),
  CONSTRAINT chk_res_duration CHECK (duration > 0),
  CONSTRAINT chk_res_amount   CHECK (amount >= 0),
  CONSTRAINT chk_res_status   CHECK (order_status IN (1,2,3,4,5))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='座位预约订单表';


-- 8. 充值订单表 recharge_order（资金流水）
--    pay_status：0待支付 1已支付 2已退款
--    order_no 是幂等键：用户重复点击「提交」时靠它的唯一约束挡住重复下单。
--    card_type_id = 买的卡种；card_id = 支付成功后生成/累加的那张持卡实例。
CREATE TABLE recharge_order (
  recharge_id  INT AUTO_INCREMENT PRIMARY KEY COMMENT '充值订单唯一ID',
  order_no     VARCHAR(32) NOT NULL COMMENT '业务单号（幂等键）',
  user_id      INT NOT NULL COMMENT '用户ID（外键）',
  card_type_id INT NOT NULL COMMENT '购买卡种ID（外键）',
  card_id      INT NULL COMMENT '支付成功后生成/累加的持卡实例ID',
  amount       DECIMAL(10,2) NOT NULL COMMENT '实际支付金额',
  pay_status   TINYINT NOT NULL DEFAULT 0 COMMENT '支付状态：0待支付 1已支付 2已退款',
  pay_time     DATETIME NULL COMMENT '支付完成时间',
  create_time  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '订单创建时间',
  update_time  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
               ON UPDATE CURRENT_TIMESTAMP COMMENT '最后修改时间',
  UNIQUE KEY uk_recharge_no (order_no),
  KEY idx_ro_user_status (user_id, pay_status),
  KEY idx_ro_paytime (pay_time),
  KEY idx_ro_card (card_id),
  CONSTRAINT fk_ro_user FOREIGN KEY (user_id) REFERENCES `user`(user_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_ro_type FOREIGN KEY (card_type_id) REFERENCES card_type(card_type_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_ro_card FOREIGN KEY (card_id) REFERENCES user_card(card_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT chk_ro_amount CHECK (amount >= 0),
  CONSTRAINT chk_ro_status CHECK (pay_status IN (0,1,2))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户充值订单表';


-- 建表完成：8 张表
--   store / user / admin / card_type / seat / user_card / reservation_order
--   / recharge_order
--
-- 下一步：执行 02_indexes.sql 补查询索引，再执行 03_seed.sql 灌测试数据。
