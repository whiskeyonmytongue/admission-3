"""JSON 일괄 분석과 성능 측정을 담당한다."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from npu import (
    EPSILON,
    benchmark_mac,
    compare_scores,
    generate_patterns,
    mac_nested,
    normalize_label,
    validate_matrix,
)


PATTERN_KEY = re.compile(r"^size_(\d+)_(.+)$")
PERFORMANCE_SIZES = (3, 5, 13, 25)


def load_json_file(path: Path) -> Dict[str, Any]:
    """UTF-8 JSON 파일을 읽고 최상위 객체를 확인한다."""
    try:
        with path.open("r", encoding="utf-8") as source:
            data = json.load(source)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("JSON 파일을 읽을 수 없습니다: {0}".format(error))
    if not isinstance(data, dict):
        raise ValueError("JSON 최상위 값은 객체여야 합니다.")
    return data


def extract_pattern_size(case_id: object) -> int:
    """size_{N}_{idx} 키에서 양의 크기 N을 추출한다."""
    if not isinstance(case_id, str):
        raise ValueError("패턴 키는 문자열이어야 합니다.")
    matched = PATTERN_KEY.fullmatch(case_id)
    if matched is None:
        raise ValueError("패턴 키는 size_{N}_{idx} 형식이어야 합니다.")
    size = int(matched.group(1))
    if size < 1:
        raise ValueError("패턴 크기는 1 이상이어야 합니다.")
    return size


def _normalized_filters(raw_filter_set: object, size: int) -> Dict[str, object]:
    if not isinstance(raw_filter_set, dict):
        raise ValueError("size_{0} 필터는 객체여야 합니다.".format(size))
    normalized = {}  # type: Dict[str, object]
    for raw_label, matrix in raw_filter_set.items():
        label = normalize_label(raw_label)
        if label in normalized:
            raise ValueError("중복 필터 라벨: {0}".format(label))
        normalized[label] = matrix
    missing = [label for label in ("Cross", "X") if label not in normalized]
    if missing:
        raise ValueError("필터 누락: {0}".format(", ".join(missing)))
    return normalized


def analyze_data(data: object) -> Dict[str, Any]:
    """모든 패턴을 독립적으로 분석하여 오류 케이스만 FAIL 처리한다."""
    if not isinstance(data, dict):
        raise ValueError("분석 데이터는 객체여야 합니다.")
    raw_patterns = data.get("patterns")
    if not isinstance(raw_patterns, dict):
        raise ValueError("patterns는 객체여야 합니다.")
    raw_filters = data.get("filters")
    if not isinstance(raw_filters, dict):
        raw_filters = {}

    results = []  # type: List[Dict[str, Any]]
    for case_id, raw_case in raw_patterns.items():
        result = {
            "id": str(case_id),
            "status": "FAIL",
            "reason": "",
            "cross_score": None,
            "x_score": None,
            "predicted": None,
            "expected": None,
        }  # type: Dict[str, Any]
        try:
            size = extract_pattern_size(case_id)
            if not isinstance(raw_case, dict):
                raise ValueError("패턴 항목은 객체여야 합니다.")
            if "input" not in raw_case or "expected" not in raw_case:
                raise ValueError("패턴 항목에는 input과 expected가 필요합니다.")

            filter_key = "size_{0}".format(size)
            if filter_key not in raw_filters:
                raise ValueError("{0} 필터가 없습니다.".format(filter_key))
            filters = _normalized_filters(raw_filters[filter_key], size)
            pattern = validate_matrix(raw_case["input"], size)
            cross_filter = validate_matrix(filters["Cross"], size)
            x_filter = validate_matrix(filters["X"], size)
            expected = normalize_label(raw_case["expected"])

            cross_score = mac_nested(pattern, cross_filter)
            x_score = mac_nested(pattern, x_filter)
            predicted = compare_scores(
                cross_score, x_score, "Cross", "X", EPSILON
            )
            result.update(
                {
                    "cross_score": cross_score,
                    "x_score": x_score,
                    "predicted": predicted,
                    "expected": expected,
                }
            )
            if predicted == expected:
                result["status"] = "PASS"
                result["reason"] = "예상 라벨과 일치"
            elif predicted == "UNDECIDED":
                result["reason"] = "epsilon 정책에 따라 동점(UNDECIDED)"
            else:
                result["reason"] = "판정 {0}, 예상 {1}".format(predicted, expected)
        except (KeyError, TypeError, ValueError) as error:
            result["reason"] = str(error)
        results.append(result)

    passed = sum(1 for result in results if result["status"] == "PASS")
    return {
        "results": results,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
    }


def performance_rows(repetitions: int = 10) -> List[Dict[str, Any]]:
    """3·5·13·25 크기에서 한 번의 N×N MAC 평균 시간을 측정한다."""
    rows = []  # type: List[Dict[str, Any]]
    for size in PERFORMANCE_SIZES:
        cross, _ = generate_patterns(size)
        average_ms, score = benchmark_mac(
            mac_nested, cross, cross, repetitions=repetitions
        )
        rows.append(
            {
                "size": size,
                "average_ms": average_ms,
                "operations": size * size,
                "score": score,
                "repetitions": repetitions,
            }
        )
    return rows

