"""语义清单 10、11：merge 互逆，以及所有入口只接受 int。"""

import unittest
from decimal import Decimal

from moneysplit import (
    allocate,
    merge,
    split,
    split_by_percent,
)


class MergeTest(unittest.TestCase):
    def test_rule10_merge_sums_parts(self):
        self.assertEqual(merge([34, 33, 33]), 100)

    def test_rule10_merge_empty_is_zero(self):
        self.assertEqual(merge([]), 0)

    def test_rule10_merge_single_part(self):
        self.assertEqual(merge([100]), 100)

    def test_rule10_merge_mixed_signs(self):
        self.assertEqual(merge([1, -1]), 0)

    def test_rule10_merge_negative_parts(self):
        self.assertEqual(merge([-34, -33, -33]), -100)

    def test_rule10_merge_is_inverse_of_split_equal_weights(self):
        self.assertEqual(merge(split(100, [1, 1, 1])), 100)

    def test_rule10_merge_is_inverse_of_split_uneven_weights(self):
        self.assertEqual(merge(split(777, [3, 1, 4, 1, 5, 9])), 777)

    def test_rule10_merge_is_inverse_of_split_negative_total(self):
        self.assertEqual(merge(split(-233, [2, 8, 3])), -233)

    def test_rule10_merge_is_inverse_of_split_zero_weights(self):
        self.assertEqual(merge(split(55, [0, 0, 0])), 55)

    def test_rule10_merge_is_inverse_of_percent_split(self):
        self.assertEqual(merge(split_by_percent(101, [50, 50])), 101)

    def test_rule10_merge_is_inverse_of_allocate(self):
        self.assertEqual(merge(allocate(89, [30, 30, 30])), 89)

    def test_rule10_merge_returns_int(self):
        self.assertIsInstance(merge([2, 2, 2]), int)

    def test_rule12_merge_does_not_mutate_parts(self):
        parts = [1, 2, 3]
        original = list(parts)
        merge(parts)
        self.assertEqual(parts, original)


class IntOnlyTest(unittest.TestCase):
    def test_rule11_split_float_total_raises_type_error(self):
        with self.assertRaises(TypeError):
            split(100.0, [1])

    def test_rule11_split_decimal_total_raises_type_error(self):
        with self.assertRaises(TypeError):
            split(Decimal(100), [1])

    def test_rule11_split_float_weight_raises_type_error(self):
        with self.assertRaises(TypeError):
            split(100, [1.0, 1])

    def test_rule11_split_decimal_weight_raises_type_error(self):
        with self.assertRaises(TypeError):
            split(100, [Decimal(1), 1])

    def test_rule11_percent_float_total_raises_type_error(self):
        with self.assertRaises(TypeError):
            split_by_percent(100.0, [50, 50])

    def test_rule11_percent_float_share_raises_type_error(self):
        with self.assertRaises(TypeError):
            split_by_percent(100, [50.0, 50])

    def test_rule11_percent_decimal_share_raises_type_error(self):
        with self.assertRaises(TypeError):
            split_by_percent(1, [Decimal(100)])

    def test_rule11_allocate_float_total_raises_type_error(self):
        with self.assertRaises(TypeError):
            allocate(10.0, [100])

    def test_rule11_allocate_float_cap_raises_type_error(self):
        with self.assertRaises(TypeError):
            allocate(10, [10.0])

    def test_rule11_allocate_decimal_cap_raises_type_error(self):
        with self.assertRaises(TypeError):
            allocate(1, [Decimal(1)])

    def test_rule11_merge_float_part_raises_type_error(self):
        with self.assertRaises(TypeError):
            merge([1.0])

    def test_rule11_merge_decimal_part_raises_type_error(self):
        with self.assertRaises(TypeError):
            merge([Decimal(1)])


if __name__ == "__main__":
    unittest.main()
