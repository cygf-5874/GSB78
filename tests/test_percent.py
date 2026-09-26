"""语义清单 7、9、12：split_by_percent 的 floor + 余数归第一个非零份额。"""

import unittest

from moneysplit import split_by_percent


class PercentTest(unittest.TestCase):
    def test_rule7_remainder_all_goes_to_first_nonzero_share(self):
        self.assertEqual(split_by_percent(101, [50, 50]), [51, 50])

    def test_rule7_fractional_split_three_parts(self):
        self.assertEqual(split_by_percent(10, [30, 30, 40]), [3, 3, 4])

    def test_rule7_sum_one_notation_is_accepted(self):
        self.assertEqual(split_by_percent(10, [1]), [10])

    def test_rule7_sum_one_with_leading_zero_share(self):
        self.assertEqual(split_by_percent(10, [0, 1]), [0, 10])

    def test_rule7_sum_one_with_trailing_zero_share(self):
        self.assertEqual(split_by_percent(10, [1, 0]), [10, 0])

    def test_rule7_sum_one_with_multiple_zeros(self):
        self.assertEqual(split_by_percent(10, [1, 0, 0]), [10, 0, 0])

    def test_rule7_exact_division_has_no_remainder(self):
        self.assertEqual(split_by_percent(100, [50, 50]), [50, 50])

    def test_rule7_first_nonzero_skips_leading_zero_share(self):
        self.assertEqual(split_by_percent(11, [0, 50, 50]), [0, 6, 5])

    def test_rule7_first_nonzero_is_last_share(self):
        self.assertEqual(split_by_percent(7, [0, 1]), [0, 7])

    def test_rule7_zero_first_share_gets_nothing_with_remainder(self):
        self.assertEqual(split_by_percent(100, [0, 100]), [0, 100])

    def test_rule7_hundred_zero_split_exact(self):
        self.assertEqual(split_by_percent(5, [100, 0]), [5, 0])

    def test_rule7_four_way_remainder_lands_on_first(self):
        self.assertEqual(split_by_percent(10, [25, 25, 25, 25]), [4, 2, 2, 2])

    def test_rule7_ninety_nine_one_split(self):
        self.assertEqual(split_by_percent(100, [99, 1]), [99, 1])

    def test_rule5_negative_percent_split_is_negated(self):
        self.assertEqual(split_by_percent(-101, [50, 50]), [-51, -50])

    def test_rule5_negative_percent_remainder_on_first_nonzero(self):
        self.assertEqual(split_by_percent(-3, [50, 50]), [-2, -1])

    def test_rule5_negative_percent_skips_leading_zero(self):
        self.assertEqual(split_by_percent(-11, [0, 50, 50]), [0, -6, -5])

    def test_rule5_negative_percent_single_cent(self):
        self.assertEqual(split_by_percent(-1, [100, 0]), [-1, 0])

    def test_rule9_percent_total_zero_is_all_zeros(self):
        self.assertEqual(split_by_percent(0, [50, 50]), [0, 0])

    def test_rule7_bad_sum_eighty_raises(self):
        with self.assertRaises(ValueError):
            split_by_percent(100, [40, 40])

    def test_rule7_bad_sum_one_o_one_raises(self):
        with self.assertRaises(ValueError):
            split_by_percent(100, [50, 51])

    def test_rule7_two_ones_do_not_count_as_one_notation(self):
        with self.assertRaises(ValueError):
            split_by_percent(100, [1, 1])

    def test_rule7_empty_percents_raises(self):
        with self.assertRaises(ValueError):
            split_by_percent(100, [])

    def test_rule7_empty_percents_even_for_zero_total_raises(self):
        with self.assertRaises(ValueError):
            split_by_percent(0, [])

    def test_rule7_all_zero_percents_raises(self):
        with self.assertRaises(ValueError):
            split_by_percent(100, [0, 0])

    def test_rule7_negative_percent_raises(self):
        with self.assertRaises(ValueError):
            split_by_percent(100, [-50, 150])

    def test_rule12_percent_split_is_deterministic(self):
        first = split_by_percent(123, [20, 30, 50])
        second = split_by_percent(123, [20, 30, 50])
        self.assertEqual(first, second)
        self.assertEqual(sum(first), 123)

    def test_rule12_percent_split_does_not_mutate_input(self):
        percents = [50, 50]
        original = list(percents)
        split_by_percent(101, percents)
        self.assertEqual(percents, original)


if __name__ == "__main__":
    unittest.main()
