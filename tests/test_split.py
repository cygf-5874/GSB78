"""语义清单 1-5、9：split 的分摊 / 守恒 / 最大余数 / 权重 / 退款 / 边界。"""

import unittest

from moneysplit import split


class SplitTest(unittest.TestCase):
    def test_rule1_split_matches_weights_length(self):
        result = split(7, [1, 2, 4])
        self.assertEqual(len(result), 3)
        self.assertEqual(result, [1, 2, 4])

    def test_rule1_simple_equal_weights_distribution(self):
        self.assertEqual(split(100, [1, 1, 1]), [34, 33, 33])

    def test_rule2_sum_always_equals_total_positive(self):
        self.assertEqual(sum(split(12345, [3, 7, 11, 19])), 12345)

    def test_rule2_single_element_gets_whole_total(self):
        self.assertEqual(split(999, [5]), [999])

    def test_rule3_largest_remainder_takes_extra_cent_first(self):
        # 权重 1:3 时余数 2 在第一份，余数 0 在第二份；余数大的先拿 +1。
        self.assertEqual(split(10, [1, 3]), [3, 7])

    def test_rule3_tied_remainders_go_to_lower_index(self):
        # 三份基础份额都是 33、余数并列 1，多出来的 1 分给索引 0。
        self.assertEqual(split(100, [1, 1, 1]), [34, 33, 33])

    def test_rule3_five_way_tie_gives_extras_to_first_two(self):
        self.assertEqual(split(2, [1, 1, 1, 1, 1]), [1, 1, 0, 0, 0])

    def test_rule3_remainder_descending_order_across_three(self):
        # 基础 [1,2,4]，仅第 2 份余 1，+1 归余数最大的第 2 份。
        self.assertEqual(split(8, [1, 2, 4]), [1, 2, 5])

    def test_rule3_no_remainder_exact_division(self):
        self.assertEqual(split(100, [2, 3, 5]), [20, 30, 50])

    def test_rule3_scaled_weights_same_ratio(self):
        self.assertEqual(split(11, [2, 2]), [6, 5])

    def test_rule4_zero_weights_degenerate_to_equal_split(self):
        self.assertEqual(split(11, [0, 0, 0]), [4, 4, 3])

    def test_rule4_all_zero_weights_two_parts_tie_index_order(self):
        self.assertEqual(split(10, [0, 0]), [5, 5])

    def test_rule4_single_zero_weight_takes_whole_total(self):
        self.assertEqual(split(10, [0]), [10])

    def test_rule4_mixed_zero_and_nonzero_weights(self):
        self.assertEqual(split(100, [0, 1, 0, 2]), [0, 33, 0, 67])

    def test_rule4_zero_weight_share_gets_nothing(self):
        self.assertEqual(split(100, [0, 0, 1]), [0, 0, 100])

    def test_rule5_negative_total_is_negated_positive_split(self):
        self.assertEqual(split(-100, [1, 1, 1]), [-34, -33, -33])

    def test_rule5_negative_total_with_uneven_remainders(self):
        self.assertEqual(split(-7, [1, 2, 4]), [-1, -2, -4])

    def test_rule5_negative_total_single_cent_lands_on_first_part(self):
        self.assertEqual(split(-1, [1, 1, 1]), [-1, 0, 0])

    def test_rule5_negative_total_still_conserves(self):
        result = split(-987, [3, 1, 4, 1, 5])
        self.assertEqual(sum(result), -987)

    def test_rule5_negative_all_zero_weights_index_order(self):
        self.assertEqual(split(-11, [0, 0]), [-6, -5])

    def test_rule9_total_zero_returns_all_zeros(self):
        self.assertEqual(split(0, [1, 2]), [0, 0])

    def test_rule9_total_zero_with_zero_weights(self):
        self.assertEqual(split(0, [0, 0]), [0, 0])

    def test_rule9_empty_weights_with_nonzero_total_raises(self):
        with self.assertRaises(ValueError):
            split(100, [])

    def test_rule9_empty_weights_with_negative_total_raises(self):
        with self.assertRaises(ValueError):
            split(-5, [])

    def test_rule9_empty_weights_with_zero_total_returns_empty(self):
        self.assertEqual(split(0, []), [])

    def test_rule4_negative_weight_raises(self):
        with self.assertRaises(ValueError):
            split(100, [1, -1, 1])

    def test_rule4_negative_first_weight_raises(self):
        with self.assertRaises(ValueError):
            split(100, [-1, 0])

    def test_rule12_split_is_deterministic_across_calls(self):
        first = split(333, [7, 11, 13, 17])
        second = split(333, [7, 11, 13, 17])
        self.assertEqual(first, second)
        self.assertEqual(sum(first), 333)

    def test_rule12_split_does_not_mutate_weights(self):
        weights = [3, 1, 2]
        original = list(weights)
        split(100, weights)
        self.assertEqual(weights, original)

    def test_rule2_large_total_conservation(self):
        result = split(1000000, [1, 1, 1])
        self.assertEqual(result, [333334, 333333, 333333])
        self.assertEqual(sum(result), 1000000)


if __name__ == "__main__":
    unittest.main()
