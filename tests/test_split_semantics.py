"""分摊语义：清单第 1/2/3/4/5/9/10/12 条。"""

import unittest

from moneysplit import merge, split


class SplitBasicTest(unittest.TestCase):
    """第 1 条：按权重分摊；第 3 条：最大余数法。"""

    def test_s01_three_way_equal_weights(self):
        self.assertEqual(split(100, [1, 1, 1]), [34, 33, 33])

    def test_s01_weighted_split_exact(self):
        self.assertEqual(split(10, [1, 2]), [3, 7])

    def test_s01_weight_order_matters(self):
        self.assertEqual(split(10, [2, 1]), [7, 3])

    def test_s03_leftover_goes_to_largest_remainder(self):
        self.assertEqual(split(8, [1, 2, 4]), [1, 2, 5])

    def test_s03_remainder_tie_prefers_lower_index(self):
        self.assertEqual(split(10, [1, 1, 2]), [3, 2, 5])

    def test_s03_leftover_distributed_one_each(self):
        self.assertEqual(split(2, [1, 1, 1]), [1, 1, 0])


class SplitConservationTest(unittest.TestCase):
    """第 2 条：总和守恒；第 12 条：纯函数。"""

    def test_s02_sum_conserved_positive(self):
        for total, weights in [
            (100, [1, 1, 1]),
            (10, [1, 2]),
            (7, [0, 0, 0]),
            (5, [3, 1, 1]),
            (1, [1, 1]),
            (999, [7, 13, 29, 1]),
        ]:
            with self.subTest(total=total, weights=weights):
                self.assertEqual(sum(split(total, weights)), total)

    def test_s02_sum_conserved_negative(self):
        for total, weights in [(-100, [1, 1, 1]), (-2, [1, 1, 1]), (-7, [2, 3])]:
            with self.subTest(total=total, weights=weights):
                self.assertEqual(sum(split(total, weights)), total)

    def test_s12_same_input_same_output(self):
        first = split(100, [1, 1, 1])
        for _ in range(5):
            self.assertEqual(split(100, [1, 1, 1]), first)


class SplitWeightsTest(unittest.TestCase):
    """第 4 条：权重非负；全零退化为均分。"""

    def test_s04_all_zero_weights_split_evenly(self):
        self.assertEqual(split(7, [0, 0, 0]), [3, 2, 2])

    def test_s04_all_zero_weights_leftover_by_index(self):
        self.assertEqual(split(5, [0, 0]), [3, 2])

    def test_s04_zero_weight_gets_nothing(self):
        self.assertEqual(split(10, [1, 0]), [10, 0])

    def test_s04_negative_weight_rejected(self):
        with self.assertRaises(ValueError):
            split(10, [-1, 5])

    def test_s04_all_negative_weights_rejected(self):
        with self.assertRaises(ValueError):
            split(10, [-2, -3])


class SplitNegativeTotalTest(unittest.TestCase):
    """第 5 条：负总额按绝对值分摊后整体取负。"""

    def test_s05_negative_three_way(self):
        self.assertEqual(split(-100, [1, 1, 1]), [-34, -33, -33])

    def test_s05_negative_leftover_by_index(self):
        self.assertEqual(split(-2, [1, 1, 1]), [-1, -1, 0])

    def test_s05_negative_weighted(self):
        self.assertEqual(split(-10, [1, 2]), [-3, -7])


class SplitEdgeCasesTest(unittest.TestCase):
    """第 9 条：单元素、空列表、total = 0。"""

    def test_s09_empty_weights_zero_total_returns_empty(self):
        self.assertEqual(split(0, []), [])

    def test_s09_empty_weights_positive_total_raises(self):
        with self.assertRaises(ValueError):
            split(1, [])

    def test_s09_empty_weights_negative_total_raises(self):
        with self.assertRaises(ValueError):
            split(-1, [])

    def test_s09_zero_total_gives_zero_shares(self):
        self.assertEqual(split(0, [1, 2, 3]), [0, 0, 0])

    def test_s09_single_element(self):
        self.assertEqual(split(3, [1]), [3])

    def test_s09_single_element_negative(self):
        self.assertEqual(split(-3, [1]), [-3])


class MergeTest(unittest.TestCase):
    """第 10 条：merge 与 split 互逆。"""

    def test_s10_merge_adds_parts(self):
        self.assertEqual(merge([30, 70]), 100)

    def test_s10_merge_empty_is_zero(self):
        self.assertEqual(merge([]), 0)

    def test_s10_merge_accepts_tuple(self):
        self.assertEqual(merge((1, 2, 3)), 6)

    def test_s10_merge_negative_parts(self):
        self.assertEqual(merge([-34, -33, -33]), -100)

    def test_s10_merge_inverts_split(self):
        for total, weights in [
            (100, [1, 1, 1]),
            (-100, [1, 1, 1]),
            (10, [1, 2]),
            (0, [5, 5]),
            (7, [0, 0, 0]),
        ]:
            with self.subTest(total=total, weights=weights):
                self.assertEqual(merge(split(total, weights)), total)


if __name__ == "__main__":
    unittest.main()
