"""文生图 / 图生图：grsai gpt-image-2。

强约束输出"100% 真实世界质感、看不出 AI"；支持传入用户真实商品/工厂图做图生图，
保证画面里的商品/工厂与用户素材一致。
"""
from __future__ import annotations

import base64
import mimetypes
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import requests

from ..config import REPO_ROOT, Secrets

# 真实感强约束（拼接到每条 prompt 末尾）
REALISM_SUFFIX = (
    ", ultra realistic photograph, shot on smartphone, natural lighting, real-world textures, "
    "candid photojournalistic look, true-to-life colors, high detail, photographic depth of field. "
    "Absolutely no text, no watermark, no logo overlay, no captions. "
    "Not an illustration, not a 3D render, not CGI, not cartoon — looks like a real photo."
)

# 默认不出人正脸（也能显著降低视频模型的安全过滤误杀）
NO_FACE_SUFFIX = (
    " Do NOT show any person's full frontal face: keep people turned away from camera "
    "(back of head, over-the-shoulder, side profile), or show only hands / torso / lower body, "
    "or frame so the face is out of shot. No identifiable face looking at the camera."
)


@dataclass
class ImageResult:
    path: Path
    url: str  # grsai 托管地址（约 2 小时有效，可直接喂给视频生成）


def _aspect_for(width: int, height: int) -> str:
    if width < height:
        return "1024x1536"
    if width > height:
        return "1536x1024"
    return "1024x1024"


def _encode_ref(ref: str) -> str | None:
    """本地图片转 base64 data URI；http(s) 直接返回。"""
    if ref.startswith("http://") or ref.startswith("https://"):
        return ref
    p = Path(ref)
    if not p.is_absolute():
        p = REPO_ROOT / ref
    if not p.exists():
        return None
    mime = mimetypes.guess_type(str(p))[0] or "image/png"
    data = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


def _poll(base: str, headers: dict[str, str], task_id: str,
          timeout: float = 600, interval: float = 6,
          progress: Callable[[str], None] | None = None) -> str:
    deadline = time.time() + timeout
    last_pct = -1
    while time.time() < deadline:
        time.sleep(interval)
        r = requests.post(f"{base}/v1/draw/result", json={"id": task_id},
                          headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json().get("data") or {}
        status = data.get("status")
        if progress and status == "running":
            pct = int(data.get("progress") or 0)
            if pct != last_pct:
                progress(f"{pct}%")
                last_pct = pct
        if status == "succeeded":
            results = data.get("results") or []
            if results and results[0].get("url"):
                return results[0]["url"]
            if data.get("url"):
                return data["url"]
            raise RuntimeError("gpt-image-2 成功但未返回图片 URL")
        if status == "failed":
            raise RuntimeError(
                f"gpt-image-2 生成失败: {data.get('failure_reason')} {data.get('error')}")
    raise RuntimeError("gpt-image-2 轮询超时")


def _download(url: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=180) as r:
        r.raise_for_status()
        with open(dst, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)


def generate_image(
    prompt: str,
    out_path: Path,
    secrets: Secrets,
    *,
    width: int = 1024,
    height: int = 1024,
    ref_images: list[str] | None = None,
    realism: bool = True,
    avoid_frontal_face: bool = True,
    progress: Callable[[str], None] | None = None,
) -> ImageResult:
    """生成一张图片并下载到本地，返回本地路径 + grsai 托管 URL。

    avoid_frontal_face=True 时追加"不出正脸"约束（show_face 的分镜应传 False）。
    """
    if not secrets.grsai_api_key:
        raise RuntimeError("缺少 GRSAI_API_KEY（gpt-image-2）")
    base = secrets.grsai_base_url.rstrip("/")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {secrets.grsai_api_key}",
    }
    urls: list[str] = []
    for ref in ref_images or []:
        enc = _encode_ref(ref)
        if enc:
            urls.append(enc)

    full_prompt = prompt
    if avoid_frontal_face:
        full_prompt += NO_FACE_SUFFIX
    if realism:
        full_prompt += REALISM_SUFFIX
    payload: dict = {
        "model": secrets.image_model,
        "prompt": full_prompt,
        "aspectRatio": _aspect_for(width, height),
        "quality": "high",
        "webHook": "-1",
        "shutProgress": True,
    }
    if urls:
        payload["urls"] = urls

    resp = requests.post(f"{base}/v1/draw/completions", json=payload,
                         headers=headers, timeout=60)
    resp.raise_for_status()
    body = resp.json()
    task_id = (body.get("data") or {}).get("id")
    if not task_id:
        raise RuntimeError(f"gpt-image-2 提交失败: {body}")
    remote_url = _poll(base, headers, task_id, progress=progress)
    _download(remote_url, out_path)
    return ImageResult(path=out_path, url=remote_url)
