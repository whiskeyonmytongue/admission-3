"""표준 라이브러리만으로 프로젝트의 Python 스타일을 검사한다."""

import ast
import subprocess
import sys
import tokenize
from io import StringIO
from pathlib import Path
from typing import Iterable, List, Optional, Set


ROOT = Path(__file__).resolve().parents[1]
PYTHON_VERSION = (3, 8)
CODE_LINE_LIMIT = 79
TEXT_LINE_LIMIT = 72
MAKE_LINE_LIMIT = 100
FUNCTION_LINE_LIMIT = 50


def source_paths() -> List[Path]:
    """Git 관리 대상과 새로 만든 Python·Makefile 경로를 반환한다."""
    try:
        output = subprocess.check_output(
            [
                "git",
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                "*.py",
                "Makefile",
            ],
            cwd=ROOT,
            universal_newlines=True,
            stderr=subprocess.DEVNULL,
        )
        paths = [ROOT / item for item in output.split("\0") if item]
    except (OSError, subprocess.CalledProcessError):
        paths = list(ROOT.glob("*.py"))
        paths.extend((ROOT / "scripts").rglob("*.py"))
        paths.extend((ROOT / "tests").rglob("*.py"))
        makefile = ROOT / "Makefile"
        if makefile.exists():
            paths.append(makefile)
    return sorted(
        path
        for path in paths
        if path.exists() and ".git" not in path.parts
    )


def add_error(
    errors: List[str],
    path: Path,
    line: int,
    message: str,
) -> None:
    """일관된 파일:줄 형식으로 오류를 추가한다."""
    relative = path.relative_to(ROOT)
    errors.append("{0}:{1}: {2}".format(relative, line, message))


def decode_source(path: Path, errors: List[str]) -> Optional[str]:
    """UTF-8·LF·마지막 개행 규칙을 검사하고 텍스트를 반환한다."""
    try:
        data = path.read_bytes()
    except OSError as error:
        add_error(
            errors,
            path,
            1,
            "파일을 읽을 수 없습니다: {0}".format(error),
        )
        return None
    try:
        source = data.decode("utf-8")
    except UnicodeDecodeError as error:
        line = data[:error.start].count(b"\n") + 1
        add_error(errors, path, line, "UTF-8 파일이 아닙니다.")
        return None
    if "\r" in source:
        add_error(errors, path, 1, "줄바꿈은 LF만 사용해야 합니다.")
    if source and not source.endswith("\n"):
        add_error(
            errors,
            path,
            len(source.splitlines()),
            "마지막 개행이 없습니다.",
        )
    for number, line in enumerate(source.splitlines(), start=1):
        if line.rstrip(" \t") != line:
            add_error(errors, path, number, "줄 끝 공백이 있습니다.")
    return source


def docstring_lines(source: str) -> Set[int]:
    """AST에서 실제 docstring에 해당하는 줄 번호를 반환한다."""
    lines = set()  # type: Set[int]
    try:
        tree = ast.parse(source, feature_version=PYTHON_VERSION)
    except SyntaxError:
        return lines
    nodes = [tree]
    nodes.extend(ast.walk(tree))
    for node in nodes:
        body = getattr(node, "body", None)
        if not body or not isinstance(body, list):
            continue
        first = body[0]
        if not isinstance(first, ast.Expr):
            continue
        if not isinstance(first.value, ast.Constant):
            continue
        if not isinstance(first.value.value, str):
            continue
        end_line = first.end_lineno or first.lineno
        lines.update(range(first.lineno, end_line + 1))
    return lines


def text_lines(source: str) -> Set[int]:
    """주석 또는 docstring이 놓인 줄 번호를 반환한다."""
    lines = docstring_lines(source)
    try:
        tokens = tokenize.generate_tokens(StringIO(source).readline)
        for token in tokens:
            if token.type == tokenize.COMMENT:
                lines.update(range(token.start[0], token.end[0] + 1))
    except (IndentationError, tokenize.TokenError):
        return lines
    return lines


