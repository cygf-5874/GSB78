"""四种舍入模式：清单第 6 条。"""

import unittest
from fractions import Fraction

from moneysplit import round_ceil, round_floor, round_half_even, round_half_up


class RoundFloorTest(unittest.TestCase):
    def test_s06_floor_positive_fraction(self):
        self.assertEqual(round_floor(Fraction(7, 2)), 3)

    def test_s06_floor_negative_fraction(self):
        self.assertEqual(round_floor(Fraction(-7, 2)), -4)

    def test_s06_floor_negative_half(self):
        self.assertEqual(round_floor(Fraction(-1, 2)), -1)

    def test_s06_floor_int_passthrough(self):
        self.assertEqual(round_floor(5), 5)


class RoundCeilTest(unittest.TestCase):
    def test_s06_ceil_positive_fraction(self):
        self.assertEqual(round_ceil(Fraction(7, 2)), 4)

    def test_s06_ceil_negative_fraction(self):
        self.assertEqual(round_ceil(Fraction(-7, 2)), -3)

    def test_s06_ceil_int_passthrough(self):
        self.assertEqual(round_ceil(5), 5)


class RoundHalfUpTest(unittest.TestCase):
    def test_s06_half_up_exact_half_rounds_up(self):
        self.assertEqual(round_half_up(Fraction(5, 2)), 3)
        self.assertEqual(round_half_up(Fraction(3, 2)), 2)

    def test_s06_half_up_negative_half_toward_positive_infinity(self):
        self.assertEqual(round_half_up(Fraction(-3, 2)), -1)
        self.assertEqual(round_half_up(Fraction(-1, 2)), 0)
        self.assertEqual(round_half_up(Fraction(-5, 2)), -2)

    def test_s06_half_up_quarters(self):
        self.assertEqual(round_half_up(Fraction(7, 4)), 2)
        self.assertEqual(round_half_up(Fraction(5, 4)), 1)

    def test_s06_half_up_int_passthrough(self):
        self.assertEqual(round_half_up(3), 3)


class RoundHalfEvenTest(unittest.TestCase):
    def test_s06_half_even_half_to_even(self):
        self.assertEqual(round_half_even(Fraction(5, 2)), 2)
        self.assertEqual(round_half_even(Fraction(3, 2)), 2)
        self.assertEqual(round_half_even(Fraction(7, 2)), 4)
        self.assertEqual(round_half_even(Fraction(1, 2)), 0)

    def test_s06_half_even_negative_half(self):
        self.assertEqual(round_half_even(Fraction(-3, 2)), -2)
        self.assertEqual(round_half_even(Fraction(-1, 2)), 0)

    def test_s06_half_even_non_half_values(self):
        self.assertEqual(round_half_even(Fraction(3, 4)), 1)
        self.assertEqual(round_half_even(Fraction(5, 4)), 1)
        self.assertEqual(round_half_even(Fraction(9, 4)), 2)

    def test_s06_half_even_int_passthrough(self):
        self.assertEqual(round_half_even(3), 3)


class RoundReturnTypeTest(unittest.TestCase):
    def test_s06_results_are_int(self):
        for func in (round_floor, round_ceil, round_half_up, round_half_even):
            with self.subTest(func=func.__name__):
                self.assertIsInstance(func(Fraction(5, 2)), int)
                self.assertIsInstance(func(4), int)


if __name__ == "__main__":
    unittest.main()
