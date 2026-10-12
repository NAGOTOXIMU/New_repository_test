-- =============================================================================
--  测试数据（最小可用版，可重复执行）
--  文件  : db/sql/03_seed.sql
--
--  ⚠️ 推荐用 Python 脚本灌数据，它会用 services/password.py 现算密码哈希，
--     保证和系统登录校验一致：
--         python -m db.seed --with-orders
--
--  本文件是「不想装 Python 依赖时」的纯 SQL 备用方案，只灌主数据，
--  不灌历史订单（历史订单含动态日期，SQL 里写不优雅，交给 db/seed.py）。
--
--  顺序：store → seat/admin → card_type → user → user_card
--  账号：用户手机号 13800000001，密码 123456；管理员 admin，密码 admin123
--        （哈希由 services/password.py 的 pbkdf2 生成，盐与 db/seed.py 输出一致）
-- =============================================================================

USE study_room_management;

-- ---------------------------------------------------------------------------
-- 1. 门店（2 家）
-- ---------------------------------------------------------------------------
INSERT INTO store (store_id, store_name, address, open_time, close_time, seat_count, status) VALUES
  (1, '旗舰店·市中心馆', '杭州市西湖区文三路 100 号 3 层', '08:00:00', '22:00:00', 6, 1),
  (2, '滨江分馆',       '杭州市滨江区江南大道 500 号 2 层', '09:00:00', '21:00:00', 4, 1)
ON DUPLICATE KEY UPDATE
  store_name=VALUES(store_name), address=VALUES(address),
  open_time=VALUES(open_time), close_time=VALUES(close_time),
  seat_count=VALUES(seat_count), status=VALUES(status);

-- ---------------------------------------------------------------------------
-- 2. 座位（门店1 六个、门店2 四个；area_type 1普通 2安静 3靠窗）
-- ---------------------------------------------------------------------------
INSERT INTO seat (seat_id, store_id, seat_code, area_type, has_socket, status) VALUES
  (1,  1, 'A01', 1, 1, 1),
  (2,  1, 'A02', 1, 1, 1),
  (3,  1, 'A03', 1, 0, 1),
  (4,  1, 'B01', 2, 1, 1),
  (5,  1, 'B02', 2, 1, 1),
  (6,  1, 'C01', 3, 1, 0),
  (7,  2, 'A01', 1, 1, 1),
  (8,  2, 'A02', 1, 0, 1),
  (9,  2, 'B01', 2, 1, 1),
  (10, 2, 'C01', 3, 1, 1)
ON DUPLICATE KEY UPDATE
  store_id=VALUES(store_id), seat_code=VALUES(seat_code), area_type=VALUES(area_type),
  has_socket=VALUES(has_socket), status=VALUES(status);

-- ---------------------------------------------------------------------------
-- 3. 管理员（admin = 超级管理员，无门店；ops1 = 旗舰店运营员）密码 admin123
-- ---------------------------------------------------------------------------
INSERT INTO admin (admin_id, username, password_hash, real_name, phone, store_id, role_type, status) VALUES
  (1, 'admin', '9Ns5LIJeZNSuApPzSJLPrg==$/IUA65r4doVKMnbrbYSCAZw2KkqCpdoMd3RMboljRZw=', '系统管理员', '13900000000', NULL, 2, 1),
  (2, 'ops1',  '9Ns5LIJeZNSuApPzSJLPrg==$/IUA65r4doVKMnbrbYSCAZw2KkqCpdoMd3RMboljRZw=', '王运营',     '13900000001', 1,    1, 1)
ON DUPLICATE KEY UPDATE
  password_hash=VALUES(password_hash), real_name=VALUES(real_name),
  phone=VALUES(phone), store_id=VALUES(store_id), role_type=VALUES(role_type), status=VALUES(status);

-- ---------------------------------------------------------------------------
-- 4. 卡种
--    kind：1时长卡 2次卡 3储值卡
--    时长卡 value = 分钟数；次卡 value = 次数；
--    储值卡 value 约定为「这张卡包含的小时数」，单价 = price ÷ value
--    （100 元 / 20 小时 = 5 元/小时，与 config.STORED_HOUR_RATE 一致）
-- ---------------------------------------------------------------------------
INSERT INTO card_type (card_type_id, card_name, kind, price, value, valid_days, status) VALUES
  (1, '10 小时时长卡', 1, 49.00,  600,  180, 1),
  (2, '30 小时时长卡', 1, 129.00, 1800, 365, 1),
  (3, '20 次卡',       2, 99.00,  20,   180, 1),
  (4, '100 元储值卡',  3, 100.00, 20,   365, 1)
