"""数据库连接获取。

职责：
    - 提供统一的连接入口 get_conn()，参数从 config.py 读取
    - 提供连通性自检 check_connection()

不做什么：
    - 不写任何 SQL（SQL 属于 repository/）
    - 不写业务判断（属于 services/）

关于连接策略（为什么不做连接池）：
    Streamlit 每次交互都会从头重跑整个脚本。理论上可以把连接缓存起来复用，
    但 pymysql 的 Connection 不是线程安全的——多个用户同时用一个连接会出问题。
    本项目规模小、并发低，"每次新建、用完即关"最稳妥，也不会踩坑。
    将来真要优化，再引入 DBUtils.PooledDB 或 SQLAlchemy 的连接池。

关于 DictCursor：
    加上它，查询结果才是字典（row["name"]），而不是元组（row[2]）；
    不加的话得靠数位置取值，很容易数错。

注意：游标必须用 with 关闭；跨多张表的写操作统一交给 db/uow.py 的 uow()。
"""
import pymysql

from config import DB_CONFIG


def get_conn(autocommit: bool = False):
    """新建一条数据库连接。用完务必在 finally 里 close()。

    只做单表单条读写时用它；跨多张表的写操作请用 db/uow.py 的 uow()。
    """
    return pymysql.connect(
        **DB_CONFIG,
        autocommit=autocommit,
        cursorclass=pymysql.cursors.DictCursor,
    )


def check_connection() -> tuple[bool, str]:
    """连通性自检。返回 (是否成功, 说明文字)。

    在项目根目录执行：
        python -c "from db.connection import check_connection; print(check_connection())"

    常见失败原因：
        Access denied            → .env 里的 DB_PASSWORD 不对
        Unknown database         → 还没执行 db/sql/01_schema.sql 建库
        Can't connect to MySQL   → MySQL 服务没启动
    """
    try:
        conn = get_conn()
    except Exception as e:
        return False, f"连接失败：{e}"
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION() AS version, DATABASE() AS db")
            row = cur.fetchone()
        return True, f"连接成功：MySQL {row['version']}，当前库 {row['db']}"
    except Exception as e:
        return False, f"已连上但查询失败：{e}"
    finally:
        conn.close()
