"""합성 data.json의 전체 케이스가 통과하는지 검증한다."""

from pathlib import Path

from simulator import analyze_data, load_json_file


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data.json"


def main() -> None:
    """정적 데이터의 6개 케이스가 모두 통과하는지 확인한다."""
    report = analyze_data(load_json_file(DATA_PATH))
    summary = (report["total"], report["passed"], report["failed"])
    if summary != (6, 6, 0):
        raise SystemExit("[FAIL] data.json 결과: {0}".format(summary))
    print("[PASS] data.json 6/6")


if __name__ == "__main__":
    main()
