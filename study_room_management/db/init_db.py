"""一键建库建表：执行 db/sql/ 下的 SQL 脚本。

用法（在项目根目录 study_room_management 下执行）：

    python -m db.init_db               # 只建库建表（会先提示确认）
    python -m db.init_db --yes         # 跳过确认
    python -m db.init_db --with-seed   # 连索引和测试数据一起灌

为什么用它而不是 mysql 命令行：
    - 复用 .env 里的密码，不用在命令行里再输一遍
    - 组员的机器上不一定配好了 mysql.exe 的 PATH
        然后编辑 .env，把 DB_PASSWORD 改成你本机 MySQL 的密码
    - 可重复执行（脚本里都是 IF NOT EXISTS / DROP TABLE IF EXISTS / ON DUPLICATE KEY）

注意：连接时【不指定 database】——因为库可能还不存在。
"""
import sys
from pathlib import Path

import pymysql
from pymysql.constants import CLIENT

from config import DB_CONFIG

SQL_DIR = Path(__file__).resolve().parent / "sql"


def _has_real_sql(text: str) -> bool:
    """文件里是否有真正的 SQL 语句（忽略注释行和空行）。"""
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("--") and not s.startswith("#"):
            return True
    return False


def _run_sql_file(conn, path: Path) -> int:
    """执行一个 .sql 文件。返回最后一条语句的结果行数（SELECT 才有意义）。

    ⚠️ 只能用 PyMySQL 能解析的 SQL：不支持 mysql 客户端的 DELIMITER、
       SOURCE 等命令。需要多条语句时用分号分隔并开启 MULTI_STATEMENTS。
    """
    sql = path.read_text(encoding="utf-8")
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
    db_name = DB_CONFIG["database"]

    files = ["01_schema.sql"]
    if with_seed:
        files += ["02_indexes.sql", "03_seed.sql"]

    # 01_schema.sql 是先 DROP 再 CREATE，等于清空整个库，所以默认要人工确认
    if not assume_yes:
        print(f"⚠️  这会 DROP 掉 {db_name} 库里的所有表再重建，库里的数据会全部丢失。")
        try:
            answer = input("确认继续请输入 yes 回车（其他输入都取消）：").strip().lower()
        except EOFError:
            answer = ""
        if answer != "yes":
            print("已取消，什么都没做。")
            return 0

    # 建库阶段不能带 database 参数，否则连不上还不存在的库
    cfg = dict(DB_CONFIG)
    cfg.pop("database", None)
    cfg["client_flag"] = CLIENT.MULTI_STATEMENTS
    cfg["autocommit"] = True
    cfg["cursorclass"] = pymysql.cursors.DictCursor   # DB_CONFIG 里没带这一项，补上

    print(f"目标 MySQL：{cfg['host']}:{cfg['port']}  用户 {cfg['user']}  目标库 {db_name}")
    try:
        conn = pymysql.connect(**cfg)
    except Exception as e:
        print(f"\n连不上 MySQL：{e}")
        print("请检查：.env 里的 DB_PASSWORD 是否正确 / MySQL 服务是否已启动")
        return 1

    try:
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
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
