"""用户业务：注册、登录。本文件不写 SQL，只做校验和调用 repository。"""
import pymysql

from repository import user_repo
from services.exceptions import BizError
from services.password import hash_password, verify_password


def register(username, password, real_name, phone, email=None):
    """注册新用户。成功返回用户 dict（不含密码），失败抛 BizError。"""
    username = (username or "").strip()
    real_name = (real_name or "").strip()
    phone = (phone or "").strip()

    if not username or not password or not real_name or not phone:
        raise BizError("用户名、密码、姓名、手机号都不能为空")

    if user_repo.exists_username(username):
        raise BizError("这个用户名已经被注册了")
    if user_repo.exists_phone(phone):
        raise BizError("这个手机号已经被注册了")

    try:
        user_id = user_repo.create(
            username, hash_password(password), real_name, phone, email
        )
    except pymysql.err.IntegrityError:
        # 并发下两个请求同时通过查重时会撞唯一索引，这里兜一句人话
        raise BizError("这个用户名或手机号已经被注册了")

    return {
        "user_id": user_id,
        "username": username,
        "real_name": real_name,
        "role": "user",
    }


def login(username, password):
    """登录。成功返回用户 dict（不含密码），失败抛 BizError。"""
    user = user_repo.get_by_username((username or "").strip())

    # 查不到用户 和 密码不对，故意给同一句提示，不让人猜出哪些用户名存在
    if user is None:
        raise BizError("用户名或密码错误")
    if not verify_password(password or "", user["password"]):
        raise BizError("用户名或密码错误")
    if user["status"] != "正常":
        raise BizError("账号已被冻结，请联系管理员")

    user.pop("password")        # 哈希值不能传到界面层
    user["role"] = "user"       # 管理员登录走 admin_service，那里写 "admin"
    return user
