"""全局配置与业务常量。

放什么：
    - 数据库连接参数：host / port / user / password / database / charset
    - 业务常量：预约时段粒度、卡默认有效期、分页大小、状态枚举等

约定：
    - 其他模块只读本文件，不修改
    - 密码最终要改成读环境变量或 .env（见 docs/DESIGN.md 的 C 类事项），
      不要把真实密码提交进仓库

示例结构：
    DB_CONFIG = {
        "host": "127.0.0.1", "port": 3306, "user": "root",
        "password": "", "database": "study_room", "charset": "utf8mb4",
    }
    SLOT_HOURS = 1        # 预约时段粒度（小时），见 DESIGN.md B1
    PAGE_SIZE = 20        # 列表分页大小
    CARD_STATUS_OK = "正常"
"""
