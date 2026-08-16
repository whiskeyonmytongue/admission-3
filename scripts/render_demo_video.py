"""실제 콘솔 실행 결과를 터미널 데모 영상으로 렌더링한다.

이 스크립트는 제출 프로그램의 실행 결과를 먼저 수집한 뒤, 터미널 화면
형태의 프레임으로 만들어 MP4로 인코딩한다. 실행에는 개발용 Pillow와
ffmpeg가 필요하며, 과제 실행 자체에는 영향을 주지 않는다.
"""

import os
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import List, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "docs" / "evidence" / "videos"
MANDATORY_VIDEO = VIDEO_DIR / "mandatory-modes.mp4"
BONUS_VIDEO = VIDEO_DIR / "bonus-mode.mp4"
WIDTH = 1280
HEIGHT = 720
FPS = 12
FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"


def _font(size: int) -> ImageFont.FreeTypeFont:
    """macOS 한글 폰트를 로드한다."""
    return ImageFont.truetype(FONT_PATH, size)


def _run_pty(
    arguments: Sequence[str], inputs: Sequence[str]
) -> Tuple[int, str]:
    """대화형 프로그램을 pseudo-terminal에서 실행하고 출력을 수집한다."""
    child_pid, master_fd = pty.fork()
    if child_pid == 0:
        os.chdir(ROOT)
        os.execv(arguments[0], list(arguments))

    chunks = []  # type: List[bytes]
    input_index = 0
    deadline = time.monotonic() + 30
    child_status = None
    while time.monotonic() < deadline:
        if input_index < len(inputs):
            time.sleep(0.08)
            os.write(master_fd, (inputs[input_index] + "\n").encode())
            input_index += 1
        readable, _, _ = select.select([master_fd], [], [], 0.1)
        if readable:
            try:
                chunks.append(os.read(master_fd, 8192))
            except OSError:
                break
        waited_pid, status = os.waitpid(child_pid, os.WNOHANG)
        if waited_pid:
            child_status = status
            break
    if child_status is None:
        _, child_status = os.waitpid(child_pid, 0)
    try:
        os.close(master_fd)
    except OSError:
        pass
    return os.waitstatus_to_exitcode(child_status), b"".join(chunks).decode(
        "utf-8", "replace"
    )


def _clean_lines(output: str) -> List[str]:
    """터미널 제어 문자를 제거하고 긴 줄을 화면 폭에 맞춘다."""
    cleaned = output.replace("\r\n", "\n").replace("\r", "\n")
    lines = []  # type: List[str]
    for raw_line in cleaned.splitlines():
        line = raw_line.replace("\x1b", "")
        line = line.replace(str(ROOT) + "/", "")
        wrapped = textwrap.wrap(
            line,
            width=68,
            replace_whitespace=False,
            drop_whitespace=False,
        )
        lines.extend(wrapped or [""])
    return lines


def _draw_frame(
    command: str,
    lines: Sequence[str],
    caption: str,
    visible_count: int,
) -> Image.Image:
    """현재까지 공개할 출력 줄을 하나의 터미널 프레임으로 그린다."""
    image = Image.new("RGB", (WIDTH, HEIGHT), (18, 22, 28))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 72), fill=(32, 43, 54))
    draw.ellipse((28, 27, 42, 41), fill=(255, 95, 86))
    draw.ellipse((52, 27, 66, 41), fill=(255, 189, 46))
    draw.ellipse((76, 27, 90, 41), fill=(39, 201, 63))
    draw.text((112, 20), "Mini NPU Simulator · 실제 실행", font=_font(25),
              fill=(235, 241, 245))

    draw.rounded_rectangle((36, 96, WIDTH - 36, 654), radius=10,
                           fill=(11, 15, 19), outline=(67, 78, 88), width=2)
    draw.text((62, 116), "codyssey/admission-3 $ " + command,
              font=_font(21), fill=(117, 229, 153))

    max_rows = 17
    shown = list(lines[:visible_count])
    if len(shown) > max_rows:
        shown = shown[-max_rows:]
    y = 158
    for line in shown:
        color = (224, 229, 233)
        if "FAIL" in line or "오류" in line:
            color = (255, 132, 132)
        elif "PASS" in line or "판정: B" in line:
            color = (125, 230, 157)
        elif line.startswith("[") or line.startswith("==="):
            color = (126, 190, 255)
        draw.text((62, y), line, font=_font(20), fill=color)
        y += 27

    draw.rectangle((0, 678, WIDTH, HEIGHT), fill=(30, 38, 47))
    draw.text((40, 689), caption, font=_font(18), fill=(222, 229, 235))
    return image


