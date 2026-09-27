"""moneysplit 的异常类型。"""


class MoneySplitError(Exception):
    """moneysplit 所有异常的基类。"""


class InsufficientCapacity(MoneySplitError):
    """容量不足以完成分摊。

    异常自带 ``shortfall`` 属性，表示「还差多少分」才够分。
    """

    def __init__(self, shortfall):
        self.shortfall = shortfall
        super().__init__("capacity short by %d cents" % shortfall)
