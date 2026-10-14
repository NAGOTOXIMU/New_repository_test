"""一键建库建表：执行 db/sql/ 下的 SQL 脚本。

用法（在项目根目录 study_room_management 下执行）：

    python -m db.init_db               # 只建库建表（会先提示确认）
    python -m db.init_db --yes         # 跳过确认
    python -m db.init_db --with-seed   # 连索引和测试数据一起灌
    python -m db.init_db --migrate     # 只对存量库做结构迁移（不动数据，不 DROP 表）

为什么用它而不是 mysql 命令行：
    - 复用 .env 里的密码，不用在命令行里再输一遍
    - 组员的机器上不一定配好了 mysql.exe 的 PATH
        然后编辑 .env，把 DB_PASSWORD 改成你本机 MySQL 的密码
    - 可重复执行（脚本里都是 IF NOT EXISTS / DROP TABLE IF EXISTS / ON DUPLICATE KEY）

注意：连接时【不指定 database】——因为库可能还不存在。

⚠️ --migrate 和上面的建表是两回事：
    01_schema.sql 是先 DROP 再 CREATE，会把数据清空；
    --migrate 只对**已有数据的库**做结构升级（例如换 uk_seat_slot 唯一键），
    不清数据。已经建过库的机器升级代码后必须跑它，否则库结构还是旧的。

🌐 云端部署（Streamlit Cloud + 公网 MySQL）：
    设了 DB_HOST 环境变量 = 云端模式。此时：
      · 脚本里的 CREATE DATABASE / USE 会被自动剔掉（云端实例通常不允许），
        改为在连接时用 database= 参数指定目标库；
      · 目标库不存在会尝试自动建一次，失败则给出手工建库指引。
    连接信息来源（按优先级）：环境变量 → st.secrets → `.streamlit/secrets.toml`
    → 项目根目录 `.env`。所以在本地也能先写好 secrets.toml 再初始化云库。
"""
import os
import re
import sys
from pathlib import Path

import pymysql
from pymysql.constants import CLIENT

from config import DB_CONFIG

SQL_DIR = Path(__file__).resolve().parent / "sql"

# 建表脚本（先 DROP 再 CREATE，会清空数据）
BUILD_FILES = ["01_schema.sql", "02_indexes.sql", "03_seed.sql"]
# 结构迁移脚本（只改结构，不清数据；每次改表都要在这里登记并新加一个 0N 文件）
MIGRATE_FILES = ["04_migrate_uk_seat_slot.sql"]

# 云端库（TiDB Cloud 等）通常不允许 CREATE DATABASE，也无法在这个脚本里
# 用「先连服务器、再 USE 新建库」的流程。所以连云端时把「建库/切库/删库」
# 三类语句从脚本里剔掉，改为在建立连接时直接用 database= 参数指定目标库。
_DB_LEVEL_STMT = re.compile(
    r"(?im)^\s*(CREATE\s+DATABASE|CREATE\s+SCHEMA|USE\s+|DROP\s+DATABASE|DROP\s+SCHEMA)\b[^;]*;?"
)


def _has_real_sql(text: str) -> bool:
    """文件里是否有真正的 SQL 语句（忽略注释行和空行）。"""
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("--") and not s.startswith("#"):
            return True
    return False


def is_remote() -> bool:
    """按 config.py 的同一口径判断当前是不是连公网库。"""
    return bool(os.getenv("DB_HOST"))


def _strip_db_level_statements(sql: str) -> str:
    """去掉建库/切库/删库语句（云端不允许；库由连接参数指定）。"""
    return _DB_LEVEL_STMT.sub("", sql)


def _run_sql_file(conn, path: Path) -> int:
    """执行一个 .sql 文件。返回最后一条语句的结果行数（SELECT 才有意义）。

    ⚠️ 只能用 PyMySQL 能解析的 SQL：不支持 mysql 客户端的 DELIMITER、
       SOURCE 等命令。需要多条语句时用分号分隔并开启 MULTI_STATEMENTS。
    连云端库时，建库/切库语句会被自动剔掉（见 _strip_db_level_statements）。
    """
    sql = path.read_text(encoding="utf-8")
    if is_remote():
        sql = _strip_db_level_statements(sql)
    rows = 0
    with conn.cursor() as cur:
        cur.execute(sql)
        # 多语句执行时要把后续结果集全部消费掉，否则会报 "Commands out of sync"
        while True:
            if cur.description is not None:      # 这是一条会产生结果集的语句
                rows = len(cur.fetchall())
            if not cur.nextset():
                break
    conn.commit()
    print(f"  [执行] {path.name}")
    return rows


