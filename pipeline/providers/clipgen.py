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
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from .. import ffmpeg_utils as ff
from ..config import REPO_ROOT, Secrets, TaskConfig
from ..script_model import Scene, Script
from . import imagegen

_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}

# 多线程并发出图/出视频时，保证控制台进度逐行打印不串行
_LOG_LOCK = threading.Lock()


def _log(msg: str) -> None:
    with _LOG_LOCK:
        print(msg, flush=True)


# 视频模型安全过滤容易误杀的词；软化重试时去掉它们
_RISKY = (
    "knife", "blade", "cut", "slice", "chop", "blood", "wound", "gun", "weapon",
    "fight", "punch", "kick", "fire", "flame", "burn", "explos", "spark", "weld",
    "molten", "danger", "accident", "injur", "child", "children", "kid", "baby",
    "smoke", "drug", "alcohol", "knives",
)


# 瞬时性错误（重试同一请求可能恢复）：无可用通道 / 超时 / 限流 / 网络 / 5xx 等。
# 这类失败软化 prompt 没用，应该退避后「原样」重试。
_TRANSIENT = (
    "no available channel", "no channel", "通道", "timeout", "超时", "timed out",
    "rate limit", "ratelimit", "too many", "429", "500", "502", "503", "504",
    "connection", "connect", "reset", "temporar", "try again", "overload",
    "busy", "unavailable", "gateway", "重试", "繁忙", "排队", "稍后",
)


def _is_transient(exc: Exception) -> bool:
    """是否为瞬时性错误（原样重试可能恢复）。区别于安全过滤/内容类失败。"""
    msg = str(exc).lower()
    return any(m in msg for m in _TRANSIENT)


def _soften_prompt(prompt: str, level: int) -> str:
    """level1：去掉敏感词 + 追加安全说明；level2：换成最通用安全推近。"""
    if level >= 2:
        return ("slow, gentle cinematic push-in with subtle natural parallax; calm, steady, "
                "professional and brand-safe; ordinary everyday scene, nothing sensitive")
    words = [w for w in prompt.split() if w.strip(".,").lower() not in _RISKY]
    base = " ".join(words).strip() or "slow gentle push-in"
    return base + ". Calm, safe, professional, brand-safe; no sensitive or dangerous content."


def _kenburns(src: Path, dst: Path, w: int, h: int, seconds: float, fps: int) -> None:
    """视频生成被安全过滤拒绝时的兜底：在 gpt-image-2 静帧上做缓慢推近，避免整条流水线崩。"""
    frames = max(1, int(round(seconds * fps)))
    vf = (
        f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
        f"zoompan=z='min(1.0+0.0016*on,1.14)':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},setsar=1"
    )
    ff.run(["-loop", "1", "-i", str(src), "-vf", vf, "-t", f"{seconds}",
            "-r", str(fps), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dst)])


