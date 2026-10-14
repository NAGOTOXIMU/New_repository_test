"""云库配置向导：把「配好云端数据库」压缩成一条命令。

用法（在项目根目录 study_room_management 下执行）：

    # 1. 填入从云控制台拿到的连接信息（写进 .streamlit/secrets.toml）
    python -m db.cloud_setup --set \\
        --host gateway01.ap-northeast-1.prod.aws.tidbcloud.com \\
        --port 4000 \\
        --user 3pTAoNNegb47Uc8.root \\
        --password '生成的密码' \\
        --dbname study_room_management

    # 2. 只检查：配置是否齐全 + 能不能连上（不动数据）
    python -m db.cloud_setup --check

    # 3. 初始化：建表 + 灌测试数据 + 核对测试账号（会连真实云库）
    python -m db.cloud_setup --init

    # 4. 最后一步提示（要手工填进 Streamlit Cloud 的 Secrets）
    python -m db.cloud_setup --print-secrets

为什么需要它：
    · 连接信息有 5 个字段，手工填进 secrets.toml 极易漏项或写错前缀
      （TiDB Cloud 的用户名必须带实例前缀，形如 `xxx.root`）
    · 写完之后没人帮你验证「到底连不连得上」，往往要等应用部署才发现错
    · 本向导在写入前**先连一次**验证，成功才落盘；失败会给出针对性排查提示

⚠️ 安全：
    · 只写 .streamlit/secrets.toml，该文件已在 .gitignore 里，不会进仓库
    · 校验失败时**不会**写入任何东西
    · 命令行里的 --password 会留在你的 shell 历史里；介意的话改用交互式输入
"""
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRETS_PATH = PROJECT_ROOT / ".streamlit" / "secrets.toml"

DB_KEYS = ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"]

TEST_ACCOUNTS = [
    ("用户", "13800000001", "123456"),
    ("用户", "13800000002", "123456"),
    ("超级管理员", "admin", "admin123"),
    ("门店运营员", "ops1", "admin123"),
]


# ── secrets.toml 读写（自己解析，不引入 toml 依赖）────────────────

def read_secrets() -> dict:
    """读 .streamlit/secrets.toml 的根级键值。文件不存在则返回空 dict。"""
    if not SECRETS_PATH.exists():
        return {}
    result = {}
    for line in SECRETS_PATH.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, value = s.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        result[key.strip()] = value
    return result


def write_secrets(values: dict) -> None:
    """把键值写进 .streamlit/secrets.toml（保留已存在的其他键）。"""
    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = read_secrets()
    existing.update(values)
    lines = [
        "# 由 python -m db.cloud_setup --set 生成",
        "# 本文件已被 .gitignore 忽略，不会进仓库。",
        "# 同一份内容还要复制到 Streamlit Cloud → Settings → Secrets。",
        "",
    ]
    for key in DB_KEYS:
        if key in existing:
            lines.append(f'{key} = "{existing[key]}"')
    lines.append("")
    SECRETS_PATH.write_text("\n".join(lines), encoding="utf-8")


# ── 把 secrets.toml 提升为当前进程的环境变量 ─────────────────────

def load_secrets_into_env() -> dict:
    """让 config.py 读到 secrets.toml 里的配置，返回本次设置的环境变量。

    做法是按 secrets.toml **强制覆盖**环境变量：正常优先级里 .env 高于
    secrets.toml，但本向导的目的正是「验证 secrets.toml 写得对不对」，
    所以这里临时把它顶到最高优先级。进程退出即失效。
    """
    values = read_secrets()
    applied = {}
    for key in DB_KEYS + ["DB_SSL_MODE", "DB_SSL_CA"]:
        if key in values:
            applied[key] = os.environ.get(key)
            os.environ[key] = str(values[key])
    return applied


def restore_env(applied: dict) -> None:
    for key, old in applied.items():
        if old is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old


# ── 三个动作 ────────────────────────────────────────────────────

