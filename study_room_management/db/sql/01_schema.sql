-- =============================================================================
--  自习室预约与会员管理系统 —— 建表脚本
--  文件    : db/sql/01_schema.sql
--  环境    : MySQL 8.0+ / InnoDB / utf8mb4
--  说明    : 共 8 张表。表之间有外键依赖，必须按本文件顺序执行。
--            普通索引（性能优化）放在 02_indexes.sql，本文件只含主键与唯一约束。
--  维护者  : 全组公共依赖 —— 改表前必须在群里说，由一个人统一改，改完同步给所有人
-- =============================================================================

CREATE DATABASE IF NOT EXISTS study_room
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE study_room;

-- 按依赖倒序删除，保证脚本可以重复执行
DROP TABLE IF EXISTS recharge;
DROP TABLE IF EXISTS reservation;
DROP TABLE IF EXISTS user_card;
DROP TABLE IF EXISTS seat;
DROP TABLE IF EXISTS admin;
DROP TABLE IF EXISTS card_type;
DROP TABLE IF EXISTS store;
DROP TABLE IF EXISTS `user`;


-- =============================================================================
-- 1. 门店表
-- =============================================================================
CREATE TABLE store (
  store_id    INT AUTO_INCREMENT PRIMARY KEY COMMENT '门店ID',
  name        VARCHAR(100) NOT NULL            COMMENT '门店名称',
  address     VARCHAR(255) NOT NULL            COMMENT '详细地址',
  phone       VARCHAR(20)                      COMMENT '联系电话',
  open_time   TIME NOT NULL DEFAULT '08:00:00' COMMENT '营业开始时间',
  close_time  TIME NOT NULL DEFAULT '22:00:00' COMMENT '营业结束时间',
  status      ENUM('营业','停业') NOT NULL DEFAULT '营业',
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_store_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='门店表';


-- =============================================================================
-- 2. 用户表
--    password 一律存哈希（bcrypt / pbkdf2），严禁存明文
-- =============================================================================
CREATE TABLE `user` (
  user_id     INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
  username    VARCHAR(50)  NOT NULL COMMENT '登录名',
  password    VARCHAR(255) NOT NULL COMMENT '密码哈希，严禁存明文',
  real_name   VARCHAR(50)  NOT NULL COMMENT '真实姓名',
  phone       VARCHAR(20)  NOT NULL COMMENT '手机号',
  email       VARCHAR(100)          COMMENT '邮箱',
  status      ENUM('正常','冻结') NOT NULL DEFAULT '正常' COMMENT '账号状态',
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_user_username (username),
  UNIQUE KEY uk_user_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';


-- =============================================================================
-- 3. 管理员表
--    store_id 为 NULL 表示超级管理员（可管理所有门店）
-- =============================================================================
CREATE TABLE admin (
  admin_id    INT AUTO_INCREMENT PRIMARY KEY COMMENT '管理员ID',
  username    VARCHAR(50)  NOT NULL COMMENT '登录名',
  password    VARCHAR(255) NOT NULL COMMENT '密码哈希',
  real_name   VARCHAR(50)  NOT NULL COMMENT '姓名',
  phone       VARCHAR(20)           COMMENT '手机号',
  store_id    INT NULL              COMMENT '负责的门店，NULL=超级管理员',
  status      ENUM('正常','停用') NOT NULL DEFAULT '正常',
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_admin_username (username),
  CONSTRAINT fk_admin_store FOREIGN KEY (store_id) REFERENCES store(store_id)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='管理员表';


-- =============================================================================
-- 4. 卡种表（字典表：卖什么卡）
-- =============================================================================
CREATE TABLE card_type (
  card_type_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '卡种ID',
  name         VARCHAR(50) NOT NULL COMMENT '卡种名称，如"100元储值卡"',
  kind         ENUM('储值','次卡','时长卡') NOT NULL DEFAULT '储值' COMMENT '计费方式',
  price        DECIMAL(10,2) NOT NULL COMMENT '售价（用户实付）',
  face_value   DECIMAL(10,2) NULL COMMENT '到账金额（储值卡用）',
  total_times  INT NULL COMMENT '总次数（次卡用）',
  total_hours  INT NULL COMMENT '总时长小时（时长卡用）',
  valid_days   INT NOT NULL DEFAULT 365 COMMENT '有效期天数',
  discount     DECIMAL(3,2) NOT NULL DEFAULT 1.00 COMMENT '折扣率，1.00=不打折',
  status       ENUM('上架','下架') NOT NULL DEFAULT '上架',
  created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_cardtype_name (name),
  CONSTRAINT chk_cardtype_price    CHECK (price >= 0),
  CONSTRAINT chk_cardtype_discount CHECK (discount > 0 AND discount <= 1),
  CONSTRAINT chk_cardtype_days     CHECK (valid_days > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='卡种字典表';


-- =============================================================================
-- 5. 座位表
-- =============================================================================
CREATE TABLE seat (
  seat_id        INT AUTO_INCREMENT PRIMARY KEY COMMENT '座位ID',
  store_id       INT NOT NULL COMMENT '所属门店',
  seat_no        VARCHAR(20) NOT NULL COMMENT '座位编号，如 A01',
  zone           VARCHAR(50) NULL  COMMENT '区域，如 静音区/讨论区',
  price_per_hour DECIMAL(8,2) NOT NULL DEFAULT 0.00 COMMENT '原价（元/小时）',
  status         ENUM('可用','维修','停用') NOT NULL DEFAULT '可用',
  created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_seat (store_id, seat_no),
  CONSTRAINT fk_seat_store FOREIGN KEY (store_id) REFERENCES store(store_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT chk_seat_price CHECK (price_per_hour >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='座位表';


-- =============================================================================
-- 6. 用户卡表（★ 核心：用户持有的"账户"）
--    充值使 balance / remaining_times 增加，预约消费使其减少。
--    这张表是"账户状态"，recharge 表是"资金流水"，两者成对才能对账。
-- =============================================================================
CREATE TABLE user_card (
  card_id         INT AUTO_INCREMENT PRIMARY KEY COMMENT '卡ID',
  card_no         VARCHAR(32) NOT NULL COMMENT '卡号',
  user_id         INT NOT NULL COMMENT '持卡人',
  card_type_id    INT NOT NULL COMMENT '卡种',
  balance         DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '储值余额',
  remaining_times INT NULL COMMENT '剩余次数（次卡）',
  remaining_hours INT NULL COMMENT '剩余时长小时（时长卡）',
  expire_at       DATE NULL COMMENT '到期日，NULL=永不过期',
  status          ENUM('正常','冻结','已过期','已用完') NOT NULL DEFAULT '正常',
  created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_card_no (card_no),
  CONSTRAINT fk_card_user FOREIGN KEY (user_id) REFERENCES `user`(user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_card_type FOREIGN KEY (card_type_id) REFERENCES card_type(card_type_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT chk_card_balance CHECK (balance >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户持有的卡（账户：余额/次数/时长）';


-- =============================================================================
-- 7. 预约表（★ 核心：座位 × 日期的时段占用）
--
--    防重复预约靠这条唯一约束：uk_seat_slot
--    同一个座位、同一天、同一个开始时间，最多只能有一条"有效"预约。
--
--    取消预约时把 active_flag 置为 NULL —— MySQL 的 UNIQUE 索引允许多个 NULL，
--    于是"已取消"的记录不再占用时段，用户还能重新预约同一时段。
--    （普通方案做不到这一点：改成 status='已取消' 后唯一键仍然会被占住。）
-- =============================================================================
CREATE TABLE reservation (
  reservation_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '预约ID',
  order_no       VARCHAR(32) NOT NULL COMMENT '预约单号（业务唯一号）',
  user_id        INT NOT NULL COMMENT '预约人',
  seat_id        INT NOT NULL COMMENT '预约座位',
  card_id        INT NULL COMMENT '本次消费使用的卡',
  reserve_date   DATE NOT NULL COMMENT '预约日期',
  start_time     TIME NOT NULL COMMENT '开始时间（整点）',
  end_time       TIME NOT NULL COMMENT '结束时间',
  hours          INT  NOT NULL DEFAULT 1 COMMENT '时长（小时）',
  amount         DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '实际扣费金额',
  status         ENUM('待使用','使用中','已完成','已取消') NOT NULL DEFAULT '待使用',
  active_flag    TINYINT NULL DEFAULT 1 COMMENT '1=占用时段；取消时置NULL以释放唯一索引',
  created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_reservation_no (order_no),
  UNIQUE KEY uk_seat_slot (seat_id, reserve_date, start_time, active_flag),
  CONSTRAINT fk_res_user FOREIGN KEY (user_id) REFERENCES `user`(user_id) ON UPDATE CASCADE,
  CONSTRAINT fk_res_seat FOREIGN KEY (seat_id) REFERENCES seat(seat_id)   ON UPDATE CASCADE,
  CONSTRAINT fk_res_card FOREIGN KEY (card_id) REFERENCES user_card(card_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT chk_res_time   CHECK (end_time > start_time),
  CONSTRAINT chk_res_hours  CHECK (hours > 0),
  CONSTRAINT chk_res_amount CHECK (amount >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='座位预约表';


-- =============================================================================
-- 8. 充值 / 购卡订单表（资金流水）
--    order_no 是幂等键：用户重复点击"提交"时，靠它的唯一约束挡住重复下单。
-- =============================================================================
CREATE TABLE recharge (
  recharge_id  INT AUTO_INCREMENT PRIMARY KEY COMMENT '充值订单ID',
  order_no     VARCHAR(32) NOT NULL COMMENT '业务单号（幂等键）',
  user_id      INT NOT NULL COMMENT '用户',
  card_type_id INT NOT NULL COMMENT '购买的卡种',
  card_id      INT NULL COMMENT '支付成功后生成的卡',
  amount       DECIMAL(10,2) NOT NULL COMMENT '实付金额',
  pay_method   ENUM('微信','支付宝','现金','银行卡') NOT NULL DEFAULT '微信',
  status       ENUM('待支付','已支付','已取消','已退款') NOT NULL DEFAULT '待支付',
  paid_at      DATETIME NULL COMMENT '支付完成时间',
  created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_recharge_no (order_no),
  CONSTRAINT fk_recharge_user FOREIGN KEY (user_id) REFERENCES `user`(user_id) ON UPDATE CASCADE,
  CONSTRAINT fk_recharge_type FOREIGN KEY (card_type_id) REFERENCES card_type(card_type_id)
    ON UPDATE CASCADE,
  CONSTRAINT fk_recharge_card FOREIGN KEY (card_id) REFERENCES user_card(card_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT chk_recharge_amount CHECK (amount >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='充值/购卡订单表';


-- =============================================================================
-- 建表完成：8 张表
--   store / `user` / admin / card_type / seat / user_card / reservation / recharge
--
-- 下一步：执行 02_indexes.sql 建查询索引，再执行 03_seed.sql 灌测试数据。
-- =============================================================================