def _slate(dst: Path, w: int, h: int, seconds: float, fps: int) -> None:
    """出图与文生视频都失败时的最后兜底：纯色板，保证该分镜仍产出片段、整条流水线不崩。"""
    ff.run(["-f", "lavfi", "-i", f"color=c=0x1b2230:s={w}x{h}:d={seconds}:r={fps}",
            "-t", f"{seconds}", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dst)])


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
        # -t 必须放在 -i 之后做输出时长限制；放输入侧配合 -stream_loop -1 时
        # 时间戳每次循环重置，导致永不终止（ffmpeg 卡死）。
        ff.run(["-stream_loop", "-1", "-i", str(src),
                "-an", "-vf", vf, "-t", f"{seconds}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dst)])


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


# 单次出图最多带几张参考图：多张应是「同一产品的不同角度」(正面/侧面/背面/logo特写)。
# 太多会撑大请求体且并不会更准，2-4 张通常最佳。
MAX_PRODUCT_IMAGES = 6


def _product_images(cfg: TaskConfig) -> list[str]:
    """brief.product_images：用户真实商品图（对所有分镜生效，保证推销的是真实那款货）。

    路径可写绝对路径、相对仓库根、或 media/refs 下的文件名；最多取 MAX_PRODUCT_IMAGES 张。
    """
    raw = cfg.get("brief", "product_images", default=None)
    if not raw:
        return []
    if isinstance(raw, str):
        raw = [raw]
    out: list[str] = []
    for name in raw:
        p = Path(str(name))
        cands = [p] if p.is_absolute() else [REPO_ROOT / name, _refs_dir() / name]
        for c in cands:
            if c.exists():
                out.append(str(c))
                break
    if len(out) > MAX_PRODUCT_IMAGES:
        _log(f"  商品参考图 {len(out)} 张超过上限，只取前 {MAX_PRODUCT_IMAGES} 张")
        out = out[:MAX_PRODUCT_IMAGES]
    return out


def _resolve_refs(scene: Scene, product_images: list[str] | None = None) -> list[str]:
    """优先级：分镜指定 ref_images > brief.product_images（真实商品图）> media/refs 兜底。"""
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
    if product_images:
        return product_images
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
                timeout: float = 600, interval: float = 10,
                on_poll: Callable[[int], None] | None = None) -> str:
    base = secrets.wuyin_base_url.rstrip("/")
    url = f"{base}/api/async/detail"
    headers = {"Authorization": secrets.wuyin_api_key, "Content-Type": "application/json"}
    deadline = time.time() + timeout
    polls = 0
    while time.time() < deadline:
        time.sleep(interval)
        polls += 1
        r = requests.get(url, params={"key": secrets.wuyin_api_key, "id": task_id},
                         headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json().get("data") or {}
        status = data.get("status")
        if on_poll:
            on_poll(polls)
        if status == 2:
            results = data.get("result") or []
            if results:
                return results[0]
            raise RuntimeError(f"wuyinkeji 成功但无结果: {data}")
        if status == 3:
            raise RuntimeError(f"wuyinkeji 视频生成失败: {data.get('message')}")
    raise RuntimeError("wuyinkeji 轮询超时")


def _animate_scene(s: Scene, image_url: str, want: int, w: int, h: int,
                   secrets: Secrets, n: int, tries: int = 3,
                   prompt_suffix: str = "") -> str:
    """提交无垠视频生成；失败自动重试。返回视频 URL（全部失败则抛错）。

    两类失败区别处理：
    - 安全过滤/内容类失败：换更安全的 prompt（软化）再试，重试同一个没意义；
    - 瞬时类失败（无可用通道/超时/限流/网络/5xx）：保持同一 prompt，退避后原样重试。

    有首帧图时走图生视频（image_url 非空）；首帧出图失败时退化为文生视频，
    此时把画面描述拼进 prompt，让 Veo 没有首帧也能生成真实工厂镜头。

    prompt_suffix：传入真实商品图时追加"运镜中商品保持一致不变形"约束。
    """
    base = s.mov_prompt if image_url else f"{s.img_prompt}. {s.mov_prompt}".strip()
    if prompt_suffix:
        base = f"{base}{prompt_suffix}"
    variants = [
        (base, "原始运镜"),
        (_soften_prompt(base, 1), "软化运镜(去敏感词)"),
        (_soften_prompt(base, 2), "通用安全推近"),
    ]
    tries = max(1, tries)
    last_exc: Exception | None = None
    for prompt, label in variants:
        for attempt in range(1, tries + 1):
            try:
                task_id = _wuyin_submit(prompt, image_url, w, h, want, secrets)
                _log(f"  [视频 {s.index + 1}/{n}] 已提交（{label}，第{attempt}/{tries}次），轮询中…")
                return _wuyin_poll(
                    task_id, secrets,
                    on_poll=lambda p: _log(f"  [视频 {s.index + 1}/{n}] 渲染中…(第 {p} 次轮询)"),
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                transient = _is_transient(exc)
                if transient and attempt < tries:
                    delay = min(30, 5 * attempt)
                    _log(f"  [视频 {s.index + 1}/{n}] {label} 瞬时失败：{exc} —— {delay}s 后原样重试")
                    time.sleep(delay)
                    continue
                kind = "瞬时" if transient else "内容/安全"
                _log(f"  [视频 {s.index + 1}/{n}] {label} {kind}失败：{exc}")
                break  # 换下一个更安全的 prompt 变体
    raise RuntimeError(str(last_exc))


def _gen_wuyinkeji_all(script: Script, cfg: TaskConfig, secrets: Secrets,
                       workdir: Path, w: int, h: int, fps: int) -> list[Path]:
    """每个分镜一个 worker：gpt-image-2 出图 -> 无垠图生视频 -> 抹角标 -> 定长。

    所有分镜并发跑（A 镜出视频的同时 B 镜还能在出图）。单镜被安全过滤拒绝会自动软化重试，
    仍失败则回退静帧推近，绝不让一个分镜拖垮整条流水线。
    """
    if not secrets.grsai_api_key:
        raise RuntimeError("wuyinkeji 链路需要 GRSAI_API_KEY（先用 gpt-image-2 出图）")
    if not secrets.wuyin_api_key:
        raise RuntimeError("wuyinkeji 链路需要 WUYIN_API_KEY")
    strip_wm = bool(cfg.get("decorate", "strip_ai_watermark", default=True))
    vid_seconds = int(cfg.get("clipgen", "video_seconds", default=10))
    vid_tries = max(1, int(cfg.get("clipgen", "video_retries", default=3)))
    img_tries = max(1, int(cfg.get("clipgen", "image_retries", default=2)))
    product_imgs = _product_images(cfg)
    keep_product = bool(cfg.get("clipgen", "preserve_product", default=True))
    mov_suffix = (
        " Keep the product perfectly consistent and rigid throughout the motion: do NOT morph, "
        "warp, melt, reshape or change its color/logo/proportions — only the camera, light and "
        "surroundings move."
    ) if (product_imgs and keep_product) else ""
    if product_imgs:
        _log(f"  使用真实商品图（{len(product_imgs)} 张）做图生图，强约束商品 1:1 不变形")
    img_dir = workdir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    scenes = script.scenes
    n = len(scenes)
    concurrency = int(cfg.get("clipgen", "concurrency", default=0)) or n
    concurrency = max(1, min(concurrency, n, 6))

    def _one(s: Scene) -> tuple[int, Path]:
        img_path = img_dir / f"scene_{s.index:02d}.png"
        dst = workdir / f"scene_{s.index:02d}.mp4"
        # --resume：该分镜已生成过就直接复用，省掉重复出图/出视频的钱和时间
        if dst.exists() and dst.stat().st_size > 4096:
            _log(f"  [视频 {s.index + 1}/{n}] 复用已生成片段 -> {dst.name}")
            return s.index, dst
        img: imagegen.ImageResult | None = None
        for attempt in range(1, img_tries + 1):
            try:
                _log(f"  [图 {s.index + 1}/{n}] gpt-image-2 出图中…"
                     f"（show_face={s.show_face}，第{attempt}/{img_tries}次）")
                img = imagegen.generate_image(
                    s.img_prompt, img_path, secrets, width=w, height=h,
                    ref_images=_resolve_refs(s, product_imgs),
                    avoid_frontal_face=not s.show_face, preserve_product=keep_product,
                    progress=lambda p: _log(f"  [图 {s.index + 1}/{n}] 出图 {p}"))
                _log(f"  [图 {s.index + 1}/{n}] 出图完成 -> 进入图生视频")
                break
            except Exception as exc:  # noqa: BLE001
                _log(f"  [图 {s.index + 1}/{n}] 出图失败（第{attempt}/{img_tries}次）：{exc}")
                if attempt < img_tries:
                    time.sleep(min(15, 3 * attempt))
        image_url = img.url if img else ""
        if not image_url:
            _log(f"  [图 {s.index + 1}/{n}] 出图最终失败，改用文生视频（无首帧）兜底")
        want = max(vid_seconds, int(math.ceil(s.seconds)))
        try:
            video_url = _animate_scene(s, image_url, want, w, h, secrets, n,
                                       tries=vid_tries, prompt_suffix=mov_suffix)
            raw = workdir / f"raw_{s.index:02d}.mp4"
            _download(video_url, raw)
            delogo = _wm_delogo_box(raw) if strip_wm else None
            _scale_crop(raw, dst, w, h, s.seconds, fps, delogo=delogo)
            _log(f"  [视频 {s.index + 1}/{n}] 完成 -> {dst.name}")
        except Exception as exc:  # noqa: BLE001
            _log(f"  [视频 {s.index + 1}/{n}] 生视频多次失败，回退兜底：{exc}")
            if img is not None:
                _kenburns(img.path, dst, w, h, s.seconds, fps)
            else:
                _slate(dst, w, h, s.seconds, fps)
            _log(f"  [视频 {s.index + 1}/{n}] 兜底完成 -> {dst.name}")
        return s.index, dst

    _log(f"  并发出图/出视频：{n} 个分镜，并发度={concurrency}")
    results: dict[int, Path] = {}
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(_one, s) for s in scenes]
        for f in as_completed(futs):
            idx, dst = f.result()
            results[idx] = dst
    return [results[s.index] for s in scenes]


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
