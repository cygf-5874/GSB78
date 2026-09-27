"""冒烟用例：只走最顺的那几条公开路径。"""

import unittest

from moneysplit import merge, split, split_by_percent


class SmokeTest(unittest.TestCase):
    def test_merge_adds_parts(self):
        self.assertEqual(merge([30, 70]), 100)

    def test_split_assigns_shares_in_order(self):
        self.assertEqual(split(10, [1, 1]), [5, 5])
        self.assertEqual(split(7, [1, 2]), [2, 5])

    def test_percent_split_assigns_shares(self):
        self.assertEqual(split_by_percent(100, [50, 50]), [50, 50])


if __name__ == "__main__":
    unittest.main()
