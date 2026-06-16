"""AI 片段生成 / 本地素材准备。

每个分镜产出一段 W x H、时长=scene.seconds 的视频片段（无音轨，混剪阶段再叠加配音）。

provider:
  local        : 用 media/clips 下的素材（不够则合成占位片段）—— 零 key 可跑
  replicate    : 调 Replicate（图生视频/文生视频模型），用你自己的 token
  kling        : 调可灵 API
  openai_video : 调 OpenAI 视频生成接口
  runway       : 调 Runway API
后四个是接你"自己的 key"的位置：确认了具体服务后在对应函数里补上请求即可。
"""

from __future__ import annotations

from pathlib import Path

from .. import ffmpeg_utils as ff
from ..config import REPO_ROOT, Secrets, TaskConfig
from ..script_model import Script

_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def _scale_crop(src: Path, dst: Path, w: int, h: int, seconds: float, fps: int) -> None:
    """把任意素材缩放裁剪成 WxH 并定长（视频循环/截断，图片做缓慢推近）。"""
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},fps={fps},setsar=1"
    )
    if src.suffix.lower() in _IMAGE_EXT:
        ff.run(["-loop", "1", "-t", f"{seconds}", "-i", str(src),
                "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dst)])
    else:
        ff.run(["-stream_loop", "-1", "-t", f"{seconds}", "-i", str(src),
                "-an", "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dst)])


def _synthesize(dst: Path, w: int, h: int, seconds: float, fps: int, label: str, idx: int) -> None:
    """无素材时合成占位片段：渐变底 + 分镜描述文字（保证流水线可端到端跑通）。"""
    import textwrap

    colors = ["0x1f2937", "0x0f766e", "0x7c2d12", "0x4338ca", "0x9d174d", "0x065f46"]
    bg = colors[idx % len(colors)]
    clean = label.replace(":", " ").replace("'", " ").replace("\\", " ")[:90]
    safe = "\n".join(textwrap.wrap(clean, width=18)[:4])
    vf = (
        f"drawbox=x=0:y=0:w={w}:h={h}:color={bg}:t=fill,"
        f"drawtext=text='{safe}':fontcolor=white@0.85:fontsize=40:"
        f"x=(w-text_w)/2:y=h*0.7:line_spacing=12"
    )
    ff.run(["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:d={seconds}:r={fps}",
            "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dst)])


def _local_clips() -> list[Path]:
    root = REPO_ROOT / "media" / "clips"
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if p.suffix.lower() in (_VIDEO_EXT | _IMAGE_EXT))


def generate_clips(script: Script, cfg: TaskConfig, secrets: Secrets, workdir: Path) -> list[Path]:
    provider = (secrets.clipgen_provider or "local").lower()
    workdir.mkdir(parents=True, exist_ok=True)
    w, h, fps = cfg.width, cfg.height, cfg.fps

    if provider == "local":
        pool = _local_clips()
        out: list[Path] = []
        for s in script.scenes:
            dst = workdir / f"scene_{s.index:02d}.mp4"
            if pool:
                src = pool[s.index % len(pool)]
                _scale_crop(src, dst, w, h, s.seconds, fps)
            else:
                _synthesize(dst, w, h, s.seconds, fps, s.visual_prompt or s.on_screen_text, s.index)
            out.append(dst)
        return out

    # ---- 接入你自己 key 的在线生成 provider ----
    dispatch = {
        "replicate": _gen_replicate,
        "kling": _gen_kling,
        "openai_video": _gen_openai_video,
        "runway": _gen_runway,
    }
    fn = dispatch.get(provider)
    if fn is None:
        raise ValueError(f"未知 CLIPGEN_PROVIDER={provider}")
    if not secrets.clipgen_api_key:
        raise RuntimeError(
            f"CLIPGEN_PROVIDER={provider} 需要 CLIPGEN_API_KEY，请在 .env 填入你自己的 key。"
        )
    out = []
    for s in script.scenes:
        dst = workdir / f"scene_{s.index:02d}.mp4"
        raw = fn(s.visual_prompt, s.seconds, w, h, secrets)
        _scale_crop(raw, dst, w, h, s.seconds, fps)
        out.append(dst)
    return out


# --------------------------------------------------------------------------
# 在线 provider 实现位（确认你用哪个服务后，把对应函数补成真实请求即可）
# 统一约定：下载生成好的视频到本地，返回该文件 Path。
# --------------------------------------------------------------------------
def _download(url: str, dst: Path) -> Path:
    import requests

    dst.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(dst, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
    return dst


def _gen_replicate(prompt: str, seconds: float, w: int, h: int, secrets: Secrets) -> Path:
    raise NotImplementedError("待接入：用 secrets.clipgen_api_key 调 Replicate，返回下载后的视频 Path")


def _gen_kling(prompt: str, seconds: float, w: int, h: int, secrets: Secrets) -> Path:
    raise NotImplementedError("待接入：用 secrets.clipgen_api_key 调可灵 API，返回下载后的视频 Path")


def _gen_openai_video(prompt: str, seconds: float, w: int, h: int, secrets: Secrets) -> Path:
    raise NotImplementedError("待接入：用 secrets.clipgen_api_key 调 OpenAI 视频接口，返回下载后的视频 Path")


def _gen_runway(prompt: str, seconds: float, w: int, h: int, secrets: Secrets) -> Path:
    raise NotImplementedError("待接入：用 secrets.clipgen_api_key 调 Runway API，返回下载后的视频 Path")
