"""分镜脚本数据结构（脚本生成 -> 片段生成 / 配音 / 字幕 共用）。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass
class Scene:
    index: int
    visual_prompt: str          # 喂给 AI 片段生成 / 或用于挑本地素材的描述
    narration: str              # 这段口播文案（用于配音 + 字幕）
    on_screen_text: str = ""    # 屏幕大字（钩子/卖点/CTA）
    seconds: float = 5.0


@dataclass
class Script:
    template: str               # factory | product
    language: str
    hook: str                   # 前 3 秒钩子（覆盖 scene[0].on_screen_text）
    cta: str
    scenes: list[Scene] = field(default_factory=list)

    @property
    def full_narration(self) -> str:
        return " ".join(s.narration.strip() for s in self.scenes if s.narration.strip())

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "Script":
        scenes = [Scene(**s) for s in d.get("scenes", [])]
        return cls(
            template=d.get("template", "product"),
            language=d.get("language", "en"),
            hook=d.get("hook", ""),
            cta=d.get("cta", ""),
            scenes=scenes,
        )
