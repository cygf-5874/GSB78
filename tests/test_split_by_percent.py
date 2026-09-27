"""百分比分摊：清单第 7 条。"""

import unittest

from moneysplit import split_by_percent


class PercentSplitTest(unittest.TestCase):
    def test_s07_even_split_no_leftover(self):
        self.assertEqual(split_by_percent(100, [50, 50]), [50, 50])

    def test_s07_leftover_goes_to_first_nonzero(self):
        self.assertEqual(split_by_percent(101, [50, 50]), [51, 50])

    def test_s07_leftover_skips_leading_zero_share(self):
        self.assertEqual(split_by_percent(101, [0, 50, 50]), [0, 51, 50])

    def test_s07_floor_before_leftover(self):
        self.assertEqual(split_by_percent(101, [1, 99]), [2, 99])

    def test_s07_sum_one_is_accepted(self):
        self.assertEqual(split_by_percent(10, [1]), [10])

    def test_s07_sum_one_with_zero_head(self):
        self.assertEqual(split_by_percent(7, [0, 1]), [0, 7])

    def test_s07_sum_must_be_100_or_1(self):
        for percents in ([30, 30], [1, 1], [], [50, 49], [2]):
            with self.subTest(percents=percents):
                with self.assertRaises(ValueError):
                    split_by_percent(10, percents)

    def test_s07_negative_total(self):
        self.assertEqual(split_by_percent(-101, [50, 50]), [-51, -50])

    def test_s07_zero_total(self):
        self.assertEqual(split_by_percent(0, [50, 50]), [0, 0])

    def test_s07_negative_percent_rejected(self):
        with self.assertRaises(ValueError):
            split_by_percent(10, [50, -10, 60])

    def test_s07_sum_conserved(self):
        for total, percents in [
            (101, [50, 50]),
            (100, [33, 33, 34]),
            (-101, [50, 50]),
            (7, [0, 1]),
            (103, [25, 25, 25, 25]),
        ]:
            with self.subTest(total=total, percents=percents):
                self.assertEqual(sum(split_by_percent(total, percents)), total)


if __name__ == "__main__":
    unittest.main()