def check_python_lines(
    path: Path,
    source: str,
    errors: List[str],
) -> None:
    """Python 파일의 탭·들여쓰기·줄 길이를 검사한다."""
    limited_lines = text_lines(source)
    for number, line in enumerate(source.splitlines(), start=1):
        if "\t" in line:
            add_error(errors, path, number, "Python 코드에 탭이 있습니다.")
        limit = TEXT_LINE_LIMIT if number in limited_lines else CODE_LINE_LIMIT
        if len(line) > limit:
            kind = "주석/docstring" if number in limited_lines else "코드"
            add_error(
                errors,
                path,
                number,
                "{0} 줄이 {1}자를 초과합니다 ({2}자).".format(
                    kind,
                    limit,
                    len(line),
                ),
            )
    check_indent_tokens(path, source, errors)


def check_indent_tokens(
    path: Path,
    source: str,
    errors: List[str],
) -> None:
    """실제 suite의 들여쓰기 증가 폭이 4칸인지 검사한다."""
    indent_stack = [0]
    try:
        tokens = tokenize.generate_tokens(StringIO(source).readline)
        for token in tokens:
            if token.type == tokenize.INDENT:
                width = len(token.string.expandtabs(8))
                if width != indent_stack[-1] + 4:
                    add_error(
                        errors,
                        path,
                        token.start[0],
                        "새 코드 블록은 4칸 들여써야 합니다.",
                    )
                indent_stack.append(width)
            elif token.type == tokenize.DEDENT and len(indent_stack) > 1:
                indent_stack.pop()
    except (IndentationError, tokenize.TokenError):
        return


def public_callables(tree: ast.Module) -> Iterable[ast.AST]:
    """docstring을 검사할 최상위·클래스 공개 API를 순회한다."""
    public_types = (
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
    )
    for node in tree.body:
        if isinstance(node, public_types) and not node.name.startswith("_"):
            yield node
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if not isinstance(
                    child,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                ):
                    continue
                if child.name == "__init__" or not child.name.startswith("_"):
                    yield child


def check_ast(path: Path, source: str, errors: List[str]) -> None:
    """최소 Python 문법, docstring, 함수 길이를 검사한다."""
    try:
        tree = ast.parse(
            source,
            filename=str(path),
            feature_version=PYTHON_VERSION,
        )
    except SyntaxError as error:
        add_error(
            errors,
            path,
            error.lineno or 1,
            "Python {0}.{1} 문법 오류".format(*PYTHON_VERSION),
        )
        return
    if ast.get_docstring(tree, clean=False) is None:
        add_error(errors, path, 1, "모듈 docstring이 없습니다.")
    if "tests" not in path.relative_to(ROOT).parts:
        for node in public_callables(tree):
            if ast.get_docstring(node, clean=False) is None:
                add_error(
                    errors,
                    path,
                    node.lineno,
                    "공개 API {0}에 docstring이 없습니다.".format(
                        node.name
                    ),
                )
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            if length > FUNCTION_LINE_LIMIT:
                add_error(
                    errors,
                    path,
                    node.lineno,
                    "함수 {0}가 50줄을 초과합니다 ({1}줄).".format(
                        node.name,
                        length,
                    ),
                )


def check_makefile(path: Path, source: str, errors: List[str]) -> None:
    """Makefile 줄 길이를 검사하되 recipe 탭은 허용한다."""
    for number, line in enumerate(source.splitlines(), start=1):
        if len(line) > MAKE_LINE_LIMIT:
            add_error(
                errors,
                path,
                number,
                "Makefile 줄이 {0}자를 초과합니다 ({1}자).".format(
                    MAKE_LINE_LIMIT,
                    len(line),
                ),
            )


def check_file(path: Path, errors: List[str]) -> None:
    """파일 종류에 맞는 스타일 규칙을 적용한다."""
    source = decode_source(path, errors)
    if source is None:
        return
    if path.name == "Makefile":
        check_makefile(path, source, errors)
        return
    check_python_lines(path, source, errors)
    check_ast(path, source, errors)


def main() -> int:
    """전체 검사 결과를 출력하고 성공 여부를 종료 코드로 반환한다."""
    errors = []  # type: List[str]
    paths = source_paths()
    if not paths:
        print("Style check: FAIL", file=sys.stderr)
        print("검사할 Python 또는 Makefile이 없습니다.", file=sys.stderr)
        return 1
    for path in paths:
        check_file(path, errors)
    if errors:
        print("Style check: FAIL", file=sys.stderr)
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(
        "Style check: PASS ({0} files, Python {1}.{2}+)".format(
            len(paths),
            *PYTHON_VERSION
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
