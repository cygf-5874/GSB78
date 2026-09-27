"""把整数金额按权重、百分比或上限分摊到若干份。

所有函数都是纯函数：同样的输入永远得到同样的结果，不依赖随机源、时间或全局状态。
"""

import math

from .errors import InsufficientCapacity


def _require_int(value, label):
    """只接受 int；float / Decimal / bool 这些一律拒掉。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("%s 必须是 int，实际是 %s" % (label, type(value).__name__))
    return value


def _require_ints(values, label):
    """校验一串非负整数（权重 / 上限 / 百分比），返回 list。"""
    if not isinstance(values, (list, tuple)):
        raise TypeError("%s 必须是 list 或 tuple，实际是 %s"
                        % (label, type(values).__name__))
    items = [_require_int(item, label) for item in values]
    if items and min(items) < 0:
        raise ValueError("%s 不能为负" % label)
    return items


def _decompose(total_cents):
    """把金额拆成 (符号, 绝对值)：符号是 +1 / -1，绝对值非负。"""
    sign = int(math.copysign(1, total_cents))
    magnitude = max(total_cents, -total_cents)
    return sign, magnitude


def _remainder_order(total, weights):
    """份额索引按「余数从大到小、索引升序」排好；权重全零时退化成索引升序。

    返回的只是顺序表，分摊有余额要补时按这个顺序逐份 +1。
    """
    total_weight = sum(weights)
    if total_weight == 0:
        return list(range(len(weights)))
    products = [total * weight for weight in weights]
    return sorted(
        range(len(weights)),
        key=lambda index: (-(products[index] % total_weight), index),
    )


def _largest_remainder_detail(total, weights):
    """最大余数法：返回 (份额表, 被补过一的索引表)。

    份额先各取 floor，余额按 ``_remainder_order`` 的顺序逐份 +1；
    补过的索引按升序返回，供 journal 逐条记账用。
    """
    count = len(weights)
    total_weight = sum(weights)
    if total_weight != 0:
        products = [total * weight for weight in weights]
        shares = [product // total_weight for product in products]
    else:
        shares = [total // count] * count
    leftover = total - sum(shares)
    boosted = sorted(_remainder_order(total, weights)[:leftover])
    for index in boosted:
        shares[index] += 1
    return shares, boosted


def _largest_remainder(total, weights):
    """把非负的 total 按非负的 weights 分成 len(weights) 份。"""
    return _largest_remainder_detail(total, weights)[0]


def split(total_cents, weights):
    """按权重把 total_cents 分到 len(weights) 份，返回整数分列表。

    负数按绝对值分摊后整体取负；空权重表只在 total_cents 为 0 时合法。
    """
    _require_int(total_cents, "total_cents")
    weights = _require_ints(weights, "weight")
    if not weights:
        if total_cents != 0:
            raise ValueError("weights 为空时 total_cents 必须为 0")
        return []
    sign, magnitude = _decompose(total_cents)
    shares = _largest_remainder(magnitude, weights)
    return [sign * share for share in shares]


def merge(parts):
    """把若干份合并回总额；与 split 互逆。"""
    if not isinstance(parts, (list, tuple)):
        raise TypeError("parts 必须是 list 或 tuple，实际是 %s" % type(parts).__name__)
    total = 0
    for part in parts:
        _require_int(part, "part")
        total += part
    return total


def split_by_percent(total_cents, percents):
    """按百分比分摊。

    百分比之和必须是 100 或 1（两种写法都接受）；先各取 floor，
    剩下的整数分全部给**第一个非零份额**。
    """
    _require_int(total_cents, "total_cents")
    percents = _require_ints(percents, "percent")
    total_percent = sum(percents)
    if total_percent not in (100, 1):
        raise ValueError("百分比之和必须是 100 或 1，实际是 %d" % total_percent)
    sign, magnitude = _decompose(total_cents)
    shares = [magnitude * percent // total_percent for percent in percents]
    leftover = magnitude - sum(shares)
    for index in range(len(percents)):
        if percents[index] != 0:
            shares[index] += leftover
            break
    return [sign * share for share in shares]


def allocate(total_cents, caps):
    """带上限的分摊：每份不超过 caps[i]。

    容量（caps 之和）不足时抛 ``InsufficientCapacity``，异常携带还差的分数。
    """
    _require_int(total_cents, "total_cents")
    caps = _require_ints(caps, "cap")
    sign, magnitude = _decompose(total_cents)
    capacity = sum(caps)
    if magnitude > capacity:
        raise InsufficientCapacity(magnitude - capacity)
    if not caps:
        return []
    return [sign * share for share in _largest_remainder(magnitude, caps)]
