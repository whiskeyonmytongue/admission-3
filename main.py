"""Mini NPU Simulator 콘솔 진입점."""

import argparse
import math
import sys
from pathlib import Path
from typing import Callable, List, Optional, Sequence

from npu import (
    EPSILON,
    benchmark_mac,
    compare_scores,
    generate_patterns,
    mac_nested,
)
from simulator import (
    analyze_data,
    bonus_comparison_rows,
    load_json_file,
    performance_rows,
    reject_control_characters,
)


Output = Callable[[str], None]
Input = Callable[[str], str]
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = PROJECT_ROOT / "data.json"


def read_mode(input_fn: Input, output_fn: Output) -> str:
    """지원하는 모드가 선택될 때까지 다시 묻는다."""
    while True:
        output_fn("\n[모드 선택]")
        output_fn("1. 사용자 입력 (3×3)")
        output_fn("2. data.json 분석")
        choice = input_fn("선택: ").strip()
        if choice in ("1", "2"):
            return choice
        output_fn("입력 오류: 1 또는 2를 입력하세요.")


def _row_input_error(size: int) -> str:
    return (
        "입력 형식 오류: 각 줄에 {0}개의 숫자를 공백으로 구분해 "
        "입력하세요."
    ).format(size)


def read_matrix(
    name: str,
    size: int,
    input_fn: Input,
    output_fn: Output,
) -> List[List[float]]:
    """행 단위 오류를 안내하고 현재 행부터 재입력한다."""
    output_fn("{0} ({1}줄 입력, 공백 구분)".format(name, size))
    matrix = []  # type: List[List[float]]
    while len(matrix) < size:
        row_number = len(matrix) + 1
        raw = input_fn("{0}행: ".format(row_number)).strip().split()
        if len(raw) != size:
            output_fn(_row_input_error(size))
            continue
        try:
            row = [float(value) for value in raw]
        except ValueError:
            output_fn(_row_input_error(size))
            continue
        if not all(math.isfinite(value) for value in row):
            output_fn("입력 형식 오류: 유한한 숫자만 입력하세요.")
            continue
        matrix.append(row)
    output_fn("✓ {0} 저장 완료".format(name))
    return matrix


def print_performance(repetitions: int, output_fn: Output) -> None:
    """필수 크기의 평균 MAC 시간과 연산 횟수를 출력한다."""
    output_fn("\n[성능 분석: 평균/{0}회]".format(repetitions))
    output_fn("크기       평균 시간(ms)    연산 횟수(N²)")
    output_fn("----------------------------------------")
    for row in performance_rows(repetitions):
        output_fn(
            "{0:>2}×{0:<2}     {1:>12.6f}    {2:>8}".format(
                row["size"], row["average_ms"], row["operations"]
            )
        )


def print_bonus_comparison(repetitions: int, output_fn: Output) -> None:
    """동일 입력에서 2D와 1D MAC 시간을 비교해 출력한다."""
    output_fn("\n[보너스: 동일 입력의 2D/1D MAC 비교]")
    output_fn("크기       2D 평균(ms)    1D 평균(ms)    반복")
    output_fn("-----------------------------------------------")
    for row in bonus_comparison_rows(repetitions):
        output_fn(
            "{0:>2}×{0:<2}     {1:>10.6f}    {2:>10.6f}    {3:>4}".format(
                row["size"],
                row["nested_ms"],
                row["flat_ms"],
                int(row["repetitions"]),
            )
        )


def print_generated_patterns(size: int, output_fn: Output) -> None:
    """홀수 크기의 Cross와 X 패턴을 출력한다."""
    cross, x_pattern = generate_patterns(size)
    for label, matrix in (("Cross", cross), ("X", x_pattern)):
        output_fn("\n{0} {1}×{1}".format(label, size))
        for row in matrix:
            output_fn(" ".join(str(int(value)) for value in row))


def run_manual(
    input_fn: Input,
    output_fn: Output,
    repetitions: int = 10,
) -> int:
    """3×3 필터와 패턴을 입력받아 MAC 판정 결과를 출력한다."""
    output_fn("\n[1] 필터 입력")
    filter_a = read_matrix("필터 A", 3, input_fn, output_fn)
    filter_b = read_matrix("필터 B", 3, input_fn, output_fn)
    output_fn("\n[2] 패턴 입력")
    pattern = read_matrix("패턴", 3, input_fn, output_fn)

    score_a = mac_nested(pattern, filter_a)
    score_b = mac_nested(pattern, filter_b)
    average_ms, _ = benchmark_mac(
        mac_nested, pattern, filter_a, repetitions=repetitions
    )
    predicted = compare_scores(score_a, score_b, "A", "B", EPSILON)
    verdict = "판정 불가" if predicted == "UNDECIDED" else predicted

    output_fn("\n[3] MAC 결과")
    output_fn("A 점수: {0:.12g}".format(score_a))
    output_fn("B 점수: {0:.12g}".format(score_b))
    output_fn("연산 시간(평균/{0}회): {1:.6f} ms".format(repetitions, average_ms))
    output_fn("판정: {0}".format(verdict))
    if predicted == "UNDECIDED":
        output_fn("근거: |A-B| < {0}".format(EPSILON))
    return 0


