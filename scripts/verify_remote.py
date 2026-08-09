"""정확한 GitHub 저장소의 PUBLIC main과 로컬 HEAD를 검증한다."""

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_REPOSITORY = "whiskeyonmytongue/admission-3"


def run(*arguments: str) -> str:
    """프로젝트 루트에서 외부 명령을 실행하고 출력을 반환한다."""
    return subprocess.check_output(
        list(arguments), cwd=ROOT, universal_newlines=True,
        stderr=subprocess.STDOUT
    ).strip()


def fail(message: str, pending: bool = False) -> int:
    """실패 또는 미완료 메시지를 출력하고 실패 코드를 반환한다."""
    state = "PENDING" if pending else "FAIL"
    print("verify-remote: {0} - {1}".format(state, message))
    return 1


def repository_name(remote: str) -> Optional[str]:
    """허용한 GitHub URL 형식에서 owner/repository를 추출한다."""
    scp_match = re.fullmatch(
        r"git@github\.com:([^/]+/[^/]+?)(?:\.git)?",
        remote,
    )
    if scp_match:
        return scp_match.group(1)
    parsed = urlparse(remote)
    if (
        parsed.scheme not in ("https", "ssh")
        or parsed.hostname != "github.com"
        or parsed.query
        or parsed.fragment
    ):
        return None
    if parsed.scheme == "ssh" and parsed.username not in (None, "git"):
        return None
    path = parsed.path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.strip("/").split("/")
    return "/".join(parts) if len(parts) == 2 and all(parts) else None


def _repository_metadata(repository: str) -> Dict[str, Any]:
    return json.loads(
        run(
            "gh", "repo", "view", repository,
            "--json", "visibility,defaultBranchRef",
        )
    )


def _metadata_fields(metadata: object) -> Tuple[object, object]:
    if not isinstance(metadata, dict):
        raise ValueError("GitHub 메타데이터가 객체 형식이 아닙니다.")
    branch_metadata = metadata.get("defaultBranchRef")
    if branch_metadata is not None and not isinstance(branch_metadata, dict):
        raise ValueError("defaultBranchRef가 객체 형식이 아닙니다.")
    default_branch = (
        branch_metadata.get("name")
        if isinstance(branch_metadata, dict)
        else None
    )
    return metadata.get("visibility"), default_branch


def main() -> int:
    """PUBLIC main과 로컬·원격 HEAD가 모두 일치하면 성공한다."""
    try:
        remote = run("git", "remote", "get-url", "origin")
    except (OSError, subprocess.CalledProcessError):
        return fail("origin이 아직 설정되지 않았습니다.", pending=True)
    if repository_name(remote) != EXPECTED_REPOSITORY:
        return fail("origin 대상이 올바르지 않습니다: {0}".format(remote))
    try:
        local_head = run("git", "rev-parse", "HEAD")
        remote_line = run("git", "ls-remote", "origin", "refs/heads/main")
    except (OSError, subprocess.CalledProcessError) as error:
        return fail("원격 main을 확인하지 못했습니다: {0}".format(error), True)
    if not remote_line:
        return fail("원격 main 브랜치가 없습니다.", pending=True)
    remote_head = remote_line.split()[0]
    if local_head != remote_head:
        return fail(
            "HEAD 불일치: local={0}, remote={1}".format(
                local_head[:7], remote_head[:7]
            )
        )
    if not shutil.which("gh"):
        return fail("PUBLIC/default branch 확인에 필요한 gh가 없습니다.")
    try:
        metadata = _repository_metadata(EXPECTED_REPOSITORY)
        visibility, default_branch = _metadata_fields(metadata)
    except (
        OSError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        return fail("GitHub 메타데이터를 확인하지 못했습니다: {0}".format(error))
    if visibility != "PUBLIC" or default_branch != "main":
        return fail(
            "PUBLIC/main이 아닙니다: {0}/{1}".format(
                visibility, default_branch
            )
        )
    print("[PASS] PUBLIC/main/HEAD {0} 일치".format(local_head[:7]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
