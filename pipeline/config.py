"""配置加载：合并 YAML 任务配置 + .env 里的密钥。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default) or default


@dataclass
class Secrets:
    """来自 .env 的密钥/连接信息（不进版本库）。"""

    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    clipgen_provider: str = "local"
    clipgen_api_key: str = ""
    clipgen_base_url: str = ""
    clipgen_model: str = ""

    tts_provider: str = "edge"
    tts_voice: str = "en-US-AriaNeural"
    tts_api_key: str = ""
    tts_base_url: str = ""
    azure_tts_region: str = ""

    tiktok_access_token: str = ""
    tiktok_open_id: str = ""

    fb_page_id: str = ""
    fb_page_access_token: str = ""
    fb_api_version: str = "v21.0"

    @classmethod
    def load(cls, env_file: str | os.PathLike[str] | None = None) -> "Secrets":
        load_dotenv(env_file or (REPO_ROOT / ".env"), override=False)
        return cls(
            llm_api_key=_env("LLM_API_KEY"),
            llm_base_url=_env("LLM_BASE_URL", "https://api.openai.com/v1"),
            llm_model=_env("LLM_MODEL", "gpt-4o-mini"),
            clipgen_provider=_env("CLIPGEN_PROVIDER", "local"),
            clipgen_api_key=_env("CLIPGEN_API_KEY"),
            clipgen_base_url=_env("CLIPGEN_BASE_URL"),
            clipgen_model=_env("CLIPGEN_MODEL"),
            tts_provider=_env("TTS_PROVIDER", "edge"),
            tts_voice=_env("TTS_VOICE", "en-US-AriaNeural"),
            tts_api_key=_env("TTS_API_KEY"),
            tts_base_url=_env("TTS_BASE_URL"),
            azure_tts_region=_env("AZURE_TTS_REGION"),
            tiktok_access_token=_env("TIKTOK_ACCESS_TOKEN"),
            tiktok_open_id=_env("TIKTOK_OPEN_ID"),
            fb_page_id=_env("FB_PAGE_ID"),
            fb_page_access_token=_env("FB_PAGE_ACCESS_TOKEN"),
            fb_api_version=_env("FB_API_VERSION", "v21.0"),
        )


@dataclass
class TaskConfig:
    """来自 YAML 的单次任务配置。"""

    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "TaskConfig":
        with open(path, "r", encoding="utf-8") as f:
            return cls(raw=yaml.safe_load(f) or {})

    def get(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.raw
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    # 常用快捷访问
    @property
    def project(self) -> str:
        return self.get("project", default="demo")

    @property
    def template(self) -> str:
        return self.get("template", default="product")

    @property
    def language(self) -> str:
        return self.get("language", default="en")

    @property
    def width(self) -> int:
        return int(self.get("video", "width", default=1080))

    @property
    def height(self) -> int:
        return int(self.get("video", "height", default=1920))

    @property
    def fps(self) -> int:
        return int(self.get("video", "fps", default=30))

    @property
    def target_seconds(self) -> int:
        return int(self.get("video", "target_seconds", default=24))