def cmd_set(args) -> int:
    """写入 secrets.toml，写入前先尝试连接验证。"""
    parsed = {}
    for token in args:
        if not token.startswith("--") or "=" not in token:
            continue
        key, value = token[2:].split("=", 1)
        parsed[key] = value
    # 也支持 --host value 这种空格分隔的写法
    i = 0
    while i < len(args):
        t = args[i]
        if t.startswith("--") and "=" not in t and t[2:] in (
                "host", "port", "user", "password", "dbname"):
            if i + 1 < len(args):
                parsed[t[2:]] = args[i + 1]
                i += 2
                continue
        i += 1

    mapping = {
        "host": "DB_HOST", "port": "DB_PORT", "user": "DB_USER",
        "password": "DB_PASSWORD", "dbname": "DB_NAME",
    }
    unknown = [k for k in parsed if k not in mapping]
    if unknown:
        print(f"⚠️ 忽略了不认识的参数：{', '.join(unknown)}")

    values = {mapping[k]: v for k, v in parsed.items() if k in mapping}
    missing = [k for k in ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD"] if k not in values]
    if missing:
        print("缺少参数：" + ", ".join(missing))
        print("\n完整示例：")
        print("  python -m db.cloud_setup --set --host <host> --port 4000 \\")
        print("      --user <实例前缀>.root --password '<密码>' --dbname study_room_management")
        return 2

    values.setdefault("DB_NAME", "study_room_management")
    print("即将写入的配置（密码只显示长度）：")
    for key in DB_KEYS:
        v = values.get(key, "")
        shown = f"<{len(v)} 字符>" if key == "DB_PASSWORD" else v
        print(f"   {key} = {shown}")

    # 写盘前先验证能连上，避免把错的配置落盘
    print("\n先验证一次连接……")
    applied = load_secrets_into_env()
    # 临时用命令行给的值覆盖（可能是首次写入，文件里还没有）
    saved = {k: os.environ.get(k) for k in values}
    os.environ.update({k: str(v) for k, v in values.items()})
    try:
        import importlib
        import config
        importlib.reload(config)
        from db.connection import check_connection
        importlib.reload(sys.modules["db.connection"])
        ok, msg = check_connection()
    finally:
        restore_env({**applied, **saved})

    if not ok:
        print(f"❌ 连接失败，未写入任何文件。\n   {msg}")
        if "1049" in str(msg) or "Unknown database" in str(msg):
            print("\n注意：参数本身是对的，只是云实例上还没有这个库。")
            print("  直接跑下面的命令即可 —— --init 会自动建库：")
            print("      python -m db.cloud_setup --init")
            return 0
        print("\n常见原因：")
        print("  · 用户名漏了实例前缀（TiDB Cloud 是 `<前缀>.root`，不是 `root`）")
        print("  · 端口写成 3306（TiDB Cloud 是 4000）")
        print("  · 密码复制不全，或实例还没建好/被暂停")
        print("  · 实例的 IP 白名单里没有放行你的当前 IP（可先加 0.0.0.0/0）")
        return 1

    write_secrets(values)
    print(f"✅ 连接成功，已写入 {SECRETS_PATH}")
    print(f"   {msg}")
    print("\n下一步：")
    print("   python -m db.cloud_setup --init        # 建表 + 灌测试数据")
    return 0


def cmd_check() -> int:
    """只检查配置与连通性，不做任何写入。"""
    values = read_secrets()
    print(f"读取 {SECRETS_PATH}")
    if not values:
        print("❌ 文件不存在或为空。先跑：")
        print("   python -m db.cloud_setup --set --host ... --port ... "
              "--user ... --password ...")
        return 2

    missing = [k for k in ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD"] if not values.get(k)]
    for key in DB_KEYS:
        v = values.get(key, "")
        shown = f"<{len(v)} 字符>" if key == "DB_PASSWORD" else (v or "(未设置)")
        print(f"   {key} = {shown}")
    if missing:
        print(f"\n❌ 缺少：{', '.join(missing)}")
        return 2

    applied = load_secrets_into_env()
    try:
        import importlib
        import config
        importlib.reload(config)
        import db.connection as conn_mod
        importlib.reload(conn_mod)
        ok, msg = conn_mod.check_connection()
    finally:
        restore_env(applied)

    if ok:
        print(f"\n✅ 连接成功：{msg}")
        print("\n下一步：python -m db.cloud_setup --init")
        return 0
    print(f"\n❌ 连接失败：{msg}")
    return 1


def cmd_init() -> int:
    """建表 + 灌测试数据，然后核对测试账号能不能登录。"""
    if not SECRETS_PATH.exists():
        print("❌ 没找到 secrets.toml，先跑 --set")
        return 2

    print("第 1 步：建表 + 灌测试数据")
    print("=" * 60)
    import importlib

    import db.init_db as init_mod
    importlib.reload(init_mod)
    saved_argv = sys.argv
    sys.argv = ["db.init_db", "--with-seed", "--yes"]
    try:
        code = init_mod.main()
    finally:
        sys.argv = saved_argv
    if code != 0:
        print("\n初始化失败，后面步骤跳过。")
        print("若提示 Unknown database：代码会自动建库；失败时按提示手工建。")
        return code

    print("\n第 2 步：补历史订单（供数据看板演示）")
    print("=" * 60)
    import db.seed as seed_mod
    importlib.reload(seed_mod)
    saved_argv = sys.argv
    sys.argv = ["db.seed", "--with-orders"]
    try:
        seed_mod.main()
    finally:
        sys.argv = saved_argv

    print("\n第 3 步：核对测试账号能否登录")
    print("=" * 60)
    import config
    importlib.reload(config)
    import db.connection as conn_mod
    importlib.reload(conn_mod)
    from services import admin_service, user_service

    all_ok = True
    for label, account, password in TEST_ACCOUNTS:
        try:
            if label == "用户":
                row = user_service.login(account, password)
                name = row.get("nickname") or row.get("phone")
            else:
                row = admin_service.login(account, password)
                name = row.get("username") or account
            print(f"   ✅ {label:6s} {account:12s} 登录成功（{name}）")
        except Exception as e:
            all_ok = False
            print(f"   ❌ {label:6s} {account:12s} 登录失败：{e}")

    print("\n" + "=" * 60)
    if all_ok:
        print("✅ 云库已就绪，所有测试账号都能登录。")
        print("\n还差最后一步（手工）：把下面内容填进")
        print("Streamlit Cloud → 你的应用 → Settings → Secrets：")
        print("   python -m db.cloud_setup --print-secrets")
        return 0
    print("⚠️ 有账号登录失败，通常是测试数据没灌全，请检查上面的输出。")
    return 1


def cmd_print_secrets() -> int:
    """打印要填进 Streamlit Cloud Secrets 的内容（密码只显示长度）。"""
    values = read_secrets()
    if not values:
        print("❌ 没有 secrets.toml，先跑 --set")
        return 2
    print("把下面整段复制到 Streamlit Cloud → Settings → Secrets：\n")
    print("-" * 56)
    for key in DB_KEYS:
        if key in values:
            if key == "DB_PASSWORD":
                v = values[key]
                print(f'{key} = "<你在 --set 时用的那个密码（{len(v)} 字符）>"')
            else:
                print(f'{key} = "{values[key]}"')
    print("-" * 56)
    print("\n⚠️ 密码不会显示出来。请从你生成密码的地方复制，不要照抄上面的占位文字。")
    print("   填完保存后，Streamlit Cloud 会自动重新部署。")
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    args = sys.argv[1:]
    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        return 0
    if "--set" in args:
        return cmd_set([a for a in args if a != "--set"])
    if "--check" in args:
        return cmd_check()
    if "--init" in args:
        return cmd_init()
    if "--print-secrets" in args:
        return cmd_print_secrets()
    print(f"不认识的参数：{' '.join(args)}\n")
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
