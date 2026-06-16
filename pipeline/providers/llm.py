"""文案/分镜脚本生成。

有 LLM_API_KEY 时调用 OpenAI 兼容接口；没有时用内置模板，保证流水线可跑通。
"""

from __future__ import annotations

import json

from ..config import REPO_ROOT, Secrets, TaskConfig
from ..script_model import Scene, Script

_SYSTEM = """You are a senior short-video director + creative director + buyer-persona
expert for TikTok / Facebook performance ads. You write tight, hook-first, pain-point
driven scripts that match native platform formats.

Return STRICT JSON only, matching this schema:
{
  "hook": "first 3s on-screen text (scroll-stopper)",
  "cta": "final call to action",
  "scenes": [
    {"index": 0, "visual_prompt": "what to show (for AI video gen)",
     "narration": "spoken voiceover line", "on_screen_text": "big caption", "seconds": 5}
  ]
}
No markdown, no commentary."""


def _persona_prompt(template: str) -> str:
    fname = "factory_persona.md" if template == "factory" else "product_persona.md"
    p = REPO_ROOT / "prompts" / fname
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _user_prompt(cfg: TaskConfig) -> str:
    brief = cfg.get("brief", default={}) or {}
    n = int(cfg.get("clipgen", "scene_count", default=5))
    return (
        f"Persona & format guide:\n{_persona_prompt(cfg.template)}\n\n"
        f"Template: {cfg.template}\nLanguage: {cfg.language}\n"
        f"Target total length: ~{cfg.target_seconds}s across {n} scenes.\n"
        f"Brief (JSON):\n{json.dumps(brief, ensure_ascii=False)}\n\n"
        f"Write the script as JSON with exactly {n} scenes."
    )


def _template_fallback(cfg: TaskConfig) -> Script:
    """无 LLM key 时的确定性模板脚本（仍然遵循爆款结构）。"""
    brief = cfg.get("brief", default={}) or {}
    name = brief.get("product_name", "this product")
    sps = brief.get("selling_points", []) or ["it just works", "great value", "loved by users"]
    cta = brief.get("cta", "Tap the link 🔗")
    sps = (sps + sps)[:3]

    if cfg.template == "factory":
        scenes = [
            Scene(0, "sweeping overhead shot of a busy production floor",
                  f"This is what a real {name} factory looks like.",
                  f"Inside a REAL {name} factory 🏭", 5),
            Scene(1, "multiple production lines, machines running, workers",
                  "Multiple production lines running at full capacity every day.",
                  "Massive monthly capacity", 5),
            Scene(2, "close-up of QC inspection, raw materials, certificates",
                  "Every unit is quality-checked, with full certifications.",
                  "Strict QC · CE / ISO", 5),
            Scene(3, "person presenting, packaging and customization samples",
                  "Low MOQ, OEM and ODM, custom packaging — we make it for you.",
                  "Low MOQ · OEM / ODM", 5),
            Scene(4, "warehouse full of stock, container loading, shipping",
                  "Trusted by buyers worldwide. Send us your inquiry today.",
                  cta, 4),
        ]
        hook = f"Inside a REAL {name} factory 🏭"
    else:
        scenes = [
            Scene(0, f"a relatable everyday pain moment related to {name}",
                  "If you struggle with this every day, watch this.",
                  "POV: this annoys you daily 😩", 4),
            Scene(1, "agitate the problem, show the frustrating moment bigger",
                  "It is frustrating, messy, and wastes your time.",
                  "The problem 👇", 5),
            Scene(2, f"{name} in use, multiple angles, before vs after",
                  f"Then I found {name}. {sps[0]}.",
                  f"{name}", 6),
            Scene(3, "proof: results, comparison, reviews on screen",
                  f"{sps[1]}, and {sps[2]}.",
                  "10k+ sold ⭐⭐⭐⭐⭐", 5),
            Scene(4, "product hero shot with offer",
                  "Get yours now before the offer ends.",
                  cta, 4),
        ]
        hook = "POV: this annoys you daily 😩"

    return Script(template=cfg.template, language=cfg.language, hook=hook, cta=cta, scenes=scenes)


def generate_script(cfg: TaskConfig, secrets: Secrets) -> Script:
    if not secrets.llm_api_key:
        return _template_fallback(cfg)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=secrets.llm_api_key, base_url=secrets.llm_base_url or None)
        resp = client.chat.completions.create(
            model=secrets.llm_model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _user_prompt(cfg)},
            ],
            temperature=0.8,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        data.setdefault("template", cfg.template)
        data.setdefault("language", cfg.language)
        for i, s in enumerate(data.get("scenes", [])):
            s.setdefault("index", i)
        return Script.from_dict(data)
    except Exception as exc:  # noqa: BLE001 - 兜底到模板，保证流水线不中断
        print(f"[llm] 调用失败，回退到模板脚本: {exc}")
        return _template_fallback(cfg)
