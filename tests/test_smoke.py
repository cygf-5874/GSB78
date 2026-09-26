"""冒烟用例：只走最顺的那条路径。"""

import unittest

from moneysplit import merge, split, split_by_percent


class SmokeTest(unittest.TestCase):
    def test_merge_adds_parts(self):
        self.assertEqual(merge([30, 70]), 100)

    def test_split_keeps_total(self):
        self.assertEqual(sum(split(10, [1, 1])), 10)

    def test_percent_split_keeps_total(self):
        self.assertEqual(sum(split_by_percent(100, [50, 50])), 100)


if __name__ == "__main__":
    unittest.main()
