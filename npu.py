"""Mini NPU Simulator의 핵심 MAC 연산과 판정 규칙."""

import math
import time
from typing import Callable, Dict, List, Tuple


EPSILON = 1e-9
Matrix = List[List[float]]


def validate_matrix(matrix: object, expected_size: int = 0) -> Matrix:
    """유한한 숫자로 구성된 정사각 행렬을 검증하고 float 행렬로 반환한다."""
    if not isinstance(matrix, list) or not matrix:
        raise ValueError("행렬은 비어 있지 않은 2차원 배열이어야 합니다.")

    size = len(matrix)
    if expected_size and size != expected_size:
        raise ValueError(
            "행렬 크기 불일치: {0}x{0}이 필요하지만 {1}개 행입니다.".format(
                expected_size, size
            )
        )

    checked = []  # type: Matrix
    for row_index, row in enumerate(matrix, start=1):
        if not isinstance(row, list) or len(row) != size:
            raise ValueError(
                "행렬은 정사각형이어야 합니다: {0}번째 행의 열 수가 {1}이 아닙니다.".format(
                    row_index, size
                )
            )
        checked_row = []  # type: List[float]
        for value in row:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("행렬 원소는 숫자여야 합니다(bool 제외).")
            try:
                number = float(value)
            except OverflowError as error:
                raise ValueError("행렬 원소가 float 범위를 벗어났습니다.") from error
            if not math.isfinite(number):
                raise ValueError("행렬 원소는 유한한 숫자여야 합니다.")
            checked_row.append(number)
        checked.append(checked_row)
    return checked


def mac_nested(pattern: object, filter_matrix: object) -> float:
    """중첩 반복문으로 위치별 곱을 누적한다."""
    checked_pattern = validate_matrix(pattern)
    checked_filter = validate_matrix(filter_matrix, len(checked_pattern))
    return _mac_nested_values(checked_pattern, checked_filter)


def _mac_nested_values(pattern: Matrix, filter_matrix: Matrix) -> float:
    score = 0.0
    for row_index in range(len(pattern)):
        for column_index in range(len(pattern)):
            score += (
                pattern[row_index][column_index]
                * filter_matrix[row_index][column_index]
            )
    return _finite_mac_score(score)


def flatten_matrix(matrix: object) -> List[float]:
    """검증된 2차원 행렬을 행 우선 1차원 배열로 변환한다."""
    return _flatten_values(validate_matrix(matrix))


def _flatten_values(matrix: Matrix) -> List[float]:
    return [value for row in matrix for value in row]


def mac_flat(pattern: object, filter_matrix: object) -> float:
    """1차원 배열을 순차 접근해 동일한 MAC 점수를 계산한다."""
    checked_pattern = validate_matrix(pattern)
    checked_filter = validate_matrix(filter_matrix, len(checked_pattern))
    flat_pattern = _flatten_values(checked_pattern)
    flat_filter = _flatten_values(checked_filter)
    return _mac_flat_values(flat_pattern, flat_filter)


def _mac_flat_values(
    pattern: List[float],
    filter_matrix: List[float],
) -> float:
    score = 0.0
    for index in range(len(pattern)):
        score += pattern[index] * filter_matrix[index]
    return _finite_mac_score(score)


def _finite_mac_score(score: float) -> float:
    if not math.isfinite(score):
        raise ValueError("MAC 연산 결과가 float 범위를 벗어났습니다.")
    return score