def _filter_sizes(data: object) -> List[str]:
    if not isinstance(data, dict) or not isinstance(data.get("filters"), dict):
        return []
    return sorted(str(key) for key in data["filters"].keys())


def run_json(path: Path, output_fn: Output, repetitions: int = 10) -> int:
    """JSON의 전체 케이스와 성능 분석 결과를 출력한다."""
    reject_control_characters("JSON 경로", str(path))
    data = load_json_file(path)
    output_fn("\n[1] 필터 로드")
    output_fn("파일: {0}".format(path))
    for size_key in _filter_sizes(data):
        output_fn("- {0} 필터 키 발견".format(size_key))

    report = analyze_data(data)
    output_fn("\n[2] 패턴 분석 (표준 라벨 적용)")
    for result in report["results"]:
        output_fn("--- {0} ---".format(result["id"]))
        if result["cross_score"] is not None:
            output_fn("Cross 점수: {0:.12g}".format(result["cross_score"]))
            output_fn("X 점수: {0:.12g}".format(result["x_score"]))
            output_fn(
                "판정: {0} | expected: {1} | {2}".format(
                    result["predicted"], result["expected"], result["status"]
                )
            )
        else:
            output_fn("판정: 분석 불가 | FAIL")
        if result["status"] == "FAIL":
            output_fn("사유: {0}".format(result["reason"]))

    print_performance(repetitions, output_fn)
    print_bonus_comparison(repetitions, output_fn)
    output_fn("\n[결과 요약]")
    output_fn("총 테스트: {0}개".format(report["total"]))
    output_fn("통과: {0}개".format(report["passed"]))
    output_fn("실패: {0}개".format(report["failed"]))
    if report["failed"]:
        output_fn("실패 케이스:")
        for result in report["results"]:
            if result["status"] == "FAIL":
                output_fn("- {0}: {1}".format(result["id"], result["reason"]))
    return 0 if report["failed"] == 0 else 1


def run_cli(
    input_fn: Optional[Input] = None,
    output_fn: Output = print,
) -> int:
    """대화형 실행을 시작하고 입력 중단을 안전 종료로 변환한다."""
    actual_input = input if input_fn is None else input_fn
    try:
        output_fn("=== Mini NPU Simulator ===")
        mode = read_mode(actual_input, output_fn)
        if mode == "1":
            return run_manual(actual_input, output_fn)
        path_text = actual_input("data.json 경로 [data.json]: ").strip()
        path = Path(path_text) if path_text else DEFAULT_DATA_PATH
        return run_json(path, output_fn)
    except (EOFError, KeyboardInterrupt):
        output_fn("\n입력이 종료되어 시뮬레이터를 안전하게 종료합니다.")
        return 0


def build_parser() -> argparse.ArgumentParser:
    """명령행 인자 파서를 구성한다."""
    parser = argparse.ArgumentParser(description="반복문 기반 Mini NPU Simulator")
    parser.add_argument(
        "--json",
        dest="json_path",
        type=Path,
        help="메뉴를 건너뛰고 지정한 JSON 파일을 일괄 분석합니다.",
    )
    parser.add_argument(
        "--generate",
        type=int,
        metavar="N",
        help="홀수 N의 Cross/X 패턴을 생성해 출력합니다.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """명령행 모드를 실행하고 예상 가능한 오류를 종료 코드로 변환한다."""
    try:
        arguments = build_parser().parse_args(argv)
        if arguments.generate is not None:
            print("=== Mini NPU Simulator 패턴 생성기 ===")
            print_generated_patterns(arguments.generate, print)
            print_bonus_comparison(10, print)
            return 0
        if arguments.json_path is not None:
            print("=== Mini NPU Simulator ===")
            return run_json(arguments.json_path, print)
        return run_cli()
    except (EOFError, KeyboardInterrupt):
        print("\n입력이 종료되어 시뮬레이터를 안전하게 종료합니다.")
        return 0
    except ValueError as error:
        print("오류: {0}".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
