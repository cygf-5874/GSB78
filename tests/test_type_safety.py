"""只收 int：清单第 11 条。"""

import unittest
from decimal import Decimal

from moneysplit import allocate, merge, split, split_by_percent


class TypeSafetyTest(unittest.TestCase):
    def test_s11_float_total_rejected(self):
        with self.assertRaises(TypeError):
            split(10.0, [1, 1])

    def test_s11_decimal_total_rejected(self):
        with self.assertRaises(TypeError):
            split(Decimal(10), [1, 1])

    def test_s11_float_weight_rejected(self):
        with self.assertRaises(TypeError):
            split(10, [1.5, 1])

    def test_s11_decimal_weight_rejected(self):
        with self.assertRaises(TypeError):
            split(10, [Decimal(1), 1])

    def test_s11_non_list_weights_rejected(self):
        with self.assertRaises(TypeError):
            split(10, 5)

    def test_s11_percent_float_rejected(self):
        with self.assertRaises(TypeError):
            split_by_percent(10, [50.0, 50])

    def test_s11_percent_total_float_rejected(self):
        with self.assertRaises(TypeError):
            split_by_percent(10.0, [50, 50])

    def test_s11_cap_float_rejected(self):
        with self.assertRaises(TypeError):
            allocate(5, [2.0, 3])

    def test_s11_allocate_total_float_rejected(self):
        with self.assertRaises(TypeError):
            allocate(5.5, [1, 2])

    def test_s11_merge_float_part_rejected(self):
        with self.assertRaises(TypeError):
            merge([1.5])

    def test_s11_merge_decimal_part_rejected(self):
        with self.assertRaises(TypeError):
            merge([Decimal(1)])

    def test_s11_merge_non_list_rejected(self):
        with self.assertRaises(TypeError):
            merge(5)


if __name__ == "__main__":
    unittest.main()
