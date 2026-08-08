PYTHON ?= python3

.PHONY: all verify test syntax json-check cli-check run bonus clean verify-remote

all: verify

verify: test syntax json-check cli-check
	@echo "[PASS] 로컬 필수·보너스 검증 완료"

test:
	$(PYTHON) -m unittest -v

syntax:
	$(PYTHON) -m py_compile main.py npu.py simulator.py tests/*.py scripts/*.py
	$(PYTHON) scripts/check_python38.py

json-check:
	$(PYTHON) -c 'from pathlib import Path; from simulator import analyze_data, load_json_file; r = analyze_data(load_json_file(Path("data.json"))); assert (r["total"], r["passed"], r["failed"]) == (6, 6, 0); print("[PASS] data.json 6/6")'

cli-check:
	@printf '' | $(PYTHON) main.py | grep -q '안전하게 종료'
	@echo "[PASS] EOF 안전 종료"

run:
	$(PYTHON) main.py

bonus:
	$(PYTHON) main.py --generate 5

clean:
	@find . -type f -name '*.py[co]' -delete
	@find . -type d -name '__pycache__' -empty -delete

verify-remote: verify
	@remote_url="$$(git remote get-url origin)"; case "$$remote_url" in *whiskeyonmytongue/admission-3*) ;; *) echo "[FAIL] origin 주소가 admission-3 저장소가 아닙니다."; exit 1;; esac
	@remote_head="$$(git ls-remote --exit-code origin refs/heads/main | awk '{print $$1}')"; local_head="$$(git rev-parse HEAD)"; test "$$remote_head" = "$$local_head" || { echo "[FAIL] 로컬과 origin/main HEAD가 다릅니다."; exit 1; }
	@test "$$(gh repo view whiskeyonmytongue/admission-3 --json visibility --jq .visibility)" = "PUBLIC"
	@test "$$(gh repo view whiskeyonmytongue/admission-3 --json defaultBranchRef --jq .defaultBranchRef.name)" = "main"
	@echo "[PASS] PUBLIC/main/HEAD 일치"

