"""用户业务：注册、登录。本文件不写 SQL，只做校验和调用 repository。

规范口径：phone 是唯一登录账号；status 是 TINYINT（1 正常 / 0 禁用）。
"""
import pymysql

from config import STATUS_ON
from db.connection import read_cursor
from repository import recharge_repo, reservation_repo, user_card_repo, user_repo
from services.exceptions import BizError
from services.password import hash_password, verify_password


def register(phone, password, nickname):
    """注册新用户。成功返回用户 dict（不含密码哈希），失败抛 BizError。"""
    phone = (phone or "").strip()
    nickname = (nickname or "").strip()

    if not phone or not password or not nickname:
        raise BizError("手机号、密码、昵称都不能为空")
    if not (phone.isdigit() and len(phone) == 11):
        raise BizError("手机号必须是 11 位数字")
    if len(password) < 6:
        raise BizError("密码至少 6 位")

    if user_repo.exists_phone(phone):
        raise BizError("这个手机号已经被注册了")

    try:
        user_id = user_repo.create(phone, hash_password(password), nickname)
    except pymysql.err.IntegrityError:
        # 并发下两个请求同时通过查重时会撞唯一索引，这里兜一句人话
        raise BizError("这个手机号已经被注册了")

    # 结构和 login() 的返回值保持一致，界面层可以混用
    return {**user_repo.get_by_id(user_id), "role": "user"}


def login(phone, password):
    """登录。成功返回用户 dict（不含密码哈希），失败抛 BizError。"""
    user = user_repo.get_by_phone((phone or "").strip())

    # 查不到用户 和 密码不对，故意给同一句提示，不让人猜出哪些手机号存在
    if user is None:
        raise BizError("手机号或密码错误")
    if not verify_password(password or "", user["password_hash"]):
        raise BizError("手机号或密码错误")
    if user["status"] != STATUS_ON:
        raise BizError("账号已被禁用，请联系管理员")

    user.pop("password_hash")     # 哈希值不能传到界面层
    user["role"] = "user"         # 管理员登录走 admin_service，那里写 "admin"
    return user


def get_profile(user_id):
    """取最新用户资料（含余额/时长汇总），用于登录后刷新会话里的数据。"""
    user = user_repo.get_by_id(user_id)
    if user is None:
        raise BizError("用户不存在")
    return {**user, "role": "user"}


def update_nickname(user_id, nickname):
    """改昵称。"""
    nickname = (nickname or "").strip()
    if not nickname:
        raise BizError("昵称不能为空")
    if user_repo.update_profile(user_id, nickname) == 0:
        raise BizError("没有改动，或者用户不存在")
    return True


def change_password(user_id, old_password, new_password):
    """改密码：先验旧密码，再写新哈希。"""
    with read_cursor() as cur:
        cur.execute("SELECT password_hash FROM `user` WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
    if row is None:
        raise BizError("用户不存在")
    if not verify_password(old_password or "", row["password_hash"]):
        raise BizError("原密码不正确")
    if len(new_password or "") < 6:
        raise BizError("新密码至少 6 位")
    user_repo.update_password(user_id, hash_password(new_password))
    return True


def set_status(user_id, status):
    """管理员冻结 / 解冻账号。status 传 1 或 0。"""
    if status not in (0, 1):
        raise BizError("账号状态只能是 1（正常）或 0（禁用）")
    if user_repo.update_status(user_id, status) == 0:
        raise BizError("用户不存在或状态未变化")
    return True


def list_users_paged(keyword=None, page=1, page_size=20):
    """管理端用户列表。返回 (数据列表, 总条数)。"""
    offset = (max(page, 1) - 1) * page_size
    return (user_repo.list_paged(keyword, offset, page_size),
            user_repo.count(keyword))


def get_user_detail(user_id, recent=10):
    """用户详情聚合：基本信息 + 持卡 + 最近预约 + 最近充值。

    把「一个用户身上挂了几张表」的取数逻辑收在业务层，
    界面层只负责把结果铺开显示，不再自己拼几个 repo 调用。
    """
    user = user_repo.get_by_id(user_id)
    if user is None:
        raise BizError("用户不存在")

    return {
        "user": user,
        "cards": user_card_repo.list_by_user(user_id),
        "orders": reservation_repo.list_by_user(user_id, 0, recent),
        "order_total": reservation_repo.count_by_user(user_id),
        "recharges": recharge_repo.list_by_user(user_id, 0, recent),
        "recharge_total": recharge_repo.count_by_user(user_id),
    }
