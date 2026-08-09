PYTHON ?= python3

.PHONY: all verify runtime syntax style test json-check cli-check run bonus clean
.PHONY: verify-remote

all: verify

verify: runtime syntax style test json-check cli-check
	@echo "[PASS] 로컬 필수·보너스 검증 완료"

runtime:
	@$(PYTHON) scripts/check_runtime.py

syntax:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m py_compile \
		main.py npu.py simulator.py scripts/check_data.py \
		scripts/check_runtime.py scripts/check_style.py \
		tests/test_cli.py tests/test_npu.py tests/test_simulator.py \
		tests/test_style.py

style:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/check_style.py

test:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest discover -s tests -v

json-check:
	@PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m scripts.check_data

cli-check:
	@task_output=$$(mktemp); \
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
	@remote_url="$$(git remote get-url origin)"; \
		case "$$remote_url" in \
		*whiskeyonmytongue/admission-3*) ;; \
		*) echo "[FAIL] origin 주소가 admission-3 저장소가 아닙니다."; exit 1;; \
		esac
	@remote_head="$$(git ls-remote --exit-code origin refs/heads/main | \
		awk '{print $$1}')"; \
		local_head="$$(git rev-parse HEAD)"; \
		test "$$remote_head" = "$$local_head" || { \
		echo "[FAIL] 로컬과 origin/main HEAD가 다릅니다."; exit 1; }
	@test "$$(gh repo view whiskeyonmytongue/admission-3 \
		--json visibility --jq .visibility)" = "PUBLIC"
	@test "$$(gh repo view whiskeyonmytongue/admission-3 \
		--json defaultBranchRef --jq .defaultBranchRef.name)" = "main"
	@echo "[PASS] PUBLIC/main/HEAD 일치"
