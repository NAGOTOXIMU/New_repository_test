"""管理员业务：登录。"""
from repository import admin_repo
from services.exceptions import BizError
from services.password import verify_password


def login(username, password):
    """管理员登录。成功返回 dict（含 role="admin"，不含密码），失败抛 BizError。"""
    admin = admin_repo.get_by_username((username or "").strip())
    if admin is None:
        raise BizError("用户名或密码错误")
    if not verify_password(password or "", admin["password"]):
        raise BizError("用户名或密码错误")
    if admin["status"] != "正常":
        raise BizError("管理员账号已被停用")

    admin.pop("password", None)
    admin["role"] = "admin"
    return admin
