--  索引核对
--  文件  : db/sql/02_indexes.sql
--
--  说明：所有索引（含《数据库规范》第 12 张图点名要求的 3 条联合索引）都已直接
--        写在 01_schema.sql 的 CREATE TABLE 里 —— 这样「建表即建索引」，
--        不存在「忘了执行第二个脚本」的风险，也不依赖 mysql 客户端的
--        DELIMITER 语法（db/init_db.py 用 PyMySQL 执行，不认 DELIMITER）。
--
--        所以本文件不再是"建索引脚本"，而是「索引核对清单」：
--        执行它会把当前库的索引列出来，方便和下面的期望值逐个对照。
--        可重复执行、可用 mysql 客户端执行、也可被 db/init_db.py 执行。
--
--  期望索引（★ = 规范第 12 张图明确要求）
--    store              PRIMARY, uk_store_name, idx_store_status
--    user               PRIMARY, uk_user_phone
--    admin              PRIMARY, uk_admin_username, idx_admin_store, idx_admin_status
--    card_type          PRIMARY, uk_cardtype_name
--    seat               PRIMARY, uk_seat_store_code, uk_seat_id_store, idx_seat_store_status
--    user_card          PRIMARY, uk_card_no, idx_uc_user_type, idx_uc_user_status_expire
--    reservation_order  PRIMARY, uk_reservation_no,
--                       ★ uk_seat_slot, ★ idx_res_store_date, ★ idx_res_user_status,
--                       idx_res_date_status, idx_res_card
--    recharge_order     PRIMARY, uk_recharge_no, ★ idx_ro_user_status,
--                       idx_ro_paytime, idx_ro_card

USE study_room_management;

SELECT
  TABLE_NAME      AS '表',
  INDEX_NAME      AS '索引名',
  CASE NON_UNIQUE WHEN 0 THEN '唯一' ELSE '普通' END AS '类型',
  GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX SEPARATOR ', ') AS '列（按顺序）'
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
GROUP BY TABLE_NAME, INDEX_NAME, NON_UNIQUE
ORDER BY TABLE_NAME, INDEX_NAME;
