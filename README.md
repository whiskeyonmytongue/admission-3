# Mini NPU Simulator

[![verify](https://github.com/whiskeyonmytongue/admission-3/actions/workflows/verify.yml/badge.svg)](https://github.com/whiskeyonmytongue/admission-3/actions/workflows/verify.yml)

외부 라이브러리 없이 반복문으로 MAC(Multiply–Accumulate) 연산을 구현하고, Cross와 X 패턴을 판별하는 Python 콘솔 애플리케이션입니다. 3×3 직접 입력과 `data.json` 일괄 분석을 지원하며, 잘못된 JSON 케이스는 다른 케이스의 실행을 막지 않습니다.

## 구현 결과

| 항목 | 결과 | 확인 방법 |
|---|---:|---|
| 수동 3×3 판정 | PASS | `python3 main.py` |
| 합성 JSON 판정 | 6/6 PASS | `python3 main.py --json data.json` |
| 3·5·13·25 성능 측정 | 각 10회 평균 | JSON 실행 결과의 성능 표 |
| 1D 메모리 접근 비교 | 완료 | `make bonus` |
| 홀수 N 패턴 생성 | 완료 | `python3 main.py --generate 5` |
| 자동 테스트 | 68개 PASS | `make verify PYTHON=python3.8` |
| Python 3.8·3.14 실행 | 각각 68개 PASS | 공식 Python 컨테이너 |
| Python 스타일 | PASS | `make style` |

주요 실행 결과와 검증 환경은 [수동 입력 로그](docs/evidence/logs/manual-mode.txt), [JSON 분석 로그](docs/evidence/logs/json-analysis.txt), [자동 검증 로그](docs/evidence/logs/verification.txt)에 보존했습니다.

## 바로 실행하기

Python 3.8 이상만 필요하며 NumPy, pandas 같은 외부 패키지는 사용하지 않습니다.
제출 검증은 정확한 최소 버전을 증명하기 위해 Python 3.8에서 실행합니다.

```bash
git clone https://github.com/whiskeyonmytongue/admission-3.git
cd admission-3
make verify PYTHON=python3.8
```

직접 3×3 필터와 패턴을 입력하려면 다음 명령을 실행한 뒤 `1`을 선택합니다. 각 행에는 숫자 3개를 공백으로 구분해 입력합니다. 열 수가 다르거나 숫자가 아니면 그 행부터 다시 입력받습니다.

```bash
python3 main.py
```

저장된 JSON 6개 케이스를 한 번에 확인하려면 다음 명령을 실행합니다.

```bash
python3 main.py --json data.json
```

보너스 패턴 생성기와 2D/1D 접근 비교는 다음처럼 확인합니다. 짝수 N은 중앙선이 하나로 정해지지 않으므로 오류로 처리합니다. 생성 크기에는 임의의 상한을 두지 않았지만, N×N 행렬의 메모리와 출력량이 N²으로 증가하므로 실행 환경에 맞는 크기를 입력해야 합니다.

```bash
python3 main.py --generate 5
make bonus
```

원격 저장소가 연결된 뒤 공개 여부, 기본 브랜치, 로컬·원격 HEAD까지 확인하는 명령은 다음과 같습니다.

```bash
make verify-remote PYTHON=python3.8
```

## 데이터 출처

과제에 언급된 공식 `data.json` 원본은 현재 작업 환경에 첨부되지 않았습니다. 따라서 이 저장소의 [data.json](data.json)은 **공식 데이터가 아니라 합성 검증 데이터**입니다. 홀수 N의 중앙 행·열을 `Cross`, 두 대각선을 `X`로 만드는 명시적인 규칙으로 5×5·13×13·25×25에서 각 2개, 총 6개 케이스를 생성했습니다. 파일의 `_meta`에도 출처, 생성 규칙, 용도를 기록해 공식 데이터와 혼동하지 않도록 했습니다.

## 동작 원리

MAC은 같은 위치의 두 값을 곱한 뒤 하나의 점수로 누적하는 연산입니다. N×N 입력에서는 정확히 N²번 곱합니다. [npu.py](npu.py)의 `mac_nested()`가 두 겹의 `for` 문으로 이 과정을 수행합니다.

JSON 분석 흐름은 다음과 같습니다.

1. `size_{N}_{idx}` 형식의 패턴 키에서 N을 읽습니다.
2. 같은 크기의 `filters.size_N`을 찾습니다.
3. 모든 행렬이 N×N 정사각형이며 유한한 숫자로 구성됐는지 확인합니다.
4. 필터 키 `cross`, `x`와 예상값 `+`, `x`를 `Cross`, `X`로 정규화합니다.
5. 패턴과 두 필터의 MAC 점수를 각각 구합니다.
6. 점수 차이가 `1e-9`보다 작으면 `UNDECIDED`, 아니면 더 큰 점수의 라벨을 선택합니다.
7. 판정과 예상 라벨을 비교해 PASS/FAIL을 집계합니다.

경계는 의도적으로 **`abs(Cross-X) < 1e-9`**로 구현했습니다. 차이가 정확히 `1e-9`인 경우에는 동점이 아닙니다. NaN, 무한대, 계산 중 발생한 overflow, `bool`, 찌그러진 행렬, 알 수 없는 라벨도 명시적으로 거부합니다. JSON의 빈 `patterns`도 성공으로 집계하지 않습니다.

## 실제 실행 결과

합성 데이터 실행에서는 다음 결과를 얻었습니다.

```text
총 테스트: 6개
통과: 6개
실패: 0개
```

같은 실행에서 측정한 MAC 시간입니다. 시간 측정에는 파일 읽기와 출력이 들어가지 않으며, 각 행렬 크기마다 MAC 함수 호출을 10회 수행한 평균입니다.

| 크기 | 평균 시간(ms) | 연산 횟수(N²) |
|---:|---:|---:|
| 3×3 | 0.002908 | 9 |
| 5×5 | 0.006221 | 25 |
| 13×13 | 0.033821 | 169 |
| 25×25 | 0.115221 | 625 |

측정값은 2026-08-09 로컬 환경의 한 차례 실행 결과이며 CPU 상태에 따라 달라집니다. 정확한 원본 출력은 [JSON 분석 로그](docs/evidence/logs/json-analysis.txt)에서 확인할 수 있습니다.

## 결과 리포트

1. 6개 케이스가 모두 통과한 첫 번째 이유는 필터 키 `cross`와 예상값 `+`를 같은 표준 라벨 `Cross`로 바꿨기 때문입니다.
2. `x`도 입력 위치와 관계없이 `X`로 정규화하므로 문자열 표기 차이가 판정 실패로 이어지지 않습니다.
3. 합성 입력은 필터와 같은 생성 규칙을 사용해 정답 필터의 MAC 점수가 항상 더 큽니다.
4. Cross와 X가 겹치는 중앙 한 칸은 두 점수에 공통으로 들어가지만, 나머지 활성 위치가 충분히 달라 동점이 발생하지 않습니다.
5. epsilon 정책은 부동소수점의 미세한 표현 차이를 실제 패턴 차이로 오판하지 않게 합니다.
6. 반대로 차이가 epsilon과 정확히 같으면 동점이 아니라는 엄격한 경계도 테스트해 비교 정책의 모호함을 없앴습니다.
7. JSON의 한 케이스에 잘못된 크기나 라벨이 있어도 예외를 해당 케이스의 FAIL 사유로 바꾸므로 이후 케이스는 계속 분석됩니다.
8. 따라서 앞으로 FAIL이 생기면 메시지를 기준으로 데이터·스키마, 수치 비교, 실제 판정 불일치 중 어디서 발생했는지 나눠 볼 수 있습니다.
9. N×N MAC은 모든 좌표를 한 번씩 방문하므로 곱셈 횟수는 9, 25, 169, 625처럼 N²으로 증가합니다.
10. 측정에서도 3×3보다 25×25가 오래 걸렸고, 입력이 커질수록 반복 횟수 증가가 실행 시간에 반영됐습니다.
11. 다만 매우 짧은 마이크로초 단위 실행은 운영체제 스케줄링과 Python 인터프리터 오버헤드의 영향을 받아 N² 비율과 정확히 일치하지 않습니다.
12. 그러므로 시간 복잡도의 근거는 한 번의 측정 비율보다 코드의 이중 반복문과 확정적인 N² 연산 횟수에 두는 것이 타당합니다.
13. 1D 보너스는 평탄화 비용을 측정 밖에서 한 번만 지불하고 같은 입력·반복 횟수로 연속 메모리 접근 구간을 비교했습니다.
14. 실제 실행에서는 1D 접근이 대체로 짧았지만, 25×25처럼 작은 입력에서는 차이가 작으므로 단일 측정만으로 일반적인 성능 우위를 단정하지 않습니다.

## 오류 처리 확인

| 상황 | 처리 방식 |
|---|---|
| 메뉴에서 1·2 외 입력 | 안내 후 메뉴 재입력 |
| 수동 입력의 열 수·숫자 오류 | 해당 행 재입력 |
| EOF 또는 Ctrl+C | 직접 호출을 포함해 traceback 없이 종료 코드 0 |
| JSON 문법·최상위 스키마 오류 | 원인을 출력하고 종료 코드 1 |
| `filters`가 객체가 아님 | `filters는 객체여야 합니다`로 원인 명시 |
| 빈 `patterns` | 처리할 케이스가 없음을 알리고 종료 코드 1 |
| JSON `NaN`·`Infinity`·float overflow | 비유한 숫자로 처리하지 않고 오류 또는 해당 케이스 FAIL |
| 패턴 키·라벨·행렬 오류 | 해당 케이스만 FAIL, 다음 케이스 계속 실행 |
| 점수 차이 `< 1e-9` | `UNDECIDED`로 판정 |
| 짝수 패턴 생성 요청 | 홀수 크기 안내 후 종료 코드 1 |

의도적인 손상 케이스까지 포함한 테스트 이름과 결과는 [자동 검증 로그](docs/evidence/logs/verification.txt)에 있습니다.

## 파일 구성

```text
.
├── main.py                         # 메뉴, 출력, 안전 종료
├── npu.py                          # 행렬 검증, MAC, epsilon, 보너스 생성기
├── simulator.py                    # JSON 케이스 격리와 성능 측정
├── data.json                       # 출처가 표시된 합성 6개 케이스
├── tests/                          # 경계·오류·CLI 테스트
├── scripts/check_data.py           # 합성 JSON 6/6 검증
├── scripts/check_style.py          # 과제 스타일·docstring·Python 3.8 검사
├── scripts/check_syntax.py         # 모든 Python 파일 구문 컴파일
├── scripts/verify_remote.py        # 정확한 저장소·PUBLIC·HEAD 검증
├── .github/workflows/verify.yml    # Python 3.8·현재 버전 CI
├── docs/evidence/logs/             # 실제 실행 출력
└── Makefile                        # 로컬·원격 검증 진입점
```

## 테스트 범위

`make verify PYTHON=python3.8`은 정확히 Python 3.8에서 전체 Python 파일의
구문 컴파일, 과제에 적용한 PEP 8·257 핵심 규칙, unittest 68개, 합성 데이터
6/6, EOF 안전 종료를 순서대로 확인합니다. 스타일 검사는 UTF-8·LF·마지막
개행·공백·최상위 정의 사이 두 줄·줄 길이(코드 79자, 주석과 docstring
72자)·공개 API docstring·50줄 초과 함수·Python 3.8 AST 문법과 현재 Python의
컴파일 문맥을 표준 라이브러리만 사용해 검사합니다.

로컬에서는 공식 `python:3.8-slim`과 `python:3.14-slim`에서 같은 68개
테스트를 통과시켰습니다. GitHub Actions도 고정된 commit SHA의 Action을
사용해 Python 3.8 최소 버전 전체 검증과 Python 3.14 호환성 검증을 나눠
실행합니다. 테스트에는 malformed matrix/schema, 빈 데이터, 잘못된 최상위
`filters`, 과도한 정수·float·NaN·무한대, MAC overflow, epsilon 경계, 정적
6개 케이스, 전체 `--json` 성공·실패·누락 경계, 실행 위치와 무관한 기본
데이터 경로, 메뉴·행 재입력, `run_cli()` 직접 호출과 인자 파싱 중
Ctrl+C·EOF가 포함됩니다.
