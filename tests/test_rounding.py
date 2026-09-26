"""语义清单 6：round_half_up / round_half_even / round_floor / round_ceil。"""

import unittest
from fractions import Fraction

from moneysplit import (
    round_ceil,
    round_floor,
    round_half_even,
    round_half_up,
)


class RoundHalfUpTest(unittest.TestCase):
    def test_rule6_half_up_positive_half_goes_toward_infinity(self):
        self.assertEqual(round_half_up(Fraction(1, 2)), 1)

    def test_rule6_half_up_three_halves(self):
        self.assertEqual(round_half_up(Fraction(3, 2)), 2)

    def test_rule6_half_up_negative_half_goes_toward_infinity(self):
        self.assertEqual(round_half_up(Fraction(-1, 2)), 0)

    def test_rule6_half_up_negative_three_halves(self):
        self.assertEqual(round_half_up(Fraction(-3, 2)), -1)

    def test_rule6_half_up_five_halves(self):
        self.assertEqual(round_half_up(Fraction(5, 2)), 3)

    def test_rule6_half_up_large_odd_half(self):
        self.assertEqual(round_half_up(Fraction(1000001, 2)), 500001)

    def test_rule6_half_up_large_negative_odd_half(self):
        self.assertEqual(round_half_up(Fraction(-1000001, 2)), -500000)

    def test_rule6_half_up_non_tie_fraction_rounds_nearest(self):
        self.assertEqual(round_half_up(Fraction(3, 4)), 1)
        self.assertEqual(round_half_up(Fraction(-3, 4)), -1)

    def test_rule6_half_up_plain_integers_pass_through(self):
        self.assertEqual(round_half_up(Fraction(4)), 4)
        self.assertEqual(round_half_up(-7), -7)


class RoundHalfEvenTest(unittest.TestCase):
    def test_rule6_half_even_positive_half_to_even_zero(self):
        self.assertEqual(round_half_even(Fraction(1, 2)), 0)

    def test_rule6_half_even_three_halves_to_even_two(self):
        self.assertEqual(round_half_even(Fraction(3, 2)), 2)

    def test_rule6_half_even_five_halves_to_even_four(self):
        self.assertEqual(round_half_even(Fraction(5, 2)), 2)

    def test_rule6_half_even_negative_half_to_even_zero(self):
        self.assertEqual(round_half_even(Fraction(-1, 2)), 0)

    def test_rule6_half_even_negative_three_halves_to_negative_two(self):
        self.assertEqual(round_half_even(Fraction(-3, 2)), -2)

    def test_rule6_half_even_seven_halves_to_even_four(self):
        self.assertEqual(round_half_even(Fraction(7, 2)), 4)

    def test_rule6_half_even_negative_five_halves_to_negative_two(self):
        self.assertEqual(round_half_even(Fraction(-5, 2)), -2)

    def test_rule6_half_even_large_odd_halves_to_even(self):
        self.assertEqual(round_half_even(Fraction(1000001, 2)), 500000)
        self.assertEqual(round_half_even(Fraction(-1000001, 2)), -500000)

    def test_rule6_half_even_non_ties_round_nearest(self):
        self.assertEqual(round_half_even(Fraction(3, 4)), 1)
        self.assertEqual(round_half_even(Fraction(-3, 4)), -1)
        self.assertEqual(round_half_even(Fraction(9, 2)), 4)

    def test_rule6_half_even_integers_pass_through(self):
        self.assertEqual(round_half_even(6), 6)
        self.assertEqual(round_half_even(-7), -7)

    def test_rule6_half_even_eleven_halves_to_even_six(self):
        self.assertEqual(round_half_even(Fraction(11, 2)), 6)


class RoundFloorTest(unittest.TestCase):
    def test_rule6_floor_positive_half(self):
        self.assertEqual(round_floor(Fraction(1, 2)), 0)

    def test_rule6_floor_three_halves(self):
        self.assertEqual(round_floor(Fraction(3, 2)), 1)

    def test_rule6_floor_negative_half_goes_down(self):
        self.assertEqual(round_floor(Fraction(-1, 2)), -1)

    def test_rule6_floor_negative_three_halves(self):
        self.assertEqual(round_floor(Fraction(-3, 2)), -2)

    def test_rule6_floor_quarter_values(self):
        self.assertEqual(round_floor(Fraction(1, 4)), 0)
        self.assertEqual(round_floor(Fraction(-1, 4)), -1)

    def test_rule6_floor_three_quarters(self):
        self.assertEqual(round_floor(Fraction(3, 4)), 0)
        self.assertEqual(round_floor(Fraction(-3, 4)), -1)

    def test_rule6_floor_integers_pass_through(self):
        self.assertEqual(round_floor(7), 7)
        self.assertEqual(round_floor(-7), -7)
        self.assertEqual(round_floor(0), 0)


class RoundCeilTest(unittest.TestCase):
    def test_rule6_ceil_positive_half(self):
        self.assertEqual(round_ceil(Fraction(1, 2)), 1)

    def test_rule6_ceil_three_halves(self):
        self.assertEqual(round_ceil(Fraction(3, 2)), 2)

    def test_rule6_ceil_negative_half_goes_up_to_zero(self):
        self.assertEqual(round_ceil(Fraction(-1, 2)), 0)

    def test_rule6_ceil_negative_three_halves(self):
        self.assertEqual(round_ceil(Fraction(-3, 2)), -1)

    def test_rule6_ceil_quarter_values(self):
        self.assertEqual(round_ceil(Fraction(1, 4)), 1)
        self.assertEqual(round_ceil(Fraction(-1, 4)), 0)

    def test_rule6_ceil_three_quarters(self):
        self.assertEqual(round_ceil(Fraction(3, 4)), 1)
        self.assertEqual(round_ceil(Fraction(-3, 4)), 0)

    def test_rule6_ceil_integers_pass_through(self):
        self.assertEqual(round_ceil(7), 7)
        self.assertEqual(round_ceil(-7), -7)
        self.assertEqual(round_ceil(0), 0)

    def test_rule6_all_rounders_return_int(self):
        for rounder in (round_half_up, round_half_even, round_floor, round_ceil):
            self.assertIsInstance(rounder(Fraction(3, 2)), int)


if __name__ == "__main__":
    unittest.main()
