"""JSON 일괄 분석과 성능 측정을 담당한다."""

import json
import math
import re
import sys
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from npu import (
    EPSILON,
    Matrix,
    benchmark_mac,
    compare_representations,
    compare_scores,
    generate_patterns,
    mac_nested,
    normalize_label,
    validate_matrix,
)


PATTERN_KEY = re.compile(r"^size_(\d+)_(.+)$")
FILTER_KEY = re.compile(r"^size_(\d+)$")
PERFORMANCE_SIZES = (3, 5, 13, 25)
MAX_PARSED_INTEGER_DIGITS = 640


_FLOAT_OVERFLOW_SENTINEL = 10 ** 400


def reject_control_characters(label: str, value: str) -> None:
    """터미널 제어 문자와 UTF-8로 출력할 수 없는 surrogate를 거부한다."""
    unsafe_categories = {"Cc", "Cf", "Cs"}
    if any(
        unicodedata.category(character) in unsafe_categories
        for character in value
    ):
        raise ValueError(
            "{0}에 제어 문자 또는 잘못된 Unicode를 사용할 수 없습니다.".format(
                label
            )
        )


class _InvalidJsonObject:
    def __init__(self, reason: str) -> None:
        """객체 단위 JSON 오류를 케이스 분석 단계까지 보존한다."""
        self.reason = reason


def _unique_json_object(
    pairs: List[Tuple[str, Any]],
) -> object:
    result = {}  # type: Dict[str, Any]
    for key, value in pairs:
        try:
            reject_control_characters("JSON 객체 키", key)
        except ValueError as error:
            return _InvalidJsonObject(str(error))
        if key in result:
            return _InvalidJsonObject("중복 JSON 키: {0!r}".format(key))
        result[key] = value
    return result


class _OutOfRangeJsonNumber:
    def __init__(self, negative: bool) -> None:
        """부호만 보존하는 과도하게 큰 JSON 정수 표식을 만든다."""
        self.negative = negative


def _parse_json_integer(raw_value: str) -> object:
    digits = raw_value[1:] if raw_value.startswith("-") else raw_value
    if len(digits) > MAX_PARSED_INTEGER_DIGITS:
        return _OutOfRangeJsonNumber(raw_value.startswith("-"))
    return int(raw_value)


def _parse_json_float(raw_value: str) -> object:
    value = float(raw_value)
    if not math.isfinite(value):
        return _OutOfRangeJsonNumber(raw_value.startswith("-"))
    if value == 0.0:
        try:
            is_nonzero = Decimal(raw_value) != 0
        except InvalidOperation:
            is_nonzero = True
        if is_nonzero:
            return _OutOfRangeJsonNumber(raw_value.startswith("-"))
    return value


def _reject_json_constant(raw_value: str) -> object:
    raise ValueError("JSON 표준에 없는 숫자 상수입니다: {0}".format(raw_value))


