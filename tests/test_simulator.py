import json
import tempfile
import unittest
from pathlib import Path

from npu import generate_patterns
from simulator import analyze_data, extract_pattern_size, load_json_file, performance_rows


def valid_data():
    cross, x_pattern = generate_patterns(3)
    return {
        "filters": {"size_3": {"cross": cross, "x": x_pattern}},
        "patterns": {
            "size_3_1": {"input": cross, "expected": "+"},
            "size_3_2": {"input": x_pattern, "expected": "x"},
        },
    }


class JsonAnalysisTests(unittest.TestCase):
    def test_valid_cases_pass_with_normalized_labels(self):
        report = analyze_data(valid_data())
        self.assertEqual((report["total"], report["passed"], report["failed"]), (2, 2, 0))
        self.assertEqual(report["results"][0]["predicted"], "Cross")
        self.assertEqual(report["results"][1]["predicted"], "X")

    def test_bad_case_does_not_stop_following_case(self):
        data = valid_data()
        data["patterns"] = {
            "size_3_bad": {"input": [[1, 2], [3, 4]], "expected": "+"},
            "size_3_good": data["patterns"]["size_3_2"],
        }
        report = analyze_data(data)
        self.assertEqual((report["total"], report["passed"], report["failed"]), (2, 1, 1))
        self.assertIn("크기 불일치", report["results"][0]["reason"])
        self.assertEqual(report["results"][1]["status"], "PASS")

    def test_malformed_schema_is_reported_per_case(self):
        data = valid_data()
        data["patterns"] = {
            "wrong_key": {"input": [[1]], "expected": "+"},
            "size_3_missing": {"expected": "+"},
            "size_3_valid": data["patterns"]["size_3_1"],
        }
        report = analyze_data(data)
        self.assertEqual((report["passed"], report["failed"]), (1, 2))
        self.assertIn("size_{N}_{idx}", report["results"][0]["reason"])
        self.assertIn("input과 expected", report["results"][1]["reason"])

    def test_missing_filter_only_fails_related_case(self):
        data = valid_data()
        data["patterns"]["size_5_1"] = {
            "input": [[0.0] * 5 for _ in range(5)],
            "expected": "+",
        }
        report = analyze_data(data)
        self.assertEqual((report["passed"], report["failed"]), (2, 1))
        self.assertIn("size_5 필터가 없습니다", report["results"][2]["reason"])

    def test_patterns_must_be_mapping(self):
        with self.assertRaisesRegex(ValueError, "patterns"):
            analyze_data({"filters": {}, "patterns": []})

    def test_load_json_reports_parse_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "읽을 수 없습니다"):
                load_json_file(path)


class ExtractionAndPerformanceTests(unittest.TestCase):
    def test_extract_pattern_size(self):
        self.assertEqual(extract_pattern_size("size_25_6"), 25)
        for key in ("size_x_1", "size_5", 5):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    extract_pattern_size(key)

    def test_performance_has_required_sizes_and_repetitions(self):
        rows = performance_rows(10)
        self.assertEqual([row["size"] for row in rows], [3, 5, 13, 25])
        self.assertEqual([row["operations"] for row in rows], [9, 25, 169, 625])
        self.assertTrue(all(row["repetitions"] >= 10 for row in rows))


if __name__ == "__main__":
    unittest.main()
