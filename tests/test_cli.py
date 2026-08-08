import io
import unittest
from unittest.mock import patch

import main


class CliTests(unittest.TestCase):
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
        with patch("builtins.input", side_effect=EOFError), patch("sys.stdout", captured):
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


if __name__ == "__main__":
    unittest.main()
