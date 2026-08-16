"""과제 공식 data.json의 구조와 예상 판정 결과를 검증한다."""

import hashlib
import json
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
EXPECTED_SEMANTIC_SHA256 = (
    "215fe11081ef87c6c0b67399cbcbf0abcdebe26e15a2fb46ede5d9047e900618"
)
EXPECTED_SUMMARY = (6, 3, 3)
EXPECTED_FAILURES = {"size_5_1", "size_13_2", "size_25_1"}
EXPECTED_PASSES = {"size_5_2", "size_13_1", "size_25_2"}
EXPECTED_TIE_REASON = "epsilon 정책에 따라 동점(UNDECIDED)"


def semantic_digest(data: object) -> str:
    """공백과 줄바꿈에 영향받지 않는 데이터 내용 해시를 반환한다."""
    encoded = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_dataset(data: object) -> None:
    """공식 데이터의 메타 정보, 케이스 구성과 내용 해시를 확인한다."""
    if not isinstance(data, dict):
        raise ValueError("최상위 데이터가 객체가 아닙니다.")
    if data.get("meta") != {"version": "1.0", "type": "json"}:
        raise ValueError("공식 데이터의 meta가 일치하지 않습니다.")
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
    try:
        digest = semantic_digest(data)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(
            "공식 데이터에 검증할 수 없는 값이 있습니다: {0}".format(error)
        ) from error
    if digest != EXPECTED_SEMANTIC_SHA256:
        raise ValueError("공식 데이터의 내용 해시가 일치하지 않습니다.")


def main() -> None:
    """공식 데이터의 3 PASS·3 예상 동점 FAIL을 확인한다."""
    from simulator import analyze_data, load_json_file

    try:
        data = load_json_file(DATA_PATH)
        validate_dataset(data)
        report = analyze_data(data)
    except ValueError as error:
        raise SystemExit("[FAIL] data.json 구조: {0}".format(error))
    summary = (report["total"], report["passed"], report["failed"])
    if summary != EXPECTED_SUMMARY:
        raise SystemExit("[FAIL] data.json 결과: {0}".format(summary))
    failures = {
        result["id"]
        for result in report["results"]
        if result["status"] == "FAIL"
    }
    if failures != EXPECTED_FAILURES:
        raise SystemExit("[FAIL] 예상 동점 케이스: {0}".format(failures))
    passes = {
        result["id"]
        for result in report["results"]
        if result["status"] == "PASS"
    }
    if passes != EXPECTED_PASSES:
        raise SystemExit("[FAIL] 예상 통과 케이스: {0}".format(passes))
    tie_results = [
        result
        for result in report["results"]
        if result["id"] in EXPECTED_FAILURES
    ]
    if any(
        result["predicted"] != "UNDECIDED"
        or result["reason"] != EXPECTED_TIE_REASON
        for result in tie_results
    ):
        raise SystemExit("[FAIL] 공식 데이터의 동점 판정 사유가 달라졌습니다.")
    print("[PASS] 공식 data.json: 6개 중 3 PASS, 3 FAIL(예상 동점)")


if __name__ == "__main__":
    main()