def compare_representations(
    pattern: object, filter_matrix: object, repetitions: int = 10
) -> Dict[str, float]:
    """검증·평탄화 시간을 제외하고 2D/1D MAC의 동일 반복 구간을 비교한다."""
    _validate_repetitions(repetitions)
    checked_pattern = validate_matrix(pattern)
    checked_filter = validate_matrix(filter_matrix, len(checked_pattern))
    flat_pattern = _flatten_values(checked_pattern)
    flat_filter = _flatten_values(checked_filter)

    nested_score = 0.0
    nested_started = time.perf_counter_ns()
    for _ in range(repetitions):
        nested_score = _mac_nested_values(checked_pattern, checked_filter)
    nested_ns = time.perf_counter_ns() - nested_started

    flat_score = 0.0
    flat_started = time.perf_counter_ns()
    for _ in range(repetitions):
        flat_score = _mac_flat_values(flat_pattern, flat_filter)
    flat_ns = time.perf_counter_ns() - flat_started

    if nested_score != flat_score:
        raise RuntimeError("2D와 1D MAC 점수가 일치하지 않습니다.")
    nested_ms = nested_ns / repetitions / 1_000_000.0
    flat_ms = flat_ns / repetitions / 1_000_000.0
    return {
        "nested_ms": nested_ms,
        "flat_ms": flat_ms,
        "score": nested_score,
        "repetitions": float(repetitions),
    }


def compare_scores(
    first_score: float,
    second_score: float,
    first_label: str,
    second_label: str,
    epsilon: float = EPSILON,
) -> str:
    """차이가 epsilon보다 작을 때만 동점으로 판정한다."""
    if not all(math.isfinite(value) for value in (first_score, second_score)):
        raise ValueError("점수는 유한한 숫자여야 합니다.")
    if epsilon <= 0.0 or not math.isfinite(epsilon):
        raise ValueError("epsilon은 0보다 큰 유한한 숫자여야 합니다.")
    difference = abs(first_score - second_score)
    if difference < epsilon:
        return "UNDECIDED"
    if first_score > second_score:
        return first_label
    return second_label


def normalize_label(label: object) -> str:
    """JSON의 필터 키와 expected 값을 표준 라벨로 바꾼다."""
    if not isinstance(label, str):
        raise ValueError("라벨은 문자열이어야 합니다.")
    normalized = label.strip().lower()
    if normalized in ("+", "cross"):
        return "Cross"
    if normalized == "x":
        return "X"
    raise ValueError("지원하지 않는 라벨: {0!r}".format(label))


def generate_patterns(size: int) -> Tuple[Matrix, Matrix]:
    """홀수 N에 대해 중앙 행·열 Cross와 두 대각선 X를 생성한다."""
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ValueError("크기는 0보다 큰 홀수 정수여야 합니다.")
    if size % 2 == 0:
        raise ValueError("중앙선이 하나인 패턴을 위해 홀수 크기만 지원합니다.")

    center = size // 2
    cross = []  # type: Matrix
    x_pattern = []  # type: Matrix
    for row in range(size):
        cross_row = []  # type: List[float]
        x_row = []  # type: List[float]
        for column in range(size):
            cross_row.append(1.0 if row == center or column == center else 0.0)
            is_diagonal = row == column or row + column == size - 1
            x_row.append(1.0 if is_diagonal else 0.0)
        cross.append(cross_row)
        x_pattern.append(x_row)
    return cross, x_pattern


def benchmark_mac(
    operation: Callable[[object, object], float],
    pattern: object,
    filter_matrix: object,
    repetitions: int = 10,
) -> Tuple[float, float]:
    """I/O를 제외하고 MAC 함수 호출 구간의 평균 ms와 마지막 점수를 반환한다."""
    _validate_repetitions(repetitions)
    score = 0.0
    started_at = time.perf_counter_ns()
    for _ in range(repetitions):
        score = operation(pattern, filter_matrix)
    _finite_mac_score(score)
    elapsed_ns = time.perf_counter_ns() - started_at
    average_ms = elapsed_ns / repetitions / 1_000_000.0
    return average_ms, score


def _validate_repetitions(repetitions: int) -> None:
    if (
        isinstance(repetitions, bool)
        or not isinstance(repetitions, int)
        or repetitions < 1
    ):
        raise ValueError("반복 횟수는 1 이상의 정수여야 합니다.")
