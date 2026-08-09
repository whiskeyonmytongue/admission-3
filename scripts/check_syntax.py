"""발견된 모든 Python 소스를 현재 인터프리터로 컴파일한다."""

import py_compile
import sys
from pathlib import Path
from typing import List

from scripts.check_style import source_paths


def python_paths() -> List[Path]:
    """스타일 검사와 같은 검색 범위에서 Python 파일만 반환한다."""
    return [path for path in source_paths() if path.suffix == ".py"]


def main() -> int:
    """전체 Python 파일을 컴파일하고 실패 여부를 종료 코드로 반환한다."""
    paths = python_paths()
    if not paths:
        print("Syntax check: FAIL - Python 파일이 없습니다.", file=sys.stderr)
        return 1
    try:
        for path in paths:
            py_compile.compile(str(path), doraise=True)
    except (OSError, py_compile.PyCompileError) as error:
        print("Syntax check: FAIL - {0}".format(error), file=sys.stderr)
        return 1
    print("Syntax check: PASS ({0} files)".format(len(paths)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
