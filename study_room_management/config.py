"""全局配置。数据库连接从环境变量 / secrets.toml / .env 读，其他项全组一致。

支持的数据库环境变量（本地只用到 DB_PASSWORD，其余留空即可）：
    DB_HOST      数据库主机。**不设置 = 本地模式**（连 127.0.0.1）
    DB_PORT      端口。本地默认 3306；远程模式默认 4000（TiDB Cloud）
    DB_USER      用户名。TiDB Cloud Starter 的用户名带实例前缀，形如 `xxx.root`
    DB_PASSWORD  密码
    DB_NAME      库名，默认 study_room_management
    DB_SSL_CA    （可选）CA 证书路径；不设则自动用 certifi 的证书包
    DB_SSL_MODE  （可选）设为 "skip-verify" 则只加密不校验证书，仅作排障
    DB_CONNECT_TIMEOUT （可选）连接超时秒数；本地默认 5，云端默认 15

读取优先级：
    1. 已存在的环境变量（云端 Streamlit Secrets 的**根级键会被自动提升为环境变量**，
       见 streamlit/runtime/secrets.py 的 _maybe_set_environment_variable）
    2. st.secrets（同一份 Secrets 的对象式访问）
    3. 项目根目录的 .streamlit/secrets.toml（让本地 CLI 脚本也能读到云端配置）
    4. 项目根目录的 .env（本地开发）
    5. 代码里的默认值
"""
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

