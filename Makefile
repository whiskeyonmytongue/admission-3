PYTHON ?= python3
MKTEMP ?= mktemp

.PHONY: all verify runtime syntax style test json-check cli-check run bonus clean
.PHONY: verify-remote

all: verify

verify: runtime syntax style test json-check cli-check
	@echo "[PASS] 로컬 필수·보너스 검증 완료"

runtime:
	@$(PYTHON) scripts/check_runtime.py

syntax:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m scripts.check_syntax

style:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/check_style.py

test:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest discover -s tests -v

json-check:
	@PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m scripts.check_data

cli-check:
	@task_output=$$($(MKTEMP)) || { \
		echo "[FAIL] 임시 출력 파일을 만들지 못했습니다." >&2; exit 1; \
	}; \
		trap 'rm -f "$$task_output"' EXIT; \
		printf '' | PYTHONDONTWRITEBYTECODE=1 $(PYTHON) main.py \
			>"$$task_output"; \
		cli_status=$$?; \
		test "$$cli_status" -eq 0 && \
		grep -q '안전하게 종료' "$$task_output"
	@echo "[PASS] EOF 안전 종료"

run:
	$(PYTHON) main.py

bonus:
	$(PYTHON) main.py --generate 5

clean:
	@find . -type f -name '*.py[co]' -delete
	@find . -type d -name '__pycache__' -empty -delete

verify-remote: verify
	@$(PYTHON) scripts/verify_remote.py
