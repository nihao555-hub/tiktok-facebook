"""分镜脚本数据结构（脚本生成 -> 片段生成 / 配音 / 字幕 共用）。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from dataclasses import fields as dataclass_fields


@dataclass
class Scene:
    index: int = 0
    visual_prompt: str = ""     # 画面描述（无 image/motion 时回退用它）
    narration: str = ""         # 这段口播文案（主语言/泰语，用于配音 + 主字幕）
    narration_zh: str = ""      # 同句中文翻译（中泰双语时作辅助小字幕；不配音）
    on_screen_text: str = ""    # 屏幕大字（钩子/卖点/CTA）
    seconds: float = 5.0
    image_prompt: str = ""      # 喂 gpt-image-2 的静帧提示（超写实）
    motion_prompt: str = ""     # 喂视频生成的运镜/动作提示
    ref_images: list[str] = field(default_factory=list)  # 该分镜要用的真实素材文件名(media/refs/)
    show_face: bool = False     # 默认不出人正脸；仅在提示词确需正脸时由 LLM 置 True

    @property
    def img_prompt(self) -> str:
        return self.image_prompt or self.visual_prompt

    @property
    def mov_prompt(self) -> str:
        return self.motion_prompt or self.visual_prompt


@dataclass
class Script:
    template: str               # factory | product
    language: str
    hook: str                   # 前 3 秒钩子（覆盖 scene[0].on_screen_text）
    cta: str
    scenes: list[Scene] = field(default_factory=list)
    template_used: str = ""     # 本条采用的爆款结构 id（见 pipeline/templates.py）

    @property
    def full_narration(self) -> str:
        return " ".join(s.narration.strip() for s in self.scenes if s.narration.strip())

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "Script":
        fields = {f.name for f in dataclass_fields(Scene)}
        scenes = []
        for i, s in enumerate(d.get("scenes", [])):
            kw = {k: v for k, v in s.items() if k in fields}
            kw.setdefault("index", i)
            scenes.append(Scene(**kw))
        return cls(
            template=d.get("template", "product"),
            language=d.get("language", "en"),
            hook=d.get("hook", ""),
            cta=d.get("cta", ""),
            scenes=scenes,
            template_used=d.get("template_used", ""),
        )