def _normalize_out_of_range_matrix(value: object) -> object:
    if isinstance(value, _OutOfRangeJsonNumber):
        if value.negative:
            return -_FLOAT_OVERFLOW_SENTINEL
        return _FLOAT_OVERFLOW_SENTINEL
    if isinstance(value, list):
        return [_normalize_out_of_range_matrix(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _normalize_out_of_range_matrix(item)
            for key, item in value.items()
        }
    return value


def _normalize_filter_matrices(raw_filters: object) -> None:
    if not isinstance(raw_filters, dict):
        return
    for size_key, raw_filter_set in raw_filters.items():
        if (
            not isinstance(size_key, str)
            or FILTER_KEY.fullmatch(size_key) is None
        ):
            continue
        if not isinstance(raw_filter_set, dict):
            continue
        for raw_label, matrix in raw_filter_set.items():
            try:
                normalize_label(raw_label)
            except ValueError:
                continue
            raw_filter_set[raw_label] = _normalize_out_of_range_matrix(matrix)


def _normalize_loaded_data(data: Dict[str, Any]) -> Dict[str, Any]:
    _normalize_filter_matrices(data.get("filters"))
    global_data = {
        key: value
        for key, value in data.items()
        if key != "patterns"
    }
    invalid_reason = _invalid_json_reason(global_data)
    if invalid_reason is not None:
        raise ValueError(invalid_reason)
    if _contains_out_of_range_number(global_data):
        raise ValueError(
            "전역 JSON 숫자가 허용 범위를 벗어났습니다."
        )
    return data


def _walk_json_values(value: object) -> Iterator[object]:
    """깊은 JSON 구조를 재귀 없이 순회하고 순환 참조를 건너뛴다."""
    pending = [value]
    visited = set()
    while pending:
        current = pending.pop()
        yield current
        if not isinstance(current, (list, dict)):
            continue
        identity = id(current)
        if identity in visited:
            continue
        visited.add(identity)
        if isinstance(current, list):
            pending.extend(current)
        else:
            pending.extend(current.values())


def _invalid_json_reason(value: object) -> Optional[str]:
    """JSON 구조 안의 첫 번째 객체 오류 사유를 반환한다."""
    for current in _walk_json_values(value):
        if isinstance(current, _InvalidJsonObject):
            return current.reason
    return None


def _contains_out_of_range_number(value: object) -> bool:
    """JSON 구조 안에 범위를 벗어난 숫자 표식이 있는지 확인한다."""
    for current in _walk_json_values(value):
        if isinstance(current, _OutOfRangeJsonNumber):
            return True
    return False


def load_json_file(path: Path) -> Dict[str, Any]:
    """UTF-8 JSON 파일을 읽고 최상위 객체를 확인한다."""
    try:
        with path.open("r", encoding="utf-8") as source:
            data = json.load(
                source,
                parse_int=_parse_json_integer,
                parse_float=_parse_json_float,
                parse_constant=_reject_json_constant,
                object_pairs_hook=_unique_json_object,
            )
    except (OSError, ValueError, RecursionError) as error:
        raise ValueError("JSON 파일을 읽을 수 없습니다: {0}".format(error))
    if isinstance(data, _InvalidJsonObject):
        raise ValueError("JSON 파일을 읽을 수 없습니다: {0}".format(data.reason))
    if not isinstance(data, dict):
        raise ValueError("JSON 최상위 값은 객체여야 합니다.")
    try:
        return _normalize_loaded_data(data)
    except RecursionError as error:
        raise ValueError("JSON 구조가 지나치게 깊습니다.") from error


def extract_pattern_size(case_id: object) -> int:
    """size_{N}_{idx} 키에서 양의 크기 N을 추출한다."""
    if not isinstance(case_id, str):
        raise ValueError("패턴 키는 문자열이어야 합니다.")
    matched = PATTERN_KEY.fullmatch(case_id)
    if matched is None:
        raise ValueError("패턴 키는 size_{N}_{idx} 형식이어야 합니다.")
    size_text = matched.group(1).lstrip("0") or "0"
    platform_limit = str(sys.maxsize)
    if len(size_text) > len(platform_limit) or (
        len(size_text) == len(platform_limit)
        and size_text > platform_limit
    ):
        raise ValueError("패턴 크기가 실행 환경의 범위를 벗어났습니다.")
    size = int(size_text)
    if size < 1:
        raise ValueError("패턴 크기는 1 이상이어야 합니다.")
    return size


def _normalized_filters(
    raw_filter_set: object,
    size: int,
) -> Dict[str, object]:
    invalid_reason = _invalid_json_reason(raw_filter_set)
    if invalid_reason is not None:
        raise ValueError(invalid_reason)
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


def _empty_result(case_id: object) -> Dict[str, Any]:
    return {
        "id": str(case_id),
        "status": "FAIL",
        "reason": "",
        "cross_score": None,
        "x_score": None,
        "predicted": None,
        "expected": None,
    }


def _case_matrices(
    case_id: object,
    raw_case: object,
    raw_filters: Dict[str, object],
) -> Tuple[Matrix, Matrix, Matrix, str]:
    size = extract_pattern_size(case_id)
    invalid_reason = _invalid_json_reason(raw_case)
    if invalid_reason is not None:
        raise ValueError(invalid_reason)
    if not isinstance(raw_case, dict):
        raise ValueError("패턴 항목은 객체여야 합니다.")
    if _contains_out_of_range_number(raw_case):
        raise ValueError("패턴 케이스의 JSON 숫자가 허용 범위를 벗어났습니다.")
    if "input" not in raw_case or "expected" not in raw_case:
        raise ValueError("패턴 항목에는 input과 expected가 필요합니다.")
    filter_key = "size_{0}".format(size)
    if filter_key not in raw_filters:
        raise ValueError("{0} 필터가 없습니다.".format(filter_key))
    filters = _normalized_filters(raw_filters[filter_key], size)
    return (
        validate_matrix(raw_case["input"], size),
        validate_matrix(filters["Cross"], size),
        validate_matrix(filters["X"], size),
        normalize_label(raw_case["expected"]),
    )


def _analyze_case(
    case_id: object,
    raw_case: object,
    raw_filters: Dict[str, object],
) -> Dict[str, Any]:
    result = _empty_result(case_id)
    try:
        pattern, cross_filter, x_filter, expected = _case_matrices(
            case_id,
            raw_case,
            raw_filters,
        )
        cross_score = mac_nested(pattern, cross_filter)
        x_score = mac_nested(pattern, x_filter)
        predicted = compare_scores(
            cross_score,
            x_score,
            "Cross",
            "X",
            EPSILON,
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
            result.update(status="PASS", reason="예상 라벨과 일치")
        elif predicted == "UNDECIDED":
            result["reason"] = "epsilon 정책에 따라 동점(UNDECIDED)"
        else:
            result["reason"] = "판정 {0}, 예상 {1}".format(
                predicted,
                expected,
            )
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        RecursionError,
    ) as error:
        result["reason"] = str(error)
    return result


def analyze_data(data: object) -> Dict[str, Any]:
    """모든 패턴을 독립적으로 분석하여 오류 케이스만 FAIL 처리한다."""
    if not isinstance(data, dict):
        raise ValueError("분석 데이터는 객체여야 합니다.")
    raw_patterns = data.get("patterns")
    if isinstance(raw_patterns, _InvalidJsonObject):
        raise ValueError(raw_patterns.reason)
    if not isinstance(raw_patterns, dict):
        raise ValueError("patterns는 객체여야 합니다.")
    raw_filters = data.get("filters")
    if not isinstance(raw_filters, dict):
        raise ValueError("filters는 객체여야 합니다.")
    if not raw_patterns:
        raise ValueError("patterns는 비어 있을 수 없습니다.")

    results = [
        _analyze_case(case_id, raw_case, raw_filters)
        for case_id, raw_case in raw_patterns.items()
    ]

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


def bonus_comparison_rows(repetitions: int = 10) -> List[Dict[str, Any]]:
    """생성 패턴을 같은 입력·반복 수로 2D/1D 표현에서 비교한다."""
    rows = []  # type: List[Dict[str, Any]]
    for size in PERFORMANCE_SIZES:
        cross, _ = generate_patterns(size)
        comparison = compare_representations(cross, cross, repetitions)
        comparison["size"] = size
        rows.append(comparison)
    return rows
