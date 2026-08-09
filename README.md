# Mini NPU Simulator

[![verify](https://github.com/whiskeyonmytongue/admission-3/actions/workflows/verify.yml/badge.svg)](https://github.com/whiskeyonmytongue/admission-3/actions/workflows/verify.yml)

외부 라이브러리 없이 반복문으로 MAC(Multiply–Accumulate) 연산을 구현하고,
Cross와 X 패턴을 판별하는 Python 콘솔 프로그램입니다. 3×3 직접 입력과
`data.json` 일괄 분석을 지원하며, 잘못된 케이스 하나가 나머지 분석을 막지
않도록 오류를 케이스별로 격리했습니다.

## 바로 실행하기

Python 3.8 이상만 필요합니다. NumPy와 pandas 같은 외부 패키지는 사용하지
않습니다.

```bash
git clone https://github.com/whiskeyonmytongue/admission-3.git
cd admission-3
python3 main.py
```

메뉴에서 실행 방식을 선택합니다.

```text
1. 사용자 입력 (3×3)
2. data.json 분석
```

저장된 JSON 6개 케이스를 바로 분석하려면 다음 명령을 사용합니다.

```bash
python3 main.py --json data.json
```

전체 검증은 정확한 최소 지원 버전인 Python 3.8에서 실행합니다.

```bash
make verify PYTHON=python3.8
```

## 구현 결과

| 항목 | 결과 | 확인 방법 |
|---|---:|---|
| 수동 3×3 판정 | PASS | `python3 main.py` |
| 합성 JSON 판정 | 6/6 PASS | `python3 main.py --json data.json` |
| 공식 JSON 판정 | 미실행 | 공식 `data.json` 파일 미제공 |
| 3·5·13·25 성능 측정 | 각 10회 평균 | JSON 실행 결과의 성능 표 |
| 1D 메모리 접근 비교 | 완료 | `make bonus` |
| 홀수 N 패턴 생성 | 완료 | `make bonus` |
| 자동 테스트 | 74개 PASS | `make verify PYTHON=python3.8` |
| Python 3.8·3.14 실행 | 각각 74개 PASS | 공식 Python 컨테이너 |
| Python 스타일 | PASS | `make style` |

실제 출력은 다음 로그에서 확인할 수 있습니다.

- [3×3 수동 입력](docs/evidence/logs/manual-mode.txt)
- [JSON 6개 케이스와 성능 분석](docs/evidence/logs/json-analysis.txt)
- [Python 3.8·3.14 자동 검증](docs/evidence/logs/verification.txt)

## 데이터 출처

> [!IMPORTANT]
> 과제에 언급된 공식 `data.json`은 현재 작업 환경에 첨부되지 않았습니다.
> 이 저장소의 [data.json](data.json)은 공식 데이터가 아닌 **합성 검증 데이터**입니다.

합성 데이터는 홀수 N의 중앙 행·열을 `Cross`, 두 대각선을 `X`로 만드는 규칙으로
생성했습니다. 5×5·13×13·25×25에서 각 2개씩, 총 6개 케이스가 들어 있습니다.
파일의 `_meta`에도 출처, 생성 규칙과 용도를 기록해 공식 데이터와 혼동하지
않도록 했습니다.

## 동작 원리

MAC은 같은 위치의 두 값을 곱하고 그 결과를 하나의 점수로 더하는 연산입니다.
N×N 입력은 모든 좌표를 한 번씩 방문하므로 곱셈 횟수는 정확히 N²번입니다.
[npu.py](npu.py)의 `mac_nested()`가 두 겹의 `for` 문으로 이 과정을 수행합니다.

```text
패턴 키에서 N 추출
  → size_N 필터 선택
  → N×N 행렬 검증
  → Cross/X 라벨 정규화
  → 두 필터의 MAC 점수 계산
  → epsilon 기준 비교
  → PASS/FAIL 집계
```

JSON 분석의 세부 순서는 다음과 같습니다.

1. `size_{N}_{idx}` 형식의 패턴 키에서 N을 읽습니다.
2. 같은 크기의 `filters.size_N`을 찾습니다.
3. 필터와 패턴이 N×N 정사각형이며 유한한 숫자로 구성됐는지 확인합니다.
4. 필터 키 `cross`, `x`와 예상값 `+`, `x`를 `Cross`, `X`로 정규화합니다.
5. 패턴과 두 필터의 MAC 점수를 각각 구합니다.
6. 점수 차이가 `1e-9`보다 작으면 `UNDECIDED`로 판정합니다.
7. 판정과 예상 라벨을 비교해 PASS/FAIL을 집계합니다.

동점 경계는 **`abs(Cross-X) < 1e-9`**입니다. 차이가 정확히 `1e-9`이면
동점이 아닙니다. NaN, 무한대, 계산 중 overflow, `bool`, 찌그러진 행렬과
알 수 없는 라벨은 명시적으로 거부합니다. 빈 `patterns`도 성공으로 처리하지
않습니다.

## 실제 실행 결과

합성 데이터 6개를 분석한 결과입니다.

```text
총 테스트: 6개
통과: 6개
실패: 0개
```

같은 실행에서 MAC 함수 호출 구간만 10회 측정해 평균을 구했습니다. 파일 읽기와
화면 출력 시간은 측정에 포함하지 않았습니다.

| 크기 | 평균 시간(ms) | 연산 횟수(N²) |
|---:|---:|---:|
| 3×3 | 0.002400 | 9 |
| 5×5 | 0.005271 | 25 |
| 13×13 | 0.028758 | 169 |
| 25×25 | 0.112104 | 625 |

측정값은 2026-08-09 로컬 환경에서 얻었으며 CPU 상태에 따라 달라질 수 있습니다.
원본 출력은 [JSON 분석 로그](docs/evidence/logs/json-analysis.txt)에 있습니다.

## 결과 리포트

### 판정 정확도

1. 6개 케이스가 모두 통과한 첫 번째 이유는 필터 키 `cross`와 예상값 `+`를
   같은 표준 라벨 `Cross`로 바꿨기 때문입니다.
2. `x`도 입력 위치와 관계없이 `X`로 정규화하므로 문자열 표기 차이가 판정
   실패로 이어지지 않습니다.
3. 합성 입력은 필터와 같은 규칙으로 만들었기 때문에 정답 필터의 MAC 점수가
   항상 더 큽니다.
4. Cross와 X가 겹치는 중앙 한 칸은 두 점수에 공통으로 들어가지만, 나머지
   활성 위치가 충분히 달라 동점이 발생하지 않습니다.

### 비교 정책과 오류 진단

5. epsilon 정책은 부동소수점의 작은 표현 차이를 실제 패턴 차이로 오판하지
   않게 합니다.
6. 차이가 epsilon과 정확히 같으면 동점으로 보지 않는 경계도 테스트해 비교
   정책을 명확히 했습니다.
7. 한 케이스의 크기나 라벨이 잘못돼도 해당 예외만 FAIL 사유로 바꾸고 다음
   케이스를 계속 분석합니다.
8. FAIL 메시지를 보면 데이터·스키마, 수치 비교와 실제 판정 불일치 중 어디에서
   문제가 생겼는지 나눠 볼 수 있습니다.

### 시간 복잡도와 보너스 분석

9. N×N MAC은 모든 좌표를 한 번씩 방문하므로 곱셈 횟수가 9, 25, 169,
   625처럼 N²으로 증가합니다.
10. 실제 측정에서도 3×3보다 25×25가 오래 걸렸습니다. 입력이 커질수록 반복
    횟수 증가가 실행 시간에 반영됩니다.
11. 짧은 마이크로초 단위 실행은 운영체제 스케줄링과 Python 인터프리터
    오버헤드의 영향을 받으므로 측정 시간이 N² 비율과 정확히 일치하지 않습니다.
12. 시간 복잡도의 근거는 한 번의 측정 비율보다 코드의 이중 반복문과 확정적인
    N² 연산 횟수에 두는 것이 타당합니다.
13. 1D 보너스는 평탄화 비용을 측정 밖에서 한 번만 지불하고, 같은 입력과 반복
    횟수로 연속 메모리 접근 구간을 비교했습니다.
14. 실제 실행에서는 1D 접근이 대체로 짧았지만 25×25도 작은 입력입니다.
    단일 측정만으로 일반적인 성능 우위를 단정하지 않았습니다.

## 보너스 실행

다음 명령은 5×5 Cross/X 패턴을 생성하고 3·5·13·25 크기의 2D/1D MAC
성능을 같은 반복 횟수로 비교합니다.

```bash
make bonus
```

크기를 직접 지정하려면 `python3 main.py --generate 5`처럼 실행합니다. 중앙선이
하나로 정해지지 않는 짝수 N은 오류로 처리합니다. 크기에 임의의 상한은 두지
않았지만 메모리와 출력량이 N²으로 증가하므로 실행 환경에 맞는 값을 사용해야
합니다.

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

의도적인 손상 입력을 포함한 테스트 이름은
[자동 검증 로그](docs/evidence/logs/verification.txt)에서 확인할 수 있습니다.

## 자동 검증

```bash
make verify PYTHON=python3.8
```

이 명령은 Python 3.8 확인, 전체 Python 파일의 구문과 스타일 검사, unittest
74개, 합성 데이터 6/6과 EOF 안전 종료를 차례대로 실행합니다. 스타일 검사는
표준 라이브러리만 사용하며 UTF-8·LF·공백·줄 길이·공개 API docstring·함수 길이와
Python 3.8 문법을 확인합니다.

공식 `python:3.8-slim`과 `python:3.14-slim`에서 같은 74개 테스트를
통과했습니다. GitHub Actions도 Python 3.8 최소 버전 검증과 Python 3.14
호환성 검증을 나눠 실행하며, 공식 Action은 검토한 커밋 SHA로 고정했습니다.

원격 저장소까지 확인하려면 다음 명령을 사용합니다.

```bash
make verify-remote PYTHON=python3.8
```

이 명령은 정확한 저장소 URL, PUBLIC 공개 범위, 기본 브랜치 `main`과
로컬·원격 HEAD 일치를 확인합니다.

## 파일 구성

```text
.
├── main.py                         # 메뉴, 출력, 안전 종료
├── npu.py                          # 행렬 검증, MAC, epsilon, 패턴 생성기
├── simulator.py                    # JSON 케이스 격리와 성능 측정
├── data.json                       # 출처가 표시된 합성 6개 케이스
├── tests/                          # 경계·오류·CLI 테스트
├── scripts/check_data.py           # 합성 JSON 6/6 검증
├── scripts/check_style.py          # 스타일·docstring·Python 3.8 검사
├── scripts/check_syntax.py         # 전체 Python 파일 구문 검사
├── scripts/verify_remote.py        # PUBLIC/main/HEAD 검증
├── .github/workflows/verify.yml    # Python 3.8·3.14 CI
├── docs/evidence/logs/             # 실제 실행 출력
└── Makefile                        # 로컬·원격 검증 진입점
```
