"""콘솔 입력과 명령행 종료 경계를 검증한다."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class CliTests(unittest.TestCase):
    def test_run_cli_handles_eof_directly(self):
        for prefix in ([], ["1"], ["2"]):
            with self.subTest(prefix=prefix):
                answers = iter(prefix)
                lines = []

                def raise_eof_after_prefix(_prompt):
                    try:
                        return next(answers)
                    except StopIteration:
                        raise EOFError

                result = main.run_cli(
                    raise_eof_after_prefix,
                    lines.append,
                )
                output = "\n".join(lines)
                self.assertEqual(result, 0)
                self.assertIn("안전하게 종료", output)
                self.assertNotIn("저장", output)

    def test_run_cli_handles_keyboard_interrupt_directly(self):
        for prefix in ([], ["1"], ["2"]):
            with self.subTest(prefix=prefix):
                answers = iter(prefix)
                lines = []

                def raise_interrupt_after_prefix(_prompt):
                    try:
                        return next(answers)
                    except StopIteration:
                        raise KeyboardInterrupt

                result = main.run_cli(
                    raise_interrupt_after_prefix,
                    lines.append,
                )
                output = "\n".join(lines)
                self.assertEqual(result, 0)
                self.assertIn("안전하게 종료", output)
                self.assertNotIn("저장", output)

    def test_read_matrix_retries_nan_and_infinity(self):
        answers = iter(["nan", "inf", "3"])
        lines = []

        matrix = main.read_matrix(
            "필터",
            1,
            lambda _prompt: next(answers),
            lines.append,
        )

        self.assertEqual(matrix, [[3.0]])
        self.assertEqual("\n".join(lines).count("유한한 숫자"), 2)

    def test_json_option_reports_success(self):
        captured_out = io.StringIO()
        data_path = Path(__file__).parents[1] / "data.json"
        with patch("sys.stdout", captured_out):
            result = main.main(["--json", str(data_path)])

        self.assertEqual(result, 0)
        self.assertIn("통과: 6개", captured_out.getvalue())

    def test_json_option_reports_failed_case(self):
        data = {
            "filters": {
                "size_1": {"cross": [[1]], "x": [[0]]},
            },
            "patterns": {
                "size_1_1": {"input": [[1]], "expected": "x"},
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "failed.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            captured_out = io.StringIO()
            with patch("sys.stdout", captured_out):
                result = main.main(["--json", str(path)])

        self.assertEqual(result, 1)
        self.assertIn("실패: 1개", captured_out.getvalue())

    def test_json_option_reports_missing_file(self):
        captured_out = io.StringIO()
        captured_err = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            with patch("sys.stdout", captured_out), patch(
                "sys.stderr",
                captured_err,
            ):
                result = main.main(["--json", str(missing)])

        self.assertEqual(result, 1)
        self.assertIn("읽을 수 없습니다", captured_err.getvalue())

    def test_json_option_reports_invalid_filters_schema(self):
        data = {"filters": [], "patterns": {}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid-schema.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            captured_out = io.StringIO()
            captured_err = io.StringIO()
            with patch("sys.stdout", captured_out), patch(
                "sys.stderr",
                captured_err,
            ):
                result = main.main(["--json", str(path)])

        self.assertEqual(result, 1)
        self.assertIn("filters는 객체여야 합니다", captured_err.getvalue())

    def test_generate_rejects_even_size(self):
        captured_out = io.StringIO()
        captured_err = io.StringIO()
        with patch("sys.stdout", captured_out), patch(
            "sys.stderr",
            captured_err,
        ):
            result = main.main(["--generate", "4"])
        self.assertEqual(result, 1)
        self.assertIn("홀수", captured_err.getvalue())

    def test_invalid_menu_and_row_are_retried(self):
        answers = iter(
            [
                "9",
                "1",
                "0 1",
                "0 1 0",
                "1 1 1",
                "0 1 0",
                "1 0 1",
                "0 1 0",
                "1 0 1",
                "0 1 0",
                "1 1 1",
                "0 1 0",
            ]
        )
        lines = []
        result = main.run_cli(lambda _prompt: next(answers), lines.append)
        output = "\n".join(lines)
        self.assertEqual(result, 0)
        self.assertIn("1 또는 2", output)
        self.assertIn("각 줄에 3개의 숫자", output)
        self.assertIn("판정: A", output)

    def test_eof_exits_without_traceback(self):
        captured = io.StringIO()
        with patch("builtins.input", side_effect=EOFError), patch(
            "sys.stdout",
            captured,
        ):
            result = main.main([])
        self.assertEqual(result, 0)
        self.assertIn("안전하게 종료", captured.getvalue())
        self.assertNotIn("Traceback", captured.getvalue())

    def test_keyboard_interrupt_exits_without_traceback(self):
        captured = io.StringIO()
        with patch("builtins.input", side_effect=KeyboardInterrupt), patch(
            "sys.stdout", captured
        ):
            result = main.main([])
        self.assertEqual(result, 0)
        self.assertIn("안전하게 종료", captured.getvalue())

    def test_argument_parsing_interrupt_exits_without_traceback(self):
        captured = io.StringIO()
        with patch("main.build_parser") as parser_builder, patch(
            "sys.stdout", captured
        ):
            parser_builder.return_value.parse_args.side_effect = (
                KeyboardInterrupt
            )
            result = main.main([])

        self.assertEqual(result, 0)
        self.assertIn("안전하게 종료", captured.getvalue())


if __name__ == "__main__":
    unittest.main()