ON DUPLICATE KEY UPDATE
  card_name=VALUES(card_name), kind=VALUES(kind), price=VALUES(price),
  value=VALUES(value), valid_days=VALUES(valid_days), status=VALUES(status);

-- ---------------------------------------------------------------------------
-- 5. 用户（phone 是唯一登录账号；密码 123456）
-- ---------------------------------------------------------------------------
INSERT INTO `user` (user_id, phone, password_hash, nickname, member_level, expire_time, status) VALUES
  (1, '13800000001', 'aCQGgAviDqn6IibiYF1oPg==$CwvDeF1hGrPRu/lpzl6TB4nt51qo6Rr/bPamX1mkCwk=', '小林', 1, '2027-10-12 23:59:59', 1),
  (2, '13800000002', 'aCQGgAviDqn6IibiYF1oPg==$CwvDeF1hGrPRu/lpzl6TB4nt51qo6Rr/bPamX1mkCwk=', '小张', 0, NULL, 1)
ON DUPLICATE KEY UPDATE
  password_hash=VALUES(password_hash), nickname=VALUES(nickname),
  member_level=VALUES(member_level), expire_time=VALUES(expire_time), status=VALUES(status);

-- ---------------------------------------------------------------------------
-- 6. 用户持卡实例（余额/次数/分钟挂在卡上；user 表是这张表的汇总）
-- ---------------------------------------------------------------------------
INSERT INTO user_card (card_id, card_no, user_id, card_type_id, balance, remaining_times,
                       remaining_minutes, expire_at, status) VALUES
  (1, 'C20261012AAAA0001', 1, 1, 0.00,   0, 600, '2027-04-10', 1),
  (2, 'C20261012AAAA0002', 1, 3, 0.00,  20,   0, '2027-04-10', 1),
  (3, 'C20261012AAAA0003', 2, 4, 100.00, 0,   0, '2027-10-12', 1)
ON DUPLICATE KEY UPDATE
  card_no=VALUES(card_no), user_id=VALUES(user_id), card_type_id=VALUES(card_type_id),
  balance=VALUES(balance), remaining_times=VALUES(remaining_times),
  remaining_minutes=VALUES(remaining_minutes), expire_at=VALUES(expire_at), status=VALUES(status);

-- ---------------------------------------------------------------------------
-- 7. 汇总冗余字段 + 门店座位数，全部按真实数据重算
-- ---------------------------------------------------------------------------
UPDATE `user` u SET
  u.balance = (SELECT IFNULL(SUM(uc.balance), 0.00) FROM user_card uc
               WHERE uc.user_id = u.user_id AND uc.status = 1
                 AND (uc.expire_at IS NULL OR uc.expire_at >= CURDATE())),
  u.remaining_hours = (SELECT IFNULL(FLOOR(SUM(uc.remaining_minutes) / 60), 0)
               FROM user_card uc
               WHERE uc.user_id = u.user_id AND uc.status = 1
                 AND (uc.expire_at IS NULL OR uc.expire_at >= CURDATE()));

UPDATE store s SET s.seat_count =
  (SELECT COUNT(*) FROM seat WHERE seat.store_id = s.store_id);

-- =============================================================================
-- 灌完自检：
--   SELECT 'store',COUNT(*) FROM store UNION ALL SELECT 'seat',COUNT(*) FROM seat
--   UNION ALL SELECT 'card_type',COUNT(*) FROM card_type
--   UNION ALL SELECT 'user',COUNT(*) FROM `user`
--   UNION ALL SELECT 'user_card',COUNT(*) FROM user_card
--   UNION ALL SELECT 'admin',COUNT(*) FROM admin;
-- 预期：2 / 10 / 4 / 2 / 3 / 2
--
-- 历史订单请执行： python -m db.seed --with-orders
-- =============================================================================
