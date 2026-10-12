class BizError(Exception):

    """业务规则不满足时抛出

    约定 services 层用抛异常的方式表达失败，
    ui 层捕获它并把 message 显示成红字。
    """
