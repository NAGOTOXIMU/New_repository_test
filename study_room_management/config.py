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

# 数据库连接参数 —— 与《数据库规范》第一节「本地连接配置」保持一致
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": os.getenv("DB_PASSWORD", ""),
    "database": "study_room_management",
    "charset": "utf8mb4",
}

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
