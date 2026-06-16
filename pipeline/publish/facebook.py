"""Facebook 发布：Graph API 上传视频到 Page（含 Reels 形式）。

前置：拿到 Page access token（需 pages_manage_posts / publish_video 权限），
填到 .env 的 FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN。
文档：https://developers.facebook.com/docs/video-api / Reels API
"""

from __future__ import annotations

from pathlib import Path

import requests


def publish_feed_video(video: Path, caption: str, page_id: str, token: str, api: str = "v21.0") -> dict:
    """普通 Page 视频（Feed）。简单 multipart 上传，适合中小文件。"""
    if not (page_id and token):
        raise RuntimeError("缺少 FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN")
    url = f"https://graph-video.facebook.com/{api}/{page_id}/videos"
    with open(video, "rb") as f:
        r = requests.post(
            url,
            data={"description": caption, "access_token": token},
            files={"source": f},
            timeout=600,
        )
    r.raise_for_status()
    return r.json()


def publish_reel(video: Path, caption: str, page_id: str, token: str, api: str = "v21.0") -> dict:
    """Reels API：start -> upload -> finish。"""
    if not (page_id and token):
        raise RuntimeError("缺少 FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN")
    base = f"https://graph.facebook.com/{api}/{page_id}/video_reels"
    start = requests.post(
        base, data={"upload_phase": "start", "access_token": token}, timeout=60
    )
    start.raise_for_status()
    sd = start.json()
    video_id = sd["video_id"]
    upload_url = sd["upload_url"]

    file_size = video.stat().st_size
    with open(video, "rb") as f:
        up = requests.post(
            upload_url,
            headers={
                "Authorization": f"OAuth {token}",
                "offset": "0",
                "file_size": str(file_size),
            },
            data=f.read(),
            timeout=600,
        )
    up.raise_for_status()

    finish = requests.post(
        base,
        data={
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "description": caption,
            "access_token": token,
        },
        timeout=120,
    )
    finish.raise_for_status()
    return {"video_id": video_id, "finish": finish.json()}


def publish(video: Path, caption: str, page_id: str, token: str, api: str = "v21.0", reel: bool = True) -> dict:
    fn = publish_reel if reel else publish_feed_video
    return fn(video, caption, page_id, token, api)