def _append_scene(
    frames: List[Image.Image],
    command: str,
    output: str,
    caption: str,
    hold: int = 18,
) -> None:
    """출력을 한 줄씩 공개한 뒤 마지막 장면을 잠시 유지한다."""
    lines = _clean_lines(output)
    for count in range(0, len(lines) + 1):
        frame = _draw_frame(command, lines, caption, count)
        frames.extend([frame] * 2)
    final = _draw_frame(command, lines, caption, len(lines))
    frames.extend([final] * hold)


def _append_summary(
    frames: List[Image.Image],
    summary: str,
    command: str,
    caption: str,
) -> None:
    """한 영상에 포함된 장면의 핵심 결과와 재현 명령을 요약한다."""
    lines = summary.splitlines()
    for count in range(len(lines) + 1):
        frames.extend(
            [_draw_frame(command, lines, caption, count)] * 2
        )
    final = _draw_frame(command, lines, caption, len(lines))
    frames.extend([final] * 30)


def _encode(frames: Sequence[Image.Image], output_path: Path) -> None:
    """PNG 임시 프레임을 지정한 H.264 MP4로 묶는다."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg가 필요합니다.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="npu-video-") as directory:
        frame_dir = Path(directory)
        for index, frame in enumerate(frames):
            frame.save(frame_dir / "frame-{0:05d}.png".format(index))
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-framerate",
                str(FPS),
                "-i",
                str(frame_dir / "frame-%05d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output_path),
            ],
            check=True,
        )


def _collect_outputs() -> Tuple[str, str, str]:
    """모드 1·2와 보너스 명령을 실제로 실행해 출력을 수집한다."""
    mode1_code, mode1 = _run_pty(
        [sys.executable, "main.py"],
        [
            "1",
            "0 1 0",
            "1 1 1",
            "0 1 0",
            "1 0 1",
            "0 1 0",
            "1 0 1",
            "1 0 1",
            "0 1 0",
            "1 0 1",
        ],
    )
    mode2_code, mode2 = _run_pty([sys.executable, "main.py"], ["2", ""])
    bonus_code, bonus = _run_pty([sys.executable, "main.py"], ["3", "5"])
    if mode1_code != 0 or mode2_code != 1 or bonus_code != 0:
        raise RuntimeError(
            "실행 결과가 예상과 다릅니다: {0}, {1}, {2}".format(
                mode1_code, mode2_code, bonus_code
            )
        )

    return mode1, mode2, bonus


def _build_mandatory_frames(mode1: str, mode2: str) -> List[Image.Image]:
    """모드 1·2만 담은 필수 실행 영상의 프레임을 만든다."""
    frames = []  # type: List[Image.Image]
    _append_scene(
        frames,
        "python3 main.py",
        mode1,
        "모드 1 · 직접 입력한 3×3 필터 A/B와 패턴의 MAC 점수를 비교",
    )
    _append_scene(
        frames,
        "python3 main.py  (입력: 2 → 기본 data.json)",
        mode2,
        "모드 2 · JSON 케이스를 독립 분석하고 성능 표와 집계를 출력",
    )
    _append_summary(
        frames,
        "필수 실행 요약\n\n"
        "모드 1  | A=1, B=5 → 판정 B\n"
        "모드 2  | 총 6개 · PASS 3 · 예상 동점 FAIL 3\n\n"
        "재현: python3 main.py\n"
        "      python3 main.py --json data.json",
        "mandatory complete",
        "필수 모드의 실제 결과 요약",
    )
    return frames


def _build_bonus_frames(bonus: str) -> List[Image.Image]:
    """보너스 명령만 담은 별도 영상의 프레임을 만든다."""
    frames = []  # type: List[Image.Image]
    _append_scene(
        frames,
        "python3 main.py  (입력: 3 → N=5)",
        bonus,
        "보너스 · Cross/X 생성과 2D·1D MAC 평균 시간 비교",
    )
    _append_summary(
        frames,
        "보너스 실행 요약\n\n"
        "5×5 Cross/X 행렬 생성\n"
        "3·5·13·25 크기 2D/1D 평균 시간 비교\n\n"
        "재현: python3 main.py → 메뉴 3 → N=5",
        "bonus complete",
        "보너스 명령의 실제 결과 요약",
    )
    return frames


def main() -> int:
    """실제 모드와 보너스를 각각 검증하고 별도 영상을 생성한다."""
    mode1, mode2, bonus = _collect_outputs()
    mandatory = _build_mandatory_frames(mode1, mode2)
    bonus_frames = _build_bonus_frames(bonus)
    _encode(mandatory, MANDATORY_VIDEO)
    _encode(bonus_frames, BONUS_VIDEO)
    print("created {0} ({1:.1f} sec)".format(
        MANDATORY_VIDEO, len(mandatory) / FPS
    ))
    print("created {0} ({1:.1f} sec)".format(
        BONUS_VIDEO, len(bonus_frames) / FPS
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