def main() -> int:
    # Windows 控制台默认 GBK，直接 print 中文会乱码
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    args = sys.argv[1:]
    with_seed = "--with-seed" in args
    assume_yes = "--yes" in args
    only_migrate = "--migrate" in args
    db_name = DB_CONFIG["database"]

    if only_migrate:
        # 迁移模式：不碰 01_schema.sql，只在已有库上改结构
        files = list(MIGRATE_FILES)
    else:
        # 建库模式：只建表（别人可能还没灌数据，所以默认不带 seed）
        files = [BUILD_FILES[0]]
        if with_seed:
            files += BUILD_FILES[1:]

    # 01_schema.sql 是先 DROP 再 CREATE，等于清空整个库，所以默认要人工确认
    if not assume_yes and not only_migrate:
        print(f"⚠️  这会 DROP 掉 {db_name} 库里的所有表再重建，库里的数据会全部丢失。")
        try:
            answer = input("确认继续请输入 yes 回车（其他输入都取消）：").strip().lower()
        except EOFError:
            answer = ""
        if answer != "yes":
            print("已取消，什么都没做。")
            return 0

    # 本地：不带 database 直连服务器（库可能还不存在，脚本自己会建）
    # 云端：目标库必须可用，因为建库/切库语句已被剔除。库不存在时
    #       尝试自动创建一次，不给就给出明确的手工建库指引。
    cfg = dict(DB_CONFIG)
    remote = is_remote()
    if not remote:
        cfg.pop("database", None)
    cfg["client_flag"] = CLIENT.MULTI_STATEMENTS
    cfg["autocommit"] = True
    cfg["cursorclass"] = pymysql.cursors.DictCursor   # DB_CONFIG 里没带这一项，补上

    print(f"模式：{'云端库' if remote else '本地库'}（{cfg['host']}）")
    print(f"目标 MySQL：{cfg['host']}:{cfg['port']}  用户 {cfg['user']}  目标库 {db_name}")
    try:
        conn = pymysql.connect(**cfg)
    except Exception as e:
        errno = e.args[0] if e.args else None
        if remote and errno == 1049:
            # Unknown database —— 云端实例上还没建这个库
            print(f"\n云端实例上没有 `{db_name}` 库，尝试自动创建……")
            server_cfg = {k: v for k, v in cfg.items() if k != "database"}
            try:
                tmp = pymysql.connect(**server_cfg)
                with tmp.cursor() as cur:
                    cur.execute(
                        f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                tmp.close()
                print(f"已创建 `{db_name}`，重新连接……")
                conn = pymysql.connect(**cfg)
            except Exception as e2:
                print(f"\n自动建库失败：{e2}")
                print("请在云控制台（TiDB Cloud → SQL Editor）执行下面一句，"
                      "然后重新运行本命令：")
                print(f"    CREATE DATABASE `{db_name}` "
                      "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
                return 1
        else:
            print(f"\n连不上 MySQL：{e}")
            if remote:
                print("请检查：DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME 是否正确、"
                      "实例是否处于可用状态（空闲实例可能被暂停，去控制台唤醒），"
                      "以及是否已把本机 IP 加入实例的访问白名单")
            else:
                print("请检查：.env 里的 DB_PASSWORD 是否正确 / MySQL 服务是否已启动")
            return 1

    try:
        if only_migrate:
            print("模式：结构迁移（不清数据，只执行下列迁移脚本）")
        for name in files:
            path = SQL_DIR / name
            if not path.exists():
                print(f"  [跳过] {name}（文件不存在）")
                continue
            if not _has_real_sql(path.read_text(encoding="utf-8")):
                print(f"  [跳过] {name}（还没有实际内容）")
                continue
            _run_sql_file(conn, path)

        # 建完自检：列出所有表 + 关键约束统计
        with conn.cursor() as cur:
            if not remote:
                cur.execute(f"USE `{db_name}`")
            cur.execute("SHOW TABLES")
            tables = [list(row.values())[0] for row in cur.fetchall()]

            cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.CHECK_CONSTRAINTS "
                "WHERE CONSTRAINT_SCHEMA = %s", (db_name,))
            checks = cur.fetchone()["n"]

            cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.REFERENTIAL_CONSTRAINTS "
                "WHERE CONSTRAINT_SCHEMA = %s", (db_name,))
            fkeys = cur.fetchone()["n"]

            cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_COLLATION <> 'utf8mb4_unicode_ci'",
                (db_name,))
            bad_collation = cur.fetchone()["n"]

            # uk_seat_slot 的列清单：迁移是否生效就看这里有没有 end_time
            cur.execute(
                "SELECT GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX SEPARATOR ',') AS cols "
                "FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'reservation_order' "
                "  AND INDEX_NAME = 'uk_seat_slot'",
                (db_name,))
            slot_row = cur.fetchone()
            slot_cols = (slot_row or {}).get("cols")

        print(f"\n完成：{db_name} 库共 {len(tables)} 张表"
              f"（外键 {fkeys} 条，CHECK 约束 {checks} 条）")
        for t in tables:
            print(f"   - {t}")
        if len(tables) == 0:
            print("（一张表都没有，请检查 01_schema.sql 是否有内容）")
        if bad_collation:
            print(f"⚠️  有 {bad_collation} 张表的排序规则不是 utf8mb4_unicode_ci，请检查建表语句")
        else:
            print("排序规则检查：全部为 utf8mb4_unicode_ci ✅")

        if slot_cols is None:
            print("⚠️  reservation_order 上没有 uk_seat_slot，请检查建表脚本")
        elif "end_time" in slot_cols.split(","):
            print(f"uk_seat_slot 检查：{slot_cols} ✅（已是含 end_time 的新键）")
        else:
            print(f"⚠️  uk_seat_slot 还是旧键（{slot_cols}），"
                  "请执行 python -m db.init_db --migrate 升级")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
