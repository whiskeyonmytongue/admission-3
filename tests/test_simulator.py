"""JSON 케이스 격리와 성능 리포트를 검증한다."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from npu import generate_patterns
from scripts import check_data
from simulator import (
    analyze_data,
    bonus_comparison_rows,
    extract_pattern_size,
    load_json_file,
    performance_rows,
)


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
    def test_static_data_contains_six_passing_cases(self):
        project_data = load_json_file(Path(__file__).parents[1] / "data.json")
        report = analyze_data(project_data)
        self.assertEqual(
            (report["total"], report["passed"], report["failed"]),
            (6, 6, 0),
        )
        self.assertFalse(project_data["_meta"]["official_attachment"])

    def test_valid_cases_pass_with_normalized_labels(self):
        report = analyze_data(valid_data())
        self.assertEqual(
            (report["total"], report["passed"], report["failed"]),
            (2, 2, 0),
        )
        self.assertEqual(report["results"][0]["predicted"], "Cross")
        self.assertEqual(report["results"][1]["predicted"], "X")

    def test_bad_case_does_not_stop_following_case(self):
        data = valid_data()
        data["patterns"] = {
            "size_3_bad": {"input": [[1, 2], [3, 4]], "expected": "+"},
            "size_3_good": data["patterns"]["size_3_2"],
        }
        report = analyze_data(data)
        self.assertEqual(
            (report["total"], report["passed"], report["failed"]),
            (2, 1, 1),
        )
        self.assertIn("크기 불일치", report["results"][0]["reason"])
        self.assertEqual(report["results"][1]["status"], "PASS")

    def test_huge_integer_only_fails_its_case(self):
        data = valid_data()
        huge_input = [row[:] for row in data["patterns"]["size_3_1"]["input"]]
        huge_input[0][0] = 10**10000
        data["patterns"]["size_3_1"]["input"] = huge_input

        report = analyze_data(data)

        self.assertEqual(
            (report["total"], report["passed"], report["failed"]),
            (2, 1, 1),
        )
        self.assertIn("float 범위", report["results"][0]["reason"])
        self.assertEqual(report["results"][1]["status"], "PASS")

    def test_file_huge_integer_only_fails_its_case(self):
        huge_integer = "9" * 5000
        document = (
            '{"filters":{"size_1":{"cross":[[1]],"x":[[0]]}},'
            '"patterns":{'
            '"size_1_bad":{"input":[['
            + huge_integer
            + ']],"expected":"cross"},'
            '"size_1_good":{"input":[[1]],"expected":"cross"}}}'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "huge.json"
            path.write_text(document, encoding="utf-8")
            report = analyze_data(load_json_file(path))

        self.assertEqual(
            (report["total"], report["passed"], report["failed"]),
            (2, 1, 1),
        )
        self.assertIn("float 범위", report["results"][0]["reason"])
        self.assertEqual(report["results"][1]["status"], "PASS")

    def test_huge_json_integer_is_stable_and_json_safe(self):
        huge_integer = "9" * 5000
        document = (
            '{"filters":{"size_2":{"cross":[[1,0],[0,1]],'
            '"x":[[0,1],[1,0]]}},"patterns":{'
            '"size_2_bad":{"input":[['
            + huge_integer
            + ']],"expected":"cross"}},"_meta":{"n":'
            + huge_integer
            + "}}"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "huge-metadata.json"
            path.write_text(document, encoding="utf-8")
            data = load_json_file(path)
            default_reason = analyze_data(data)["results"][0]["reason"]
            json.dumps(data)
            setter = getattr(sys, "set_int_max_str_digits", None)
            getter = getattr(sys, "get_int_max_str_digits", None)
            if setter is not None and getter is not None:
                previous_limit = getter()
                try:
                    setter(0)
                    unlimited_reason = analyze_data(
                        load_json_file(path)
                    )["results"][0]["reason"]
                finally:
                    setter(previous_limit)
                self.assertEqual(unlimited_reason, default_reason)

        self.assertIsInstance(data["_meta"]["n"], int)
        self.assertIn("크기 불일치", default_reason)

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

    def test_filters_must_be_mapping(self):
        with self.assertRaisesRegex(ValueError, "filters는 객체여야 합니다"):
            analyze_data({"filters": [], "patterns": {}})

    def test_load_json_reports_parse_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "읽을 수 없습니다"):
                load_json_file(path)

    def test_load_json_reports_excessive_nesting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deep.json"
            path.write_text("{}", encoding="utf-8")
            with patch("simulator.json.load", side_effect=RecursionError):
                with self.assertRaisesRegex(ValueError, "읽을 수 없습니다"):
                    load_json_file(path)


class ExtractionAndPerformanceTests(unittest.TestCase):
    def test_data_check_uses_project_file_outside_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [sys.executable, str(check_data.__file__)],
                cwd=directory,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[PASS] data.json 6/6", completed.stdout)

    def test_extract_pattern_size(self):
        self.assertEqual(extract_pattern_size("size_25_6"), 25)
        for key in ("size_x_1", "size_5", 5):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    extract_pattern_size(key)

    def test_performance_has_required_sizes_and_repetitions(self):
        rows = performance_rows(10)
        self.assertEqual([row["size"] for row in rows], [3, 5, 13, 25])
        self.assertEqual(
            [row["operations"] for row in rows],
            [9, 25, 169, 625],
        )
        self.assertTrue(all(row["repetitions"] >= 10 for row in rows))

    def test_bonus_compares_all_sizes_with_same_repetitions(self):
        rows = bonus_comparison_rows(10)
        self.assertEqual([row["size"] for row in rows], [3, 5, 13, 25])
        self.assertTrue(all(row["repetitions"] == 10.0 for row in rows))


if __name__ == "__main__":
    unittest.main()
