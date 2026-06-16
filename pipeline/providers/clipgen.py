"""AI 片段生成 / 本地素材准备。

每个分镜产出一段 W x H、时长=scene.seconds 的视频片段（无音轨，混剪阶段再叠加配音）。

provider:
  local        : 用 media/clips 下的素材（不够则合成占位片段）—— 零 key 可跑
  wuyinkeji    : gpt-image-2 出超写实图 -> 无垠 video_google_omni 把图动起来（默认在线链路）
  replicate    : 调 Replicate（图生视频/文生视频模型），用你自己的 token
  kling        : 调可灵 API
  openai_video : 调 OpenAI 视频生成接口
  runway       : 调 Runway API
"""

from __future__ import annotations

import math
import time
from pathlib import Path

import requests

from .. import ffmpeg_utils as ff
from ..config import REPO_ROOT, Secrets, TaskConfig
from ..script_model import Scene, Script
from . import imagegen

_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def _scale_crop(src: Path, dst: Path, w: int, h: int, seconds: float, fps: int,
                delogo: str | None = None) -> None:
    """把任意素材缩放裁剪成 WxH 并定长（视频循环/截断，图片做缓慢推近）。

    delogo 不为空时先用 delogo 抹掉 AI 视频右下角的角标水印，再缩放铺满。"""
    pre = f"delogo={delogo}," if delogo else ""
    vf = (
        f"{pre}scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},fps={fps},setsar=1"
    )
    if src.suffix.lower() in _IMAGE_EXT:
        ff.run(["-loop", "1", "-t", f"{seconds}", "-i", str(src),
                "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dst)])
    else:
        ff.run(["-stream_loop", "-1", "-t", f"{seconds}", "-i", str(src),
                "-an", "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dst)])


def _wm_delogo_box(raw: Path) -> str | None:
    """无垠/Veo 视频右下角有 ✨ 角标，按真实分辨率算出 delogo 区域抹掉它。"""
    vw, vh = ff.dimensions(raw)
    if vw <= 0 or vh <= 0:
        return None
    bw = max(2, round(vw * 0.235))
    bh = max(2, round(vh * 0.155))
    x = max(1, vw - bw - 1)
    y = max(1, vh - bh - 1)
    return f"x={x}:y={y}:w={bw}:h={bh}"


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

    if provider == "wuyinkeji":
        return _gen_wuyinkeji_all(script, cfg, secrets, workdir, w, h, fps)

    # ---- 其它在线生成 provider（预留接口）----
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
# wuyinkeji 链路：gpt-image-2 超写实图 -> video_google_omni 图生视频
# --------------------------------------------------------------------------
def _refs_dir() -> Path:
    return REPO_ROOT / "media" / "refs"


def _default_refs(limit: int = 4) -> list[str]:
    d = _refs_dir()
    if not d.exists():
        return []
    imgs = sorted(p for p in d.iterdir() if p.suffix.lower() in _IMAGE_EXT)
    return [str(p) for p in imgs[:limit]]


def _resolve_refs(scene: Scene) -> list[str]:
    """分镜指定了 ref_images 用指定的；否则用 media/refs 里的真实素材兜底。"""
    if scene.ref_images:
        out = []
        for name in scene.ref_images:
            p = Path(name)
            if not p.is_absolute():
                p = _refs_dir() / name
            if p.exists():
                out.append(str(p))
        if out:
            return out
    return _default_refs()


def _wuyin_submit(prompt: str, image_url: str, w: int, h: int,
                  seconds: int, secrets: Secrets) -> str:
    base = secrets.wuyin_base_url.rstrip("/")
    url = f"{base}/api/async/{secrets.wuyin_endpoint}"
    headers = {"Authorization": secrets.wuyin_api_key, "Content-Type": "application/json"}
    payload = {"prompt": prompt, "size": f"{w}x{h}", "duration": str(seconds)}
    if image_url:
        payload["images"] = image_url
    r = requests.post(url, params={"key": secrets.wuyin_api_key}, json=payload,
                      headers=headers, timeout=60)
    r.raise_for_status()
    body = r.json()
    data = body.get("data") or {}
    task_id = data.get("id") if isinstance(data, dict) else None
    if not task_id:
        raise RuntimeError(f"wuyinkeji 提交失败: {body}")
    return task_id


def _wuyin_poll(task_id: str, secrets: Secrets,
                timeout: float = 600, interval: float = 10) -> str:
    base = secrets.wuyin_base_url.rstrip("/")
    url = f"{base}/api/async/detail"
    headers = {"Authorization": secrets.wuyin_api_key, "Content-Type": "application/json"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(interval)
        r = requests.get(url, params={"key": secrets.wuyin_api_key, "id": task_id},
                         headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json().get("data") or {}
        status = data.get("status")
        if status == 2:
            results = data.get("result") or []
            if results:
                return results[0]
            raise RuntimeError(f"wuyinkeji 成功但无结果: {data}")
        if status == 3:
            raise RuntimeError(f"wuyinkeji 视频生成失败: {data.get('message')}")
    raise RuntimeError("wuyinkeji 轮询超时")


def _gen_wuyinkeji_all(script: Script, cfg: TaskConfig, secrets: Secrets,
                       workdir: Path, w: int, h: int, fps: int) -> list[Path]:
    if not secrets.grsai_api_key:
        raise RuntimeError("wuyinkeji 链路需要 GRSAI_API_KEY（先用 gpt-image-2 出图）")
    if not secrets.wuyin_api_key:
        raise RuntimeError("wuyinkeji 链路需要 WUYIN_API_KEY")
    strip_wm = bool(cfg.get("decorate", "strip_ai_watermark", default=True))
    vid_seconds = int(cfg.get("clipgen", "video_seconds", default=10))
    img_dir = workdir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for s in script.scenes:
        img_path = img_dir / f"scene_{s.index:02d}.png"
        refs = _resolve_refs(s)
        img = imagegen.generate_image(
            s.img_prompt, img_path, secrets, width=w, height=h, ref_images=refs)
        want = max(vid_seconds, int(math.ceil(s.seconds)))
        task_id = _wuyin_submit(s.mov_prompt, img.url, w, h, want, secrets)
        video_url = _wuyin_poll(task_id, secrets)
        raw = workdir / f"raw_{s.index:02d}.mp4"
        _download(video_url, raw)
        dst = workdir / f"scene_{s.index:02d}.mp4"
        delogo = _wm_delogo_box(raw) if strip_wm else None
        _scale_crop(raw, dst, w, h, s.seconds, fps, delogo=delogo)
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
