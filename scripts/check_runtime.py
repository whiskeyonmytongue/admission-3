"""제출 검증이 정확한 최소 Python 버전에서 실행되는지 확인한다."""

import sys
from typing import Tuple


EXPECTED_VERSION = (3, 8)


def current_version() -> Tuple[int, int]:
    """현재 Python의 major·minor 버전을 반환한다."""
    return sys.version_info[:2]


def main() -> int:
    """정확한 검증 버전이면 성공하고 아니면 실행 방법을 안내한다."""
    actual = current_version()
    expected_text = ".".join(str(value) for value in EXPECTED_VERSION)
    actual_text = ".".join(str(value) for value in actual)
    if actual != EXPECTED_VERSION:
        print(
            "Runtime check: FAIL - CI 검증은 Python {0}이 필요합니다. "
            "현재 버전: {1}".format(expected_text, actual_text),
            file=sys.stderr,
        )
        return 1
    print("Runtime check: PASS (Python {0})".format(actual_text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