def _load_secrets_file() -> dict:
    """读项目根目录的 .streamlit/secrets.toml（本地跑 CLI 脚本时用）。

    Streamlit 自己在运行时也会读这个文件；这里手读一份是为了让
    `python -m db.init_db` 这类**非 Streamlit 进程**也能拿到云端连接配置，
    不必把密码重复写到命令行环境变量里。
    """
    path = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
    if not path.exists():
        return {}
    try:
        try:
            import tomllib
        except ModuleNotFoundError:      # Python < 3.11
            import tomli as tomllib
        with path.open("rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


_SECRETS_FILE = _load_secrets_file()


def _get(key: str, default: str = "") -> str:
    """读一个配置项，按「环境变量 → st.secrets → secrets.toml → 默认值」取第一个非空值。"""
    value = os.getenv(key)
    if value not in (None, ""):
        return value
    try:
        import streamlit as st
        value = st.secrets[key]
        if value not in (None, ""):
            return str(value)
    except Exception:
        pass
    value = _SECRETS_FILE.get(key)
    if value not in (None, ""):
        return str(value)
    return default


def _env_int(key: str, default: int) -> int:
    value = _get(key, "")
    if value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    value = _get(key, "")
    if value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _ssl_args(host: str) -> dict:
    """公网数据库需要 TLS。PyMySQL 的 TLS 开关是 ssl_verify_cert / ssl_ca。

    · host 是本机 → 不需要 TLS，也不传 ssl 参数（避免影响本地连接）
    · host 是公网 → 必须 TLS（TiDB Cloud Starter 强制要求）

    CA 证书查找顺序：
      1) DB_SSL_CA 指定的文件
      2) certifi 自带的证书包（pip 装的东西，最省事）
      3) 都没有 → 退化为「加密但跳过证书校验」，只加密不做身份验证

    ⚠️ 第 3 种退化只用于临时排障：不校验证书时理论上有中间人风险。
       正式使用请装 certifi（已写在 requirements.txt）或设置 DB_SSL_CA。
    """
    if host in ("127.0.0.1", "localhost", "::1"):
        return {}

    # 逃生舱：DB_SSL_MODE=skip-verify 时强制「只加密、不校验证书」。
    # 用于 certifi 验不过云端证书时的排障；日常不要使用。
    if _get("DB_SSL_MODE") == "skip-verify":
        return {"ssl_disabled": False, "ssl_verify_cert": False}

    ca = _get("DB_SSL_CA")
    if not ca or not Path(ca).exists():
        ca = None
        try:
            import certifi
            ca = certifi.where()
        except Exception:
            ca = None
    if ca:
        return {"ssl_ca": ca, "ssl_verify_cert": True}
    print("⚠️ 未找到可用的 CA 证书，当前以「加密但不校验证书」方式连接。"
          "正式使用请安装 certifi 或设置 DB_SSL_CA。")
    return {"ssl_disabled": False, "ssl_verify_cert": False}


# 数据库连接参数
#
# 双模式，同一份代码本地和云端都能跑：
#   · 本机开发：不设任何环境变量，连 .env 提供密码的本地 MySQL（和以前完全一样）
#   · 云端部署：Streamlit Cloud 的 Secrets 注入成环境变量，从而连公网库
#
# 判定依据只看 DB_HOST：
#   DB_HOST 没设 → 本地模式，host 保持 127.0.0.1，不传 SSL
#   DB_HOST 设了 → 远程模式，按注入的变量组装连接，并启用 TLS
_DB_HOST = _get("DB_HOST")
if not _DB_HOST:
    _DB_HOST = "127.0.0.1"
    DB_CONFIG = {
        "host": _DB_HOST,
        "port": _env_int("DB_PORT", 3306),
        "user": _get("DB_USER", "root"),
        "password": _get("DB_PASSWORD", ""),
        "database": _get("DB_NAME", "study_room_management"),
        "charset": "utf8mb4",
    }
else:
    DB_CONFIG = {
        "host": _DB_HOST,
        "port": _env_int("DB_PORT", 4000),          # TiDB Cloud 默认 4000
        "user": _get("DB_USER", "root"),
        "password": _get("DB_PASSWORD", ""),
        "database": _get("DB_NAME", "study_room_management"),
        "charset": "utf8mb4",
    }
    DB_CONFIG.update(_ssl_args(_DB_HOST))

# —— 业务常量（全组统一口径，禁止各处硬编码） ——

# 卡类型 card_type.kind
KIND_HOURS = 1      # 时长卡：value 是分钟数
KIND_TIMES = 2      # 次卡：value 是次数
KIND_STORED = 3     # 储值卡：余额在 user_card.balance

KIND_NAMES = {KIND_HOURS: "时长卡", KIND_TIMES: "次卡", KIND_STORED: "储值卡"}

# 订单状态 reservation_order.order_status
ORDER_PENDING = 1     # 待使用
ORDER_ONGOING = 2     # 进行中
ORDER_DONE = 3        # 已完成
ORDER_CANCELLED = 4   # 已取消
ORDER_EXPIRED = 5     # 已过期

ORDER_STATUS_NAMES = {
    ORDER_PENDING: "待使用",
    ORDER_ONGOING: "进行中",
    ORDER_DONE: "已完成",
    ORDER_CANCELLED: "已取消",
    ORDER_EXPIRED: "已过期",
}

# 可取消的订单状态（尚未结束）
ORDER_CANCELLABLE = (ORDER_PENDING, ORDER_ONGOING)

# 支付状态 recharge_order.pay_status
PAY_UNPAID = 0     # 待支付
PAY_PAID = 1       # 已支付
PAY_REFUNDED = 2   # 已退款

PAY_STATUS_NAMES = {PAY_UNPAID: "待支付", PAY_PAID: "已支付", PAY_REFUNDED: "已退款"}

# 通用启用/禁用（store / seat / card_type / user / user_card 的 status）
STATUS_ON = 1
STATUS_OFF = 0

# 区域类型 seat.area_type
AREA_NAMES = {1: "普通区", 2: "安静区", 3: "靠窗区"}

# 会员等级 user.member_level
MEMBER_LEVEL_NAMES = {0: "普通用户", 1: "月卡会员", 2: "季卡会员"}

# 管理员角色 admin.role_type
ROLE_OPERATOR = 1      # 普通运营员
ROLE_SUPER = 2         # 超级管理员
ROLE_NAMES = {ROLE_OPERATOR: "普通运营员", ROLE_SUPER: "超级管理员"}

# 业务规则
MAX_RESERVE_MINUTES = 480     # 一次预约最长 8 小时（480 分钟）
MIN_RESERVE_MINUTES = 60      # 一次预约最短 1 小时
RESERVE_STEP_MINUTES = 60     # 预约时段按整点切分

# 储值卡的默认小时单价（元/小时）。
# 规范里 card_type 没有「储值卡单价」这一列，所以定价规则是：
#   1) 如果 card_type.value > 0，就把它当作「这张卡包含的小时数」，
#      单价 = price ÷ value（例如 100 元 / 20 小时 = 5 元/小时）
#   2) value = 0 时用本常量兜底
# 管理员希望改价，只需在卡种管理里把 value 填成小时数即可，无需改代码。
STORED_HOUR_RATE = 5.00
