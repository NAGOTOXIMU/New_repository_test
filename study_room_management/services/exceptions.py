class BizError(Exception):
    """业务规则不满足时抛出。约定 services 抛它，ui 捕获后显示成红字。"""
