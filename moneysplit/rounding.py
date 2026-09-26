"""四种舍入模式。

入参是精确的有理数（``int`` 或 ``fractions.Fraction``），返回 ``int``。
四个函数都是纯函数：四舍五入只在**恰好半值**时区分模式。

- ``round_floor``   向下取整（朝 -∞）
- ``round_ceil``    向上取整（朝 +∞）
- ``round_half_up`` 半值朝 +∞ 取整
- ``round_half_even`` 半值向偶数取整（银行家舍入）
"""

from fractions import Fraction


def _as_fraction(value):
    """把入参化成 Fraction，返回 (分子, 分母)。"""
    fraction = Fraction(value)
    return fraction.numerator, fraction.denominator


def round_floor(value):
    """向下取整。"""
    numerator, denominator = _as_fraction(value)
    return numerator // denominator


def round_ceil(value):
    """向上取整。"""
    numerator, denominator = _as_fraction(value)
    return -((-numerator) // denominator)


def round_half_up(value):
    """半值朝 +∞ 取整。"""
    numerator, denominator = _as_fraction(value)
    return (2 * numerator + denominator) // (2 * denominator)


def round_half_even(value):
    """半值向偶数取整。"""
    numerator, denominator = _as_fraction(value)
    floor = numerator // denominator
    remainder = numerator - floor * denominator
    doubled = remainder * 2
    if doubled < denominator:
        return floor
    if doubled > denominator:
        return floor + 1
    if floor % 2 == 0:
        return floor
    return floor + 1
