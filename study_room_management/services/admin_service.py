"""管理员业务：登录、资料与状态管理。

规范口径：密码列是 password_hash；角色 role_type(1普通运营员 2超级管理员)；
store_id 为 NULL 表示超级管理员（可管理所有门店）。
"""
import pymysql

from config import ROLE_NAMES, ROLE_OPERATOR, ROLE_SUPER, STATUS_ON
from repository import admin_repo, store_repo
from services.exceptions import BizError
from services.password import hash_password, verify_password


def login(username, password):
    """管理员登录。成功返回 admin dict（不含密码哈希）。"""
    admin = admin_repo.get_by_username((username or "").strip())
    if admin is None:
        raise BizError("用户名或密码错误")
    if not verify_password(password or "", admin["password_hash"]):
        raise BizError("用户名或密码错误")
    if int(admin["status"]) != STATUS_ON:
        raise BizError("该账号已被禁用")

    admin.pop("password_hash")
    admin["role"] = "admin"
    admin["role_name"] = ROLE_NAMES.get(int(admin["role_type"]), "普通运营员")
    # 超管的 store_id 是 NULL，表示可以管理所有门店
    admin["is_super"] = int(admin["role_type"]) == ROLE_SUPER
    return admin


def create_admin(username, password, real_name, phone=None, store_id=None,
                 role_type=ROLE_OPERATOR):
    """新增管理员。store_id 传 None 且 role_type=2 才是超级管理员。"""
    username = (username or "").strip()
    real_name = (real_name or "").strip()
    if not username or not password or not real_name:
        raise BizError("用户名、密码、姓名都不能为空")
    if len(password) < 6:
        raise BizError("密码至少 6 位")
    if role_type not in (ROLE_OPERATOR, ROLE_SUPER):
        raise BizError("角色类型只能是 1（普通运营员）或 2（超级管理员）")
    if role_type == ROLE_OPERATOR and store_id is None:
        raise BizError("普通运营员必须指定负责的门店")
    if store_id is not None and store_repo.get_by_id(store_id) is None:
        raise BizError("指定的门店不存在")
    if role_type == ROLE_SUPER:
        store_id = None      # 超管不绑定门店

    if admin_repo.exists_username(username):
        raise BizError("这个用户名已经被占用了")
    try:
        return admin_repo.create(username, hash_password(password), real_name,
                                 phone, store_id, role_type)
    except pymysql.err.IntegrityError:
        raise BizError("这个用户名已经被占用了")


def list_admins_paged(page=1, page_size=20):
    """管理员列表。返回 (数据列表, 总条数)。"""
    offset = (max(page, 1) - 1) * page_size
    return admin_repo.list_paged(offset, page_size), admin_repo.count()


def set_status(admin_id, status):
    """启用(1) / 禁用(0)。不允许把最后一个超管禁掉。"""
    if status not in (0, 1):
        raise BizError("状态只能是 1（正常）或 0（禁用）")
    target = admin_repo.get_by_id(admin_id)
    if target is None:
        raise BizError("管理员不存在")
    if status == 0 and int(target["role_type"]) == ROLE_SUPER:
        raise BizError("超级管理员不能被禁用")
    return admin_repo.update_status(admin_id, status)


def update_profile(admin_id, real_name=None, phone=None, store_id=None):
    """改资料。"""
    if admin_repo.get_by_id(admin_id) is None:
        raise BizError("管理员不存在")
    if store_id is not None and store_repo.get_by_id(store_id) is None:
        raise BizError("指定的门店不存在")
    return admin_repo.update_profile(admin_id, real_name, phone, store_id)


def change_password(admin_id, old_password, new_password):
    """改密码：先验旧密码。"""
    row = admin_repo.get_by_id_with_hash(admin_id)
    if row is None:
        raise BizError("管理员不存在")
    if not verify_password(old_password or "", row["password_hash"]):
        raise BizError("原密码不正确")
    if len(new_password or "") < 6:
        raise BizError("新密码至少 6 位")
    admin_repo.update_password(admin_id, hash_password(new_password))
    return True
