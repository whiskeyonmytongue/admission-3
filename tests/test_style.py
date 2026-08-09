"""표준 라이브러리 스타일 검사기의 성공·실패 경계를 검증한다."""

import io
import unittest
from unittest.mock import patch

from scripts import check_style


class StyleCheckerTests(unittest.TestCase):
    def test_overlong_line_returns_failure_with_location(self):
        path = check_style.ROOT / "probe.py"
        source = '"""Temporary style probe."""\n\nprobe = "{0}"\n'.format(
            "x" * 90
        )
        captured_err = io.StringIO()
        with patch(
            "scripts.check_style.source_paths",
            return_value=[path],
        ), patch(
            "scripts.check_style.decode_source",
            return_value=source,
        ), patch("sys.stderr", captured_err):
            result = check_style.main()

        self.assertEqual(result, 1)
        self.assertIn("probe.py:3", captured_err.getvalue())
        self.assertIn("79자를 초과", captured_err.getvalue())

    def test_empty_discovery_returns_failure(self):
        captured_err = io.StringIO()
        with patch(
            "scripts.check_style.source_paths",
            return_value=[],
        ), patch("sys.stderr", captured_err):
            result = check_style.main()

        self.assertEqual(result, 1)
        self.assertIn("검사할", captured_err.getvalue())

    def test_indent_check_allows_alignment_but_rejects_wide_suite(self):
        path = check_style.ROOT / "probe.py"
        aligned = "value = call(\n     first,\n     second,\n)\n"
        errors = []
        check_style.check_python_lines(path, aligned, errors)
        self.assertEqual(errors, [])

        wide_suite = "if True:\n        value = 1\n"
        check_style.check_python_lines(path, wide_suite, errors)
        self.assertTrue(any("4칸" in item for item in errors))

    def test_invalid_utf8_reports_line_number(self):
        path = check_style.ROOT / "probe.py"
        errors = []
        with patch("pathlib.Path.read_bytes", return_value=b"valid\n\xff"):
            self.assertIsNone(check_style.decode_source(path, errors))

        self.assertTrue(any("probe.py:2" in item for item in errors))

    def test_control_flow_string_is_not_a_docstring(self):
        path = check_style.ROOT / "probe.py"
        source = '"""Module."""\nif True:\n    "{0}"\n'.format(
            "x" * 70
        )
        errors = []

        check_style.check_python_lines(path, source, errors)

        self.assertEqual(errors, [])

    def test_inline_comment_uses_code_line_limit(self):
        path = check_style.ROOT / "probe.py"
        source = 'value = "{0}"  # note\n'.format("x" * 58)
        errors = []

        check_style.check_python_lines(path, source, errors)

        self.assertEqual(errors, [])

    def test_crlf_reports_its_actual_line(self):
        path = check_style.ROOT / "probe.py"
        errors = []
        with patch(
            "pathlib.Path.read_bytes",
            return_value=b"first\nsecond\r\n",
        ):
            check_style.decode_source(path, errors)

        self.assertTrue(any("probe.py:2" in item for item in errors))
        self.assertFalse(any("probe.py:1" in item for item in errors))

    def test_function_length_includes_decorator(self):
        path = check_style.ROOT / "probe.py"
        source = (
            '"""Module."""\n\n@decorator\ndef public():\n'
            '    """Public function."""\n'
            + "    pass\n" * 48
        )
        errors = []

        check_style.check_ast(path, source, errors)

        self.assertTrue(any("50줄" in item for item in errors))

    def test_compiler_context_error_fails_style_check(self):
        path = check_style.ROOT / "probe.py"
        errors = []

        check_style.check_ast(path, '"""Module."""\nreturn\n', errors)

        self.assertTrue(any("문법 오류" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
