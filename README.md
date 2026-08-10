# Mini NPU Simulator

[![verify](https://github.com/whiskeyonmytongue/admission-3/actions/workflows/verify.yml/badge.svg)](https://github.com/whiskeyonmytongue/admission-3/actions/workflows/verify.yml)

외부 라이브러리 없이 반복문으로 MAC(Multiply–Accumulate) 연산을 구현해
Cross와 X 패턴을 판별하는 Python 콘솔 프로그램입니다. 3×3 행렬을 직접
입력하거나 `data.json`을 한꺼번에 분석할 수 있습니다. 문제가 있는 케이스는
따로 실패 처리하므로 나머지 분석은 계속됩니다.

## 바로 실행하기

Python 3.8 이상만 준비하면 됩니다. NumPy나 pandas 같은 외부 패키지는
필요하지 않습니다.

```bash
git clone https://github.com/whiskeyonmytongue/admission-3.git
cd admission-3
python3 main.py
```

프로그램을 실행한 뒤 원하는 방식을 고릅니다.

```text
1. 사용자 입력 (3×3)
2. data.json 분석
```

저장된 JSON 6개 케이스는 아래 명령으로 바로 분석합니다.

```bash
python3 main.py --json data.json
```

전체 검증에는 최소 지원 버전인 Python 3.8을 사용합니다.

```bash
make verify PYTHON=python3.8
```

## 구현 결과

| 항목 | 결과 | 확인 방법 |
|---|---:|---|
| 수동 3×3 판정 | PASS | `python3 main.py` |
| 공식 JSON 판정 | 3 PASS·3 예상 FAIL | `python3 main.py --json data.json` |
| 3·5·13·25 성능 측정 | 각 10회 평균 | JSON 실행 결과의 성능 표 |
| 1D 메모리 접근 비교 | 완료 | `make bonus` |
| 홀수 N 패턴 생성 | 완료 | `make bonus` |
| 자동 테스트 | 75개 PASS | `make verify PYTHON=python3.8` |
| Python 3.8·3.14 실행 | 각각 75개 PASS | 공식 Python 컨테이너 |
| Python 스타일 | PASS | `make style` |

## 데이터 구성

[data.json](data.json)은 과제에서 제공한 `version: 1.0`, `type: json` 데이터입니다.
5×5·13×13·25×25 필터와 크기별 패턴 2개씩, 모두 6개 케이스가 들어 있습니다.
`scripts/check_data.py`는 필터·패턴 키, 예상 판정 결과와 내용 해시를 함께 검사해
파일이 의도치 않게 바뀌는 것을 막습니다.

## 동작 원리

MAC은 같은 위치에 놓인 두 값을 곱한 뒤 결과를 모두 더해 하나의 점수로 만드는
연산입니다. N×N 입력의 모든 좌표를 한 번씩 방문하므로 곱셈은 정확히 N²번
일어납니다. [npu.py](npu.py)의 `mac_nested()`가 두 겹의 `for` 문으로 이
과정을 구현합니다.

```text
패턴 키에서 N 추출
  → size_N 필터 선택
  → N×N 행렬 검증
  → Cross/X 라벨 정규화
  → 두 필터의 MAC 점수 계산
  → epsilon 기준 비교
  → PASS/FAIL 집계
```

JSON 데이터는 아래 순서로 분석합니다.

1. `size_{N}_{idx}` 형식의 패턴 키에서 N을 읽습니다.
2. 같은 크기의 `filters.size_N`을 찾습니다.
3. 필터와 패턴이 N×N 정사각형이며 유한한 숫자로 구성됐는지 확인합니다.
4. 필터 키 `cross`, `x`와 예상값 `+`, `x`를 `Cross`, `X`로 정규화합니다.
5. 패턴과 두 필터의 MAC 점수를 각각 구합니다.
6. 점수 차이가 `1e-9`보다 작으면 `UNDECIDED`로 판정합니다.
7. 판정과 예상 라벨을 비교해 PASS/FAIL을 집계합니다.

동점 경계는 **`abs(Cross-X) < 1e-9`**입니다. 차이가 정확히 `1e-9`이면
동점으로 보지 않습니다. NaN, 무한대, 계산 중 overflow, `bool`, 찌그러진
행렬과 알 수 없는 라벨은 오류로 처리합니다. 빈 `patterns` 역시 성공으로
넘기지 않습니다.

## 실제 실행 결과

### 수동 3×3 판정

Cross 모양을 필터 A, X 모양을 필터 B로 입력한 뒤 X 패턴을 판정했습니다.
B 점수가 5로 A 점수 1보다 높아 `B`로 판정됩니다.

![3×3 필터와 패턴을 직접 입력한 터미널 실행 화면](docs/evidence/images/manual-mode-terminal.png)

### 공식 JSON 일괄 분석

아래 화면은 `python3 main.py --json data.json`을 실제로 실행한 결과입니다.
6개 케이스의 판정, N² 연산 횟수, 2D/1D 보너스 비교와 최종 집계를 한 번에
확인할 수 있습니다.

![공식 data.json 6개 케이스를 분석한 터미널 실행 화면](docs/evidence/images/json-analysis-terminal.png)

공식 데이터 6개를 실행한 결과입니다.

```text
총 테스트: 6개
통과: 3개
실패: 3개

실패 케이스:
- size_5_1: epsilon 정책에 따라 동점(UNDECIDED)
- size_13_2: epsilon 정책에 따라 동점(UNDECIDED)
- size_25_1: epsilon 정책에 따라 동점(UNDECIDED)
```

세 케이스는 분석 오류가 아닙니다. Cross와 X 점수가 정확히 같아 동점 정책이
적용됐고, 기대 라벨은 Cross 또는 X이므로 요구사항에 따라 FAIL로 집계됐습니다.
이 때문에 JSON 실행 명령은 종료 코드 `1`을 반환합니다. 공식 데이터의 예상
결과가 맞는지는 `make verify PYTHON=python3.8`로 검사합니다.

같은 실행에서 MAC 함수를 호출하는 구간만 10회 재고 평균을 냈습니다. 파일을
읽거나 화면에 출력하는 시간은 제외했습니다.

| 크기 | 평균 시간(ms) | 연산 횟수(N²) |
|---:|---:|---:|
| 3×3 | 0.004488 | 9 |
| 5×5 | 0.010208 | 25 |
| 13×13 | 0.059192 | 169 |
| 25×25 | 0.211747 | 625 |

측정값은 2026-08-09 Python 3.8 컨테이너에서 얻었습니다. 실행 시간은 CPU
상태에 따라 달라집니다.

## 결과 리포트

### 판정 결과

1. 필터 키 `cross`와 예상값 `+`는 모두 표준 라벨 `Cross`로 바꿨습니다.
2. 필터 키와 예상값의 `x`도 같은 표준 라벨 `X`로 정규화했습니다.
3. `size_5_1`의 Cross와 X 점수는 모두 `0.9`여서 `UNDECIDED`가 됐습니다.
4. `size_13_2`도 두 점수가 `7.5`로 같아 예상값 `Cross`와 달랐습니다.
5. `size_25_1`은 두 점수가 `4.9`로 같아 예상값 `X` 대신 동점으로 판정됐습니다.
6. 나머지 세 케이스의 점수 차이는 각각 `8.8`, `14.4`, `52.8`이어서 예상
   라벨과 같은 결과가 나왔습니다.

### 비교 정책과 오류 진단

7. 두 점수의 차이가 `1e-9`보다 작을 때만 `UNDECIDED`로 판정합니다.
8. 공식 데이터의 세 FAIL은 이 정책을 정확히 적용한 예상 결과이며 프로그램
   오류가 아닙니다.
9. 차이가 epsilon과 정확히 같으면 동점이 아닌 것으로 처리하고, 이 경계도
   테스트로 고정했습니다.
10. 잘못된 크기나 라벨은 해당 케이스만 FAIL로 기록해 다음 분석을 이어갑니다.
11. FAIL 메시지는 데이터·스키마 오류와 수치 비교, 판정 불일치를 구분합니다.

### 시간 복잡도와 보너스 분석

12. N×N MAC은 모든 좌표를 한 번씩 방문합니다. 곱셈 횟수도 9, 25, 169,
   625처럼 N²으로 늘어납니다.
13. 실제 측정에서도 25×25가 3×3보다 오래 걸렸습니다. 입력이 커지면서 늘어난
    반복 횟수가 실행 시간에 반영된 결과입니다.
14. 마이크로초 단위의 짧은 실행은 운영체제 스케줄링과 Python 인터프리터
    오버헤드에 영향을 받습니다. 그래서 측정값이 N² 비율과 정확히 맞지는
    않습니다.
15. 시간 복잡도는 한 번 측정한 시간의 비율보다 코드의 이중 반복문과 정확한
    N² 연산 횟수에서 더 분명하게 드러납니다.
16. 1D 보너스는 평탄화 작업을 측정 전에 한 번만 마쳤습니다. 그 뒤 같은 입력과
    반복 횟수로 연속 메모리 접근 구간을 비교했습니다.
17. 이번 실행에서는 1D 접근이 대체로 빨랐지만 25×25도 작은 입력입니다. 한 번의
    측정만으로 이 방식이 항상 빠르다고 단정하지 않았습니다.

## 보너스 실행

아래 명령은 5×5 Cross/X 패턴을 만든 뒤 3·5·13·25 크기의 2D/1D MAC 성능을
같은 반복 횟수로 비교합니다.

```bash
make bonus
```

크기를 직접 지정할 때는 `python3 main.py --generate 5`처럼 실행합니다.
중앙선이 하나로 정해지지 않는 짝수 N은 오류로 처리합니다. 임의의 크기 상한은
없지만 메모리 사용량과 출력량이 N²으로 늘어나므로 실행 환경에 맞는 값을
입력해야 합니다.

## 오류 처리

| 상황 | 처리 방식 |
|---|---|
| 메뉴에서 1·2 외 입력 | 안내 후 메뉴 재입력 |
| 수동 입력의 열 수·숫자 오류 | 해당 행 재입력 |
| EOF 또는 Ctrl+C | traceback 없이 종료 코드 0 |
| JSON 문법·최상위 스키마 오류 | 원인을 출력하고 종료 코드 1 |
| 패턴 케이스 안의 중복 JSON 키 | 해당 케이스만 FAIL, 다음 케이스 계속 실행 |
| 전역 객체의 중복 JSON 키 | 값을 임의로 고르지 않고 종료 코드 1 |
| JSON 키·경로의 위험 문자 | 제어 문자·Unicode surrogate를 출력 전에 거부 |
| `filters`가 객체가 아님 | `filters는 객체여야 합니다`로 원인 명시 |
| 빈 `patterns` | 처리할 케이스가 없음을 알리고 종료 코드 1 |
| JSON `NaN`·`Infinity`·float overflow | 오류 또는 해당 케이스 FAIL |
| 패턴 키·라벨·행렬 오류 | 해당 케이스만 FAIL, 다음 케이스 계속 실행 |
| 점수 차이 `< 1e-9` | `UNDECIDED`로 판정 |
| 짝수 패턴 생성 요청 | 홀수 크기 안내 후 종료 코드 1 |

의도적으로 손상한 입력까지 검사한 테스트 목록은 `make test`로 확인합니다.

## 자동 검증

```bash
make verify PYTHON=python3.8
```

Python 3.8 확인부터 전체 Python 파일의 구문과 스타일 검사, unittest 75개,
공식 데이터의 3 PASS·3 예상 동점 FAIL, EOF 안전 종료까지 차례로 실행됩니다.
스타일 검사에는 표준 라이브러리만 사용하며 UTF-8·LF·공백·줄 길이·공개 API
docstring·함수 길이와 Python 3.8 문법을 검사합니다.

공식 `python:3.8-slim`과 `python:3.14-slim`에서 같은 75개 테스트를 모두
통과했습니다. GitHub Actions는 Python 3.8 최소 버전과 Python 3.14 호환성을
나눠 검사합니다. 여기에 쓰는 공식 Action은 검토를 마친 커밋 SHA로
고정했습니다.

원격 저장소 상태까지 검사할 때는 아래 명령을 사용합니다.

```bash
make verify-remote PYTHON=python3.8
```

이 명령은 저장소 URL과 PUBLIC 공개 범위, 기본 브랜치 `main`, 로컬·원격 HEAD
일치를 검사합니다.

## 파일 구성

```text
.
├── main.py                         # 메뉴, 출력, 안전 종료
├── npu.py                          # 행렬 검증, MAC, epsilon, 패턴 생성기
├── simulator.py                    # JSON 케이스 격리와 성능 측정
├── data.json                       # 과제 공식 필터와 패턴 6개
├── tests/                          # 경계·오류·CLI 테스트
├── scripts/check_data.py           # 공식 JSON 구조·해시·예상 결과 검증
├── scripts/check_style.py          # 스타일·docstring·Python 3.8 검사
├── scripts/check_syntax.py         # 전체 Python 파일 구문 검사
├── scripts/verify_remote.py        # PUBLIC/main/HEAD 검증
├── docs/evidence/images/           # 실제 터미널 실행 화면
├── .github/workflows/verify.yml    # Python 3.8·3.14 CI
└── Makefile                        # 로컬·원격 검증 진입점
```
