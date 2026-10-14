--  迁移：修补 uk_seat_slot 唯一键
--  文件  : db/sql/04_migrate_uk_seat_slot.sql
--  适用  : 已经建过库、库里有数据的机器（新库直接跑 01_schema.sql 就带新键，不需要本文件）
--  执行  : python -m db.init_db --migrate
--          或者 mysql 客户端： mysql -u root -p < db/sql/04_migrate_uk_seat_slot.sql
--  可重复执行？不是完全幂等 —— 第二次执行会因为「索引不存在」报错，看到
--           "Can't DROP 'uk_seat_slot'" 说明已经迁移过了，不用管。
--
--  ── 为什么要改 ──────────────────────────────────────────────
--  旧键：uk_seat_slot (seat_id, reserve_date, start_time, active_flag)
--  新键：uk_seat_slot (seat_id, reserve_date, start_time, end_time, active_flag)
--  顺带：idx_res_date_status 扩成 (reserve_date, order_status, start_time)
--        （多出的 start_time 供订单状态自动流转使用，前缀没变所以旧查询照旧走它）
--
--  旧键的问题是它**把 end_time 排除在键外**：同一个座位、同一天、同一个
--  开始时间但**时长不同**的两条预约（比如 09:00~10:00 和 09:00~11:00）
--  会被唯一键当成「同一条」而互相挡住 —— 用户明明选的是不同时长，
--  却收到「这个时段刚刚被别人约走了」，属于误挡。
--
--  ⚠️ 新旧键都**挡不住部分重叠**（09:00~11:00 与 10:00~12:00 开始时间不同，
--     唯一索引判不出冲突）。所以真正的防重叠靠业务层：
--         order_service.reserve() 里先取座位级互斥锁（GET_LOCK），
--         再查一次重叠，最后才 INSERT。
--     本迁移只是把「完全相同 / 开始时间相同」这一层的键修正确。
--     详见 docs/DESIGN.md 的「并发防线」一节。
--
--  ⚠️ 本文件会 DROP 再 ADD 索引。加唯一键时如果库里有重复的
--     (seat_id, reserve_date, start_time, end_time) 有效预约，ADD 会直接失败，
--     这是**故意的**：数据没清理干净就不该加上唯一键。
--     先跑下面第 1 步的预检查询，把冲突处理掉再迁移。
-- ────────────────────────────────────────────────────────────

USE study_room_management;

-- 第 1 步 · 预检（把本段取消注释后单独执行；有结果行就说明有冲突，先处理再迁移）
--   ① 会撞新唯一键的重复时段（同一座位/日期/开始/结束，有多条有效预约）
-- SELECT seat_id, reserve_date, start_time, end_time, COUNT(*) AS n
--   FROM reservation_order
--  WHERE active_flag IS NOT NULL
--  GROUP BY seat_id, reserve_date, start_time, end_time
-- HAVING n > 1;
--
--   ② 部分重叠（唯一键挡不住，但业务上仍然是抢座，建议一并清理）
-- SELECT a.order_id AS 订单A, b.order_id AS 订单B, a.seat_id,
--        a.reserve_date, a.start_time AS A起, a.end_time AS A止,
--        b.start_time AS B起, b.end_time AS B止
--   FROM reservation_order a
--   JOIN reservation_order b
--     ON a.seat_id = b.seat_id AND a.reserve_date = b.reserve_date
--    AND a.order_id < b.order_id
--  WHERE a.active_flag IS NOT NULL AND b.active_flag IS NOT NULL
--    AND a.start_time < b.end_time AND a.end_time > b.start_time;
--
--   处理办法二选一：把多余的那条改掉
--     UPDATE reservation_order SET order_status = 4, active_flag = NULL
--      WHERE order_id = <要作废的订单ID>;
--   或者直接删掉（测试数据才建议删）：
--     DELETE FROM reservation_order WHERE order_id = <订单ID>;

-- 第 2 步 · 换键（真正的迁移）
ALTER TABLE reservation_order DROP INDEX uk_seat_slot;
ALTER TABLE reservation_order
  ADD UNIQUE KEY uk_seat_slot (seat_id, reserve_date, start_time, end_time, active_flag);

-- 第 2b 步 · 索引合并：把 idx_res_date_status 扩成 (reserve_date, order_status, start_time)
--   多出来的 start_time 供「按当前时间自动流转订单状态」用
--   （reservation_repo.sync_time_status()）；前缀 (reserve_date, order_status) 不变，
--   所以原来按日期 + 状态筛订单的查询照旧走这个索引，不需要单独再加索引。
ALTER TABLE reservation_order DROP INDEX idx_res_date_status;
ALTER TABLE reservation_order
  ADD KEY idx_res_date_status (reserve_date, order_status, start_time);

-- 第 3 步 · 自检：应看到新键的 5 列，且 active_flag 在最后
SELECT INDEX_NAME      AS '索引名',
       CASE NON_UNIQUE WHEN 0 THEN '唯一' ELSE '普通' END AS '类型',
       GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX SEPARATOR ', ') AS '列（按顺序）'
  FROM information_schema.STATISTICS
 WHERE TABLE_SCHEMA = DATABASE()
   AND TABLE_NAME = 'reservation_order'
   AND INDEX_NAME IN ('uk_seat_slot', 'idx_res_date_status')
 GROUP BY INDEX_NAME, NON_UNIQUE;

-- 第 4 步 · 自检：这条语句应该被新键挡下来（报 Duplicate entry for key 'uk_seat_slot'）
--   验证完记得把测试行删掉。先在库里找一条真实预约，把下面三个值换成它的。
-- INSERT INTO reservation_order
--   (order_no, user_id, seat_id, store_id, reserve_date, start_time, end_time, duration)
-- VALUES
--   (CONCAT('MIGTEST', UNIX_TIMESTAMP()), 1, 1, 1, CURDATE(), '09:00:00', '10:00:00', 60);


--  ── 可选：写成存储过程，重复执行不报错 ──────────────────────
--  如果你的 MySQL 用户没有 CREATE ROUTINE 权限就用上面的两步版。
--  注意：db/init_db.py 用 PyMySQL 执行，不认 mysql 客户端的 DELIMITER，
--  所以要把下面整段拷到 mysql 客户端里执行。
--
-- DROP PROCEDURE IF EXISTS migrate_uk_seat_slot;
-- DELIMITER $$
-- CREATE PROCEDURE migrate_uk_seat_slot()
-- BEGIN
--   IF EXISTS (SELECT 1 FROM information_schema.STATISTICS
--               WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'reservation_order'
--                 AND INDEX_NAME = 'uk_seat_slot'
--                 AND COLUMN_NAME = 'end_time') THEN
--     SELECT '已经是新键，无需迁移' AS 结果;
--   ELSE
--     ALTER TABLE reservation_order DROP INDEX uk_seat_slot;
--     ALTER TABLE reservation_order
--       ADD UNIQUE KEY uk_seat_slot (seat_id, reserve_date, start_time, end_time, active_flag);
--     SELECT '迁移完成' AS 结果;
--   END IF;
-- END$$
-- DELIMITER ;
-- CALL migrate_uk_seat_slot();
-- DROP PROCEDURE migrate_uk_seat_slot;
