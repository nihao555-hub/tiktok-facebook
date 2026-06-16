"""文案/分镜脚本生成。

有 LLM_API_KEY 时调用 OpenAI 兼容接口；没有时用内置模板，保证流水线可跑通。
"""

from __future__ import annotations

import json
import re
import time

from ..config import REPO_ROOT, Secrets, TaskConfig
from ..script_model import Scene, Script

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}

_SYSTEM = """You are a senior short-video director + creative director + buyer-persona
expert for TikTok / Facebook performance ads. You write tight, hook-first, pain-point
driven scripts that match native platform formats.

The visuals are produced by: (1) gpt-image-2 makes ONE photorealistic still per scene
from the brand's REAL reference photos, then (2) a video model animates that still.
So every scene needs an image_prompt (the still) and a motion_prompt (how it moves).

Hard rules for image_prompt:
- Describe a single REAL-LOOKING photograph: shot on a phone, natural light, true colors,
  candid, real-world textures. NEVER say illustration / 3D / render / cartoon / poster.
- The brand's actual product or factory (from the reference photos) MUST appear and stay
  consistent. No on-image text, no watermark, no logo overlay.
Hard rules for motion_prompt:
- Subtle, realistic camera or subject motion for a 5-10s clip
  (slow push-in, hand picks up the product, pan across the line, parallax). Keep it natural.

Creative freedom (IMPORTANT): you are the director — be original and avoid homogenized,
templated ad copy. Pick whatever hook angle fits THIS product/audience best (POV, bold
question, shocking number, before/after, mini-story, myth-busting, "things I wish I knew").
Vary pacing, scene ideas and wording every time. It must feel like a native organic clip a
real creator posted, NOT a polished commercial. Do not say the word "ad".

Return STRICT JSON only, matching this schema:
{
  "hook": "first 3s on-screen text (scroll-stopper)",
  "cta": "final call to action",
  "scenes": [
    {"index": 0,
     "image_prompt": "one photorealistic still to generate",
     "motion_prompt": "subtle camera/subject motion for the clip",
     "narration": "spoken voiceover line",
     "on_screen_text": "big caption",
     "ref_images": ["file names from the provided reference list, or omit"],
     "seconds": 5}
  ]
}
No markdown, no commentary."""


_LANG_NAMES = {
    "th": "Thai (ภาษาไทย)",
    "en": "English",
    "zh": "Chinese",
    "id": "Indonesian",
    "vi": "Vietnamese",
    "ms": "Malay",
}


def _lang_directive(cfg: TaskConfig) -> str:
    code = (cfg.language or "en").strip().lower()
    name = _LANG_NAMES.get(code[:2], cfg.language or "English")
    out = (
        f"LANGUAGE: Write hook, cta, narration and on_screen_text in {name}. "
        "Keep image_prompt and motion_prompt in ENGLISH — they are technical prompts that "
        "drive the image/video models, not shown to viewers."
    )
    if code.startswith("th"):
        out += (
            " Localize FULLY for a Thai audience: write natural spoken Thai (never "
            "translated-sounding), casual TikTok/Reels tone with local particles "
            "(นะ/เลย/อ่ะ/จัดไป/ดีงาม), Thai cultural context (Thai people, homes, street "
            "food, weather, prices in ฿), and the way Thai creators actually hook viewers in "
            "viral product videos. Keep on_screen_text short (a few words) so it fits one line."
        )
    return out


def _persona_prompt(template: str) -> str:
    fname = "factory_persona.md" if template == "factory" else "product_persona.md"
    p = REPO_ROOT / "prompts" / fname
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _available_refs() -> list[str]:
    d = REPO_ROOT / "media" / "refs"
    if not d.exists():
        return []
    return sorted(p.name for p in d.iterdir() if p.suffix.lower() in _IMAGE_EXT)


def _user_prompt(cfg: TaskConfig) -> str:
    brief = cfg.get("brief", default={}) or {}
    n = int(cfg.get("clipgen", "scene_count", default=5))
    refs = _available_refs()
    refs_line = (
        f"Reference photos available (assign relevant ones per scene via ref_images): {refs}\n"
        if refs else
        "No reference photos provided yet; write image_prompt to stand alone.\n"
    )
    return (
        f"Persona & format guide:\n{_persona_prompt(cfg.template)}\n\n"
        f"Template: {cfg.template}\n{_lang_directive(cfg)}\n"
        f"Target total length: ~{cfg.target_seconds}s across {n} scenes.\n"
        f"{refs_line}"
        f"Brief (JSON):\n{json.dumps(brief, ensure_ascii=False)}\n\n"
        f"Write the script as JSON with exactly {n} scenes."
    )


def _parse_json(content: str) -> dict:
    """容错解析：去 markdown 围栏，抽取第一个 JSON 对象。"""
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


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


def _call_llm(cfg: TaskConfig, secrets: Secrets, retries: int = 3) -> Script:
    from openai import OpenAI

    client = OpenAI(
        api_key=secrets.llm_api_key, base_url=secrets.llm_base_url or None, timeout=120.0
    )
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _user_prompt(cfg)},
    ]
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            try:
                resp = client.chat.completions.create(
                    model=secrets.llm_model, messages=messages, temperature=0.9,
                    response_format={"type": "json_object"},
                )
            except Exception:  # noqa: BLE001 - 部分兼容端不支持 response_format
                resp = client.chat.completions.create(
                    model=secrets.llm_model, messages=messages, temperature=0.9,
                )
            data = _parse_json(resp.choices[0].message.content or "{}")
            if not data.get("scenes"):
                raise ValueError("LLM 未返回 scenes")
            data.setdefault("template", cfg.template)
            data.setdefault("language", cfg.language)
            return Script.from_dict(data)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            print(f"[llm] 第 {attempt}/{retries} 次调用失败: {exc}")
            if attempt < retries:
                time.sleep(2 * attempt)
    raise RuntimeError(f"LLM 连续 {retries} 次调用失败") from last_exc


def generate_script(cfg: TaskConfig, secrets: Secrets) -> Script:
    if not secrets.llm_api_key:
        return _template_fallback(cfg)
    return _call_llm(cfg, secrets)
