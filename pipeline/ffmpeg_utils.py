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
