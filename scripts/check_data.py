"""합성 data.json의 전체 케이스가 통과하는지 검증한다."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


EXPECTED_FILTER_KEYS = {"size_5", "size_13", "size_25"}
EXPECTED_PATTERN_KEYS = {
    "size_5_1",
    "size_5_2",
    "size_13_1",
    "size_13_2",
    "size_25_1",
    "size_25_2",
}


def validate_dataset(data: object) -> None:
    """합성 데이터의 출처 표식과 고정된 케이스 구성을 확인한다."""
    if not isinstance(data, dict):
        raise ValueError("최상위 데이터가 객체가 아닙니다.")
    metadata = data.get("_meta")
    if not isinstance(metadata, dict):
        raise ValueError("_meta가 객체가 아닙니다.")
    if metadata.get("official_attachment") is not False:
        raise ValueError("합성 데이터 출처 표식이 올바르지 않습니다.")
    for key in ("source", "rule", "purpose"):
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            raise ValueError("_meta.{0} 설명이 없습니다.".format(key))
    filters = data.get("filters")
    patterns = data.get("patterns")
    if not isinstance(filters, dict) or set(filters) != EXPECTED_FILTER_KEYS:
        raise ValueError("필터 크기 구성이 5·13·25와 일치하지 않습니다.")
    valid_patterns = (
        isinstance(patterns, dict)
        and set(patterns) == EXPECTED_PATTERN_KEYS
    )
    if not valid_patterns:
        raise ValueError("패턴 케이스 ID 6개가 기준과 일치하지 않습니다.")


def main() -> None:
    """정적 데이터의 6개 케이스가 모두 통과하는지 확인한다."""
    from simulator import analyze_data, load_json_file

    try:
        data = load_json_file(DATA_PATH)
        validate_dataset(data)
        report = analyze_data(data)
    except ValueError as error:
        raise SystemExit("[FAIL] data.json 구조: {0}".format(error))
    summary = (report["total"], report["passed"], report["failed"])
    if summary != (6, 6, 0):
        raise SystemExit("[FAIL] data.json 결과: {0}".format(summary))
    print("[PASS] data.json 6/6")


if __name__ == "__main__":
    main()
