"""带上限分摊：清单第 8 条。"""

import unittest

from moneysplit import InsufficientCapacity, MoneySplitError, allocate


class AllocateTest(unittest.TestCase):
    def test_s08_caps_respected(self):
        self.assertEqual(allocate(5, [2, 10]), [1, 4])

    def test_s08_exact_capacity_is_allowed(self):
        self.assertEqual(allocate(5, [2, 3]), [2, 3])

    def test_s08_each_share_within_cap(self):
        caps = [3, 3, 3]
        shares = allocate(7, caps)
        self.assertEqual(shares, [3, 2, 2])
        for share, cap in zip(shares, caps):
            self.assertLessEqual(share, cap)

    def test_s08_insufficient_capacity_raises(self):
        with self.assertRaises(InsufficientCapacity):
            allocate(10, [2, 3])

    def test_s08_shortfall_amount(self):
        with self.assertRaises(InsufficientCapacity) as caught:
            allocate(10, [2, 3])
        self.assertEqual(caught.exception.shortfall, 5)

    def test_s08_shortfall_mentioned_in_message(self):
        with self.assertRaises(InsufficientCapacity) as caught:
            allocate(10, [2, 3])
        self.assertIn("5", str(caught.exception))

    def test_s08_error_is_moneysplit_error(self):
        with self.assertRaises(MoneySplitError):
            allocate(10, [2, 3])

    def test_s08_negative_total(self):
        self.assertEqual(allocate(-5, [2, 10]), [-1, -4])

    def test_s08_negative_total_shortfall(self):
        with self.assertRaises(InsufficientCapacity) as caught:
            allocate(-10, [2, 3])
        self.assertEqual(caught.exception.shortfall, 5)

    def test_s08_empty_caps_zero_total(self):
        self.assertEqual(allocate(0, []), [])

    def test_s08_empty_caps_nonzero_raises(self):
        with self.assertRaises(InsufficientCapacity):
            allocate(1, [])

    def test_s08_zero_total(self):
        self.assertEqual(allocate(0, [1, 2]), [0, 0])

    def test_s08_sum_conserved(self):
        for total, caps in [(5, [2, 10]), (7, [3, 3, 3]), (-5, [2, 10]), (0, [4, 4])]:
            with self.subTest(total=total, caps=caps):
                self.assertEqual(sum(allocate(total, caps)), total)


if __name__ == "__main__":
    unittest.main()
