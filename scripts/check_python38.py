"""모든 Python 소스가 Python 3.8 문법으로 파싱되는지 확인한다."""

import ast
from pathlib import Path


def main() -> None:
    paths = [Path("main.py"), Path("npu.py"), Path("simulator.py")]
    paths.extend(sorted(Path("tests").glob("*.py")))
    paths.extend(sorted(Path("scripts").glob("*.py")))
    for path in paths:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 8))
    print("[PASS] Python 3.8 문법 호환")


if __name__ == "__main__":
    main()
