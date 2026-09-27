"""跨笔分摊：把多笔金额按同一组权重逐笔分摊，再逐份累加。

**纯函数**：同样的输入永远得到同样的结果，``journal`` 的逐条顺序也固定。

``settle(entries, weights)`` 返回 ``(net, journal)``：

- ``net[j]`` 是第 j 份的净额，等于各笔在该份上的份额之和；
- ``journal`` 里是每一笔各自的**余额分配**记录 ``(entry_index, share_index, delta)``，
  按 ``(entry_index, share_index)`` 升序排列；``delta`` 是该笔在那一份上补的符号量。

某一笔为负时，该笔先按绝对值分摊，再整体取负后累加。
"""

from .split import _decompose, _largest_remainder_detail, _require_int, _require_ints


def _require_entries(entries):
    """entries 是一串可正可负的整数金额。"""
    if not isinstance(entries, (list, tuple)):
        raise TypeError("entries 必须是 list 或 tuple，实际是 %s"
                        % type(entries).__name__)
    return [_require_int(amount, "entry") for amount in entries]


def settle(entries, weights):
    """把多笔金额逐笔分摊后逐份累加，返回 ``(net, journal)``。

    空权重表只在每一笔金额都为 0 时合法；空 entries 返回全零净额。
    """
    entries = _require_entries(entries)
    weights = _require_ints(weights, "weight")
    count = len(weights)
    if count == 0:
        if any(amount != 0 for amount in entries):
            raise ValueError("weights 为空时每笔金额必须为 0")
        return [], []
    net = [0] * count
    journal = []
    for entry_index, amount in enumerate(entries):
        sign, magnitude = _decompose(amount)
        shares, boosted = _largest_remainder_detail(magnitude, weights)
        for index in range(count):
            net[index] += sign * shares[index]
        for index in boosted:
            journal.append((entry_index, index, sign))
    return net, journal
