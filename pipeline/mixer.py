"""混剪 + 平台原生装饰（全部用 FFmpeg，可在 Linux 无界面环境直接渲染出 MP4）。

assemble(): 把每个分镜的视频片段 + 该分镜配音对齐拼接成带人声的底片（时间轴严格对齐）。
render_final(): 烧录字幕(ASS) + 进度条 + 品牌 logo + 背景音乐，产出最终成片。
"""

from __future__ import annotations

from pathlib import Path

from . import ffmpeg_utils as ff
from .config import REPO_ROOT, TaskConfig
from .script_model import Script


def _resolve(path: str) -> Path | None:
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / path
    return p if p.exists() else None


def assemble(
    script: Script,
    video_paths: list[Path],
    audio_paths: list[Path],
    cfg: TaskConfig,
    workdir: Path,
) -> Path:
    """每个分镜：视频(已定长=scene.seconds) + 配音(补静音/截断到 scene.seconds) -> 拼接。"""
    workdir.mkdir(parents=True, exist_ok=True)
    seg_paths: list[Path] = []
    for s, vp, ap in zip(script.scenes, video_paths, audio_paths):
        sec = float(s.seconds)
        seg = workdir / f"seg_{s.index:02d}.mp4"
        ff.run([
            "-i", str(vp),
            "-i", str(ap),
            "-filter_complex",
            f"[1:a]apad,atrim=0:{sec:.3f},asetpts=PTS-STARTPTS[a]",
            "-map", "0:v:0", "-map", "[a]",
            "-t", f"{sec:.3f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(cfg.fps),
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            "-video_track_timescale", "30000",
            str(seg),
        ])
        seg_paths.append(seg)

    listfile = workdir / "concat.txt"
    listfile.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in seg_paths) + "\n", encoding="utf-8"
    )
    base = workdir / "base.mp4"
    ff.run(["-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(base)])
    return base


def extract_voiceover(base: Path, workdir: Path) -> Path:
    """抽出底片人声（给 whisper 做字幕时间戳，单声道 16k）。"""
    voice = workdir / "voice.wav"
    ff.run(["-i", str(base), "-vn", "-ac", "1", "-ar", "16000", str(voice)])
    return voice


def render_final(
    base: Path,
    ass: Path,
    fontsdir: str | None,
    cfg: TaskConfig,
    out_path: Path,
    bgm_override: str | None = None,
) -> Path:
    dec = cfg.get("decorate", default={}) or {}
    logo = _resolve(dec.get("logo", ""))
    bgm = _resolve(bgm_override) if bgm_override else _resolve(dec.get("bgm", ""))
    bgm_vol = float(dec.get("bgm_volume", 0.18))

    tokens: list[str] = ["-i", str(base)]
    nxt = 1
    li = bi = None
    if logo:
        tokens += ["-i", str(logo)]
        li, nxt = nxt, nxt + 1
    if bgm:
        tokens += ["-stream_loop", "-1", "-i", str(bgm)]
        bi, nxt = nxt, nxt + 1

    ass_arg = f"ass={ass.as_posix()}"
    if fontsdir:
        ass_arg += f":fontsdir={fontsdir}"

    fc = f"[0:v]{ass_arg}[v0]"
    cur = "[v0]"
    if li is not None:
        fc += f";[{li}:v]scale=iw*0.14:-1[lg];{cur}[lg]overlay=W-w-30:40[vout]"
        cur = "[vout]"

    aout = None
    if bi is not None:
        fc += f";[{bi}:a]volume={bgm_vol}[bg];[0:a][bg]amix=inputs=2:duration=first[aout]"
        aout = "[aout]"

    args = tokens + ["-filter_complex", fc, "-map", cur]
    args += ["-map", aout] if aout else ["-map", "0:a?"]
    args += [
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(cfg.fps),
        "-c:a", "aac", "-ar", "44100", "-shortest", str(out_path),
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ff.run(args)
    return out_path
