"""TikTok 发布：Content Posting API (Direct Post, FILE_UPLOAD)。

前置：在 TikTok for Developers 创建应用，拿到带 video.publish / video.upload
权限的 user access token，填到 .env 的 TIKTOK_ACCESS_TOKEN。
文档：https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
"""

from __future__ import annotations

import os
from pathlib import Path

import requests

_BASE = "https://open.tiktokapis.com/v2"
_CHUNK = 10 * 1024 * 1024  # 10MB


def publish(video: Path, caption: str, access_token: str) -> dict:
    if not access_token:
        raise RuntimeError("缺少 TIKTOK_ACCESS_TOKEN")
    size = os.path.getsize(video)
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    init = requests.post(
        f"{_BASE}/post/publish/video/init/",
        headers=headers,
        json={
            "post_info": {
                "title": caption[:2200],
                "privacy_level": "SELF_ONLY",  # 先草稿/自见，确认无误再改 PUBLIC_TO_EVERYONE
                "disable_comment": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": min(_CHUNK, size),
                "total_chunk_count": max(1, -(-size // _CHUNK)),
            },
        },
        timeout=60,
    )
    init.raise_for_status()
    data = init.json()["data"]
    upload_url = data["upload_url"]
    publish_id = data["publish_id"]

    with open(video, "rb") as f:
        body = f.read()
    put = requests.put(
        upload_url,
        headers={"Content-Type": "video/mp4", "Content-Range": f"bytes 0-{size - 1}/{size}"},
        data=body,
        timeout=600,
    )
    put.raise_for_status()
    return {"publish_id": publish_id}


def status(publish_id: str, access_token: str) -> dict:
    r = requests.post(
        f"{_BASE}/post/publish/status/fetch/",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={"publish_id": publish_id},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()
