"""全局配置。数据库密码从 .env 读，其他项全组一致。"""
import os
from pathlib import Path


def _load_env_file() -> None:
    """把同目录下 .env 里的键值对读进环境变量（已存在的环境变量不覆盖）。"""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file()

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": os.getenv("DB_PASSWORD", ""),
    "database": "study_room",
    "charset": "utf8mb4",
}
