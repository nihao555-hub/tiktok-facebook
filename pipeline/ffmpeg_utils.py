"""FFmpeg / ffprobe 薄封装。"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from pathlib import Path

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


def run(args: list[str], quiet: bool = True) -> None:
    cmd = [FFMPEG, "-y", *(["-loglevel", "error"] if quiet else []), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n  {shlex.join(cmd)}\n{proc.stderr[-2000:]}")


def duration(path: str | Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(json.loads(out.stdout)["format"]["duration"])
    except Exception:  # noqa: BLE001
        return 0.0


def dimensions(path: str | Path) -> tuple[int, int]:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    try:
        st = json.loads(out.stdout)["streams"][0]
        return int(st["width"]), int(st["height"])
    except Exception:  # noqa: BLE001
        return 0, 0


def last_frame(video: str | Path, dst: str | Path) -> Path:
    """抽取视频接近结尾的一帧存为图片。

    用于「链式尾帧」连贯：把上一镜的尾帧当作下一镜出图的首帧参考，让相邻镜头在
    打光/主体/色调上自然顺接。优先用 -sseof 从尾部定位；失败再按时长回退定位。
    """
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        run(["-sseof", "-0.2", "-i", str(video), "-frames:v", "1", "-q:v", "2",
             "-update", "1", str(dst)])
    except RuntimeError:
        dst.unlink(missing_ok=True)
    if not dst.exists() or dst.stat().st_size < 1024:
        dur = duration(video)
        ss = max(0.0, dur - 0.1)
        run(["-ss", f"{ss}", "-i", str(video), "-frames:v", "1", "-q:v", "2",
             "-update", "1", str(dst)])
    return dst


def has_audio(path: str | Path) -> bool:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    try:
        return bool(json.loads(out.stdout).get("streams"))
    except Exception:  # noqa: BLE001
        return False
