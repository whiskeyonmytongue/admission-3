"""행렬 검증, MAC 계산, 판정 정책을 검증한다."""

import math
import unittest

from npu import (
    EPSILON,
    benchmark_mac,
    compare_representations,
    compare_scores,
    flatten_matrix,
    generate_patterns,
    mac_flat,
    mac_nested,
    normalize_label,
    validate_matrix,
)


class MatrixAndMacTests(unittest.TestCase):
    def test_cross_scores_higher_for_cross_pattern(self):
        cross, x_pattern = generate_patterns(3)
        self.assertEqual(mac_nested(cross, cross), 5.0)
        self.assertEqual(mac_nested(cross, x_pattern), 1.0)

    def test_flat_and_nested_have_same_score(self):
        cross, x_pattern = generate_patterns(5)
        self.assertEqual(
            mac_nested(cross, x_pattern),
            mac_flat(cross, x_pattern),
        )
        self.assertEqual(len(flatten_matrix(cross)), 25)

    def test_representation_comparison_uses_same_score_and_repetitions(self):
        cross, _ = generate_patterns(13)
        result = compare_representations(cross, cross, 10)
        self.assertEqual(result["score"], 25.0)
        self.assertEqual(result["repetitions"], 10.0)
        self.assertGreaterEqual(result["nested_ms"], 0.0)
        self.assertGreaterEqual(result["flat_ms"], 0.0)

    def test_ragged_and_size_mismatch_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "정사각형"):
            validate_matrix([[1, 2], [3]])
        with self.assertRaisesRegex(ValueError, "크기 불일치"):
            mac_nested([[1]], [[1, 0], [0, 1]])

    def test_invalid_numbers_are_rejected(self):
        for value in (True, "1", math.nan, math.inf, 10**10000):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_matrix([[value]])

    def test_finite_inputs_cannot_return_infinite_mac_score(self):
        huge = [[1e308]]
        with self.assertRaisesRegex(ValueError, "MAC 연산 결과"):
            mac_nested(huge, huge)
        with self.assertRaisesRegex(ValueError, "MAC 연산 결과"):
            mac_flat(huge, huge)


class PolicyTests(unittest.TestCase):
    def test_difference_below_epsilon_is_tie(self):
        self.assertEqual(
            compare_scores(1.0, 1.0 + EPSILON / 2.0, "A", "B"),
            "UNDECIDED",
        )

    def test_difference_exactly_epsilon_is_not_tie(self):
        self.assertEqual(compare_scores(EPSILON, 0.0, "A", "B"), "A")

    def test_label_normalization(self):
        self.assertEqual(normalize_label("+"), "Cross")
        self.assertEqual(normalize_label("cross"), "Cross")
        self.assertEqual(normalize_label(" X "), "X")
        with self.assertRaises(ValueError):
            normalize_label("circle")

    def test_even_pattern_size_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "홀수"):
            generate_patterns(4)

    def test_benchmark_rejects_invalid_repetition(self):
        with self.assertRaises(ValueError):
            benchmark_mac(mac_nested, [[1]], [[1]], 0)

    def test_benchmark_rejects_non_finite_operation_result(self):
        with self.assertRaisesRegex(ValueError, "MAC 연산 결과"):
            benchmark_mac(lambda _a, _b: math.inf, [[1]], [[1]], 1)


if __name__ == "__main__":
    unittest.main()
