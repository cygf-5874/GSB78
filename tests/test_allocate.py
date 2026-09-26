"""语义清单 8、9、12：allocate 带上限分摊与 InsufficientCapacity。"""

import unittest

from moneysplit import InsufficientCapacity, MoneySplitError, allocate


class AllocateTest(unittest.TestCase):
    def test_rule8_each_part_respects_cap_with_remainder(self):
        self.assertEqual(allocate(5, [2, 10]), [1, 4])

    def test_rule8_cap_on_first_part_is_binding(self):
        self.assertEqual(allocate(10, [2, 10]), [2, 8])

    def test_rule8_exact_capacity_saturates_each_cap(self):
        self.assertEqual(allocate(12, [2, 10]), [2, 10])

    def test_rule8_equal_caps_distribute_evenly(self):
        self.assertEqual(allocate(100, [100, 100]), [50, 50])

    def test_rule8_smaller_total_under_equal_caps(self):
        self.assertEqual(allocate(6, [100, 100]), [3, 3])

    def test_rule8_single_cap_takes_whole_total(self):
        self.assertEqual(allocate(100, [100]), [100])

    def test_rule8_zero_cap_share_gets_nothing(self):
        self.assertEqual(allocate(100, [0, 100]), [0, 100])

    def test_rule8_multiple_zero_caps_skipped(self):
        self.assertEqual(allocate(100, [0, 0, 100]), [0, 0, 100])

    def test_rule8_three_way_remainder_index_order(self):
        self.assertEqual(allocate(7, [3, 3, 3]), [3, 2, 2])

    def test_rule8_four_way_remainder_index_order(self):
        self.assertEqual(allocate(10, [3, 3, 3, 3]), [3, 3, 2, 2])

    def test_rule8_capacity_filled_with_no_remainder(self):
        self.assertEqual(allocate(20, [5, 5, 5, 5]), [5, 5, 5, 5])

    def test_rule8_one_cent_under_capacity(self):
        self.assertEqual(allocate(19, [5, 5, 5, 5]), [5, 5, 5, 4])

    def test_rule8_insufficient_capacity_raises_named_error(self):
        with self.assertRaises(InsufficientCapacity):
            allocate(100, [30, 30, 30])

    def test_rule8_insufficient_capacity_is_value_error_family(self):
        self.assertTrue(issubclass(InsufficientCapacity, MoneySplitError))

    def test_rule8_shortfall_carries_missing_amount(self):
        try:
            allocate(100, [10, 20, 30])
        except InsufficientCapacity as error:
            self.assertEqual(error.shortfall, 40)
        else:
            self.fail("应当抛出 InsufficientCapacity")

    def test_rule8_shortfall_single_cent(self):
        try:
            allocate(100, [99])
        except InsufficientCapacity as error:
            self.assertEqual(error.shortfall, 1)
        else:
            self.fail("应当抛出 InsufficientCapacity")

    def test_rule8_shortfall_empty_caps_is_whole_total(self):
        try:
            allocate(5, [])
        except InsufficientCapacity as error:
            self.assertEqual(error.shortfall, 5)
        else:
            self.fail("应当抛出 InsufficientCapacity")

    def test_rule8_zero_cap_with_total_is_insufficient(self):
        try:
            allocate(100, [0])
        except InsufficientCapacity as error:
            self.assertEqual(error.shortfall, 100)
        else:
            self.fail("应当抛出 InsufficientCapacity")

    def test_rule5_negative_total_allocation_distribution(self):
        self.assertEqual(allocate(-5, [10, 10]), [-3, -2])

    def test_rule5_negative_total_insufficient_capacity_shortfall(self):
        try:
            allocate(-100, [10, 20, 30])
        except InsufficientCapacity as error:
            self.assertEqual(error.shortfall, 40)
        else:
            self.fail("应当抛出 InsufficientCapacity")

    def test_rule5_negative_total_zero_capacity_shortfall(self):
        try:
            allocate(-11, [0, 10])
        except InsufficientCapacity as error:
            self.assertEqual(error.shortfall, 1)
        else:
            self.fail("应当抛出 InsufficientCapacity")

    def test_rule9_zero_total_allocate_is_all_zeros(self):
        self.assertEqual(allocate(0, [1, 1]), [0, 0])

    def test_rule9_zero_total_empty_caps_returns_empty(self):
        self.assertEqual(allocate(0, []), [])

    def test_rule8_negative_cap_raises(self):
        with self.assertRaises(ValueError):
            allocate(10, [-1, 20])

    def test_rule12_allocate_is_deterministic(self):
        first = allocate(89, [30, 30, 30])
        second = allocate(89, [30, 30, 30])
        self.assertEqual(first, second)
        self.assertEqual(first, [30, 30, 29])

    def test_rule12_allocate_does_not_mutate_caps(self):
        caps = [10, 20]
        original = list(caps)
        allocate(5, caps)
        self.assertEqual(caps, original)


if __name__ == "__main__":
    unittest.main()
