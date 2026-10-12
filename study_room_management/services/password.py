"""密码哈希。数据库里存的一律是 hash_password() 的输出，绝不存明文。

原理不用看代码，记住三件事：
    1. 每个密码配一个随机盐，所以两个人密码相同、哈希也不同
    2. 迭代 10 万次，让暴力破解变慢
    3. 校验用 compare_digest，防时序攻击
"""
import base64
import hashlib
import hmac
import os

_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    """明文密码 → "盐$哈希" 字符串。"""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    """校验明文密码是否与库里的 "盐$哈希" 匹配。"""
    if not isinstance(stored, str) or "$" not in stored:
        return False
    salt_b64, dk_b64 = stored.split("$", 1)
    try:
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
    except Exception:      # 库里存的值格式坏了，按校验失败处理
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return hmac.compare_digest(dk, expected)
