"""文案/分镜脚本生成。

有 LLM_API_KEY 时调用 OpenAI 兼容接口；没有时用内置模板，保证流水线可跑通。
"""

from __future__ import annotations

import json
import re
import time

from .. import brand, templates
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
- FACES: by default DO NOT show any person's full frontal face. Frame people from behind,
  over-the-shoulder, side profile, or show only their hands / torso / lower body. Set
  "show_face": false on these scenes. Only when a real human face is truly essential
  (e.g. the founder talking straight to camera) set "show_face": true AND describe that
  frontal face explicitly in the image_prompt.
Hard rules for motion_prompt:
- Subtle, realistic camera or subject motion for a 5-10s clip
  (slow push-in, hand picks up the product, pan across the line, parallax). Keep it natural.
- Keep it brand-safe: calm, ordinary, professional actions only. No violence, no danger,
  no blades cutting toward people, nothing a video model's safety filter would reject.

Creative freedom (IMPORTANT): you are the director — be original and avoid homogenized,
templated ad copy. Pick whatever hook angle fits THIS product/audience best (POV, bold
question, shocking number, before/after, mini-story, myth-busting, "things I wish I knew").
Vary pacing, scene ideas and wording every time. It must feel like a native organic clip a
real creator posted, NOT a polished commercial. Do not say the word "ad".

STRUCTURE (IMPORTANT): you will be given a library of proven viral structures (or one
pinned structure). Build the scenes so they FOLLOW the chosen structure's beats in order,
but improvise the wording, hook angle and shots freely inside it — never canned lines.
Return the id of the structure you used in "template_used".

DIFFERENTIATION (IMPORTANT): you may be given this factory's persistent BRAND SIGNATURE and a
list of hook angles / structures already used. Keep the brand signature consistent (so the
factory is recognizable) but make THIS video clearly different from the recent ones — rotate
to a fresh hook category and a fresh opening shot. Report the hook category you used in
"hook_category" (one of: curiosity_gap, contrarian, transformation, pov_identity,
direct_question, stat_shock).

Return STRICT JSON only, matching this schema:
{
  "hook": "first 3s on-screen text (scroll-stopper)",
  "cta": "final call to action",
  "template_used": "the viral structure id you followed",
  "hook_category": "the hook-bank category id this video's opening uses",
  "scenes": [
    {"index": 0,
     "image_prompt": "one photorealistic still to generate",
     "motion_prompt": "subtle camera/subject motion for the clip",
     "narration": "spoken voiceover line (in the target language)",
     "narration_zh": "an accurate, natural Simplified-Chinese translation of THIS narration",
     "on_screen_text": "big caption",
     "ref_images": ["file names from the provided reference list, or omit"],
     "show_face": false,
     "seconds": 5}
  ]
}
narration_zh is REQUIRED on every scene: it must be a faithful, fluent Chinese
translation of that scene's narration (used for a Chinese helper subtitle line). Do not
leave it empty and do not just transliterate.
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


def _focus_directive(cfg: TaskConfig) -> str:
    """工厂(B2B)片的硬性聚焦：每个分镜都要是工厂真实作业镜头、集中宣传工厂业务实力。"""
    if cfg.template != "factory":
        return ""
    return (
        "FACTORY FOCUS (HARD REQUIREMENT): This is a factory-showcase B2B video whose ONLY job is "
        "to present and sell the factory's MANUFACTURING BUSINESS to sourcing buyers. EVERY single "
        "scene must show a concrete, REAL factory operation in action — e.g. raw material / loading, "
        "the core process machine actually running on the product, the production line, in-process & "
        "final QC/inspection, packing, warehouse stock, container loading / shipping. Show the WORK and "
        "the PRODUCTS being made, on the real shop floor. NO lifestyle/home/street scenes, NO abstract or "
        "decorative shots, NO talking-head-only scenes. image_prompt must name the specific workstation, "
        "machine and product so the buyer sees genuine production capability and wants to source / partner. "
        "Match the structure/pace of viral factory-tour clips on TikTok/Facebook in this niche.\n"
        "PROVE THE OUTPUT (HARD REQUIREMENT): the buyer only DMs when they SEE how good the result is, so "
        "most scenes must be (a) tight CLOSE-UPS of the core process actually happening on the product "
        "(the tool/beam/machine working on the material, in macro detail) and (b) HERO close-ups of the "
        "FINISHED products — show the sharpness, precision, texture and finish quality, plus a wall / "
        "batch / many-SKU spread of finished pieces. Open on the single most visually impressive process "
        "or finished-result shot. Spend far less time on slogans and more on this visible 'effect evidence'. "
        "For a LASER engraving / marking factory specifically: scenes should center on the laser beam "
        "engraving/marking in macro (sparks, the mark forming line by line) across DIFFERENT materials "
        "(stainless steel, aluminum, acrylic, wood, leather) and razor-sharp close-ups of the engraved "
        "finished pieces — make a buyer think 'their quality is insane, I want to order'.\n"
        "NARRATION STYLE: write each scene's narration as ONE short, natural spoken sentence that plainly "
        "tells the sourcing buyer what they are seeing and the capability it proves (concrete, not vague "
        "slogans). Keep all scenes a similar narration length so pacing is even — never one long monologue "
        "scene and one near-empty scene.\n"
        "FIXED FREE-SAMPLE CTA (HARD REQUIREMENT — the ending NEVER changes): the FINAL scene's narration "
        "AND the script-level cta AND that scene's on_screen_text must ALL be a free-sampling lead-gen call: "
        "tell the buyer to FILL OUT THE FORM / message us with the item they want, and we will send them a "
        "FREE SAMPLE so they can check the quality and see the result in their own hands before placing any "
        "real order. Frame it as zero-risk: free sample, no upfront payment, judge the quality yourself. Do "
        "NOT end on a vague 'DM us / contact us / inquiry' — it MUST land on 'fill the form → get a free "
        "sample → see the quality for yourself'. Write it naturally in the target language, short and "
        "punchy. (decisive_trigger / cta in the strategy should reflect this free-sample offer too.)"
    )


def _persona_prompt(template: str) -> str:
    fname = "factory_persona.md" if template == "factory" else "product_persona.md"
    p = REPO_ROOT / "prompts" / fname
    return p.read_text(encoding="utf-8") if p.exists() else ""


# --------------------------------------------------------------------------
# 第 0 步：买家画像 / 策略（LLM 先当买家画像专家 + 创意总监 思考，再写脚本）
# --------------------------------------------------------------------------
_STRATEGY_SYSTEM = """You are a world-class buyer-persona researcher, creative director and
performance-marketing strategist for TikTok / Facebook video ads. Before any script exists,
you think hard about WHO we are selling to and HOW a native viral video would hook them.

Think like the buyer first, then like the director. For a FACTORY (B2B) video the buyer is an
importer / wholesaler / sourcing agent / brand owner looking for a manufacturer; for a PRODUCT
(B2C) video the buyer is an end consumer. Ground everything in the target market's real
culture, buying psychology and the way THAT platform's viral videos in this niche actually look.

Return STRICT JSON only (no markdown), matching:
{
  "market": "target market / country",
  "buyer_persona": {"who": "", "role": "", "context": "where/when they watch & decide"},
  "biggest_pain": "the #1 fear / frustration / risk that keeps them from buying",
  "desires": ["what they really want"],
  "objections": ["doubts we must neutralize on camera"],
  "decisive_trigger": "the single thing that makes them DM / click / inquire",
  "hook_angle": "the ONE strongest opening angle for this audience",
  "emotional_drivers": ["emotions to pull"],
  "proof_to_show": ["concrete on-screen proof: numbers, certs, capacity, demos, before/after"],
  "native_format_notes": "how real viral videos in this niche/market look & sound",
  "recommended_template": "the viral structure id that best fits",
  "brand_signature": {
    "signature_motif": "this factory's ONE recognizable recurring motif / through-line",
    "brand_personality": "3-5 adjectives describing the brand's on-camera personality",
    "hero_product": "the single hero product/capability to anchor the brand around",
    "unique_evidence": ["the proprietary, hard-to-copy proof that sets THIS factory apart"],
    "founder_story": "a short, human origin/why story to humanize the factory",
    "visual_motifs": ["recurring visual signatures: a color, a shot, a gesture, a sound"],
    "tagline": "a short memorable brand line"
  },
  "do_not": ["homogenized / cringe / over-polished traps to avoid"]
}
If a BRAND SIGNATURE is already provided to you, keep it CONSISTENT (you may refine but not
contradict it) and return it in brand_signature."""


def _diff_block(cfg: TaskConfig, mem: dict | None) -> str:
    """创意差异化层指令（品牌母题 + 反重复轮换）；无记忆时返回空串。"""
    if not mem:
        return ""
    text = brand.directives(cfg, mem)
    return f"{text}\n\n" if text else ""


def _strategy_user_prompt(cfg: TaskConfig, mem: dict | None = None) -> str:
    brief = cfg.get("brief", default={}) or {}
    btype = "B2B factory sourcing" if cfg.template == "factory" else "B2C product"
    focus = _focus_directive(cfg)
    focus_block = f"{focus}\n\n" if focus else ""
    return (
        f"Persona & format guide:\n{_persona_prompt(cfg.template)}\n\n"
        f"Video type: {cfg.template} ({btype}).\n"
        f"{_lang_directive(cfg)}\n\n"
        f"{focus_block}"
        f"{_diff_block(cfg, mem)}"
        f"Available viral structures (pick the best id for recommended_template):\n"
        f"{templates.menu(cfg.template)}\n\n"
        f"{templates.hook_bank()}\n\n"
        f"Brief (JSON):\n{json.dumps(brief, ensure_ascii=False)}\n\n"
        "Develop the buyer-persona & creative strategy as JSON now."
    )


def _strategy_fallback(cfg: TaskConfig) -> dict:
    is_factory = cfg.template == "factory"
    return {
        "market": cfg.language,
        "buyer_persona": {
            "who": "importer / wholesaler sourcing a manufacturer" if is_factory
            else "everyday online shopper",
            "role": "sourcing / purchasing" if is_factory else "consumer",
            "context": "scrolling TikTok/FB on a phone",
        },
        "biggest_pain": "fear of unreliable suppliers / wasted money" if is_factory
        else "a daily annoyance the product fixes",
        "desires": ["trust", "good price", "proof it works"],
        "objections": ["is this real?", "can I trust them?"],
        "decisive_trigger": "clear proof + low-friction CTA",
        "hook_angle": "direct-from-factory, no middleman" if is_factory
        else "POV of the pain then the fix",
        "emotional_drivers": ["trust", "relief", "FOMO"],
        "proof_to_show": ["capacity", "QC", "certifications", "export countries"] if is_factory
        else ["before/after", "reviews", "units sold"],
        "native_format_notes": "raw, candid, creator-style, not a polished commercial",
        "recommended_template": "factory_tour" if is_factory else "pas",
        "do_not": ["canned ad lines", "over-polished look"],
    }


def _models(secrets: Secrets) -> list[str]:
    """主模型 + 备用模型（gpt-5.5 过载时自动降级到 gemini-3.5-flash）。"""
    out = [secrets.llm_model]
    fb = (secrets.llm_model_fallback or "").strip()
    if fb and fb != secrets.llm_model:
        out.append(fb)
    return [m for m in out if m]


def _complete_json(secrets: Secrets, messages: list, temperature: float,
                   validate, tries_per_model: int = 4) -> dict:
    """调用 LLM 拿 JSON：每个模型耐心重试(退避)，主模型连续失败后自动切备用模型。

    validate(data)->bool 校验返回字段是否完整；不完整也当失败继续重试/换模型。
    所有模型都失败才抛错。
    """
    from openai import OpenAI

    client = OpenAI(
        api_key=secrets.llm_api_key, base_url=secrets.llm_base_url or None, timeout=120.0
    )
    models = _models(secrets)
    last_exc: Exception | None = None
    for mi, model in enumerate(models):
        for attempt in range(1, tries_per_model + 1):
            try:
                try:
                    resp = client.chat.completions.create(
                        model=model, messages=messages, temperature=temperature,
                        response_format={"type": "json_object"},
                    )
                except Exception:  # noqa: BLE001 - 部分兼容端不支持 response_format
                    resp = client.chat.completions.create(
                        model=model, messages=messages, temperature=temperature,
                    )
                data = _parse_json(resp.choices[0].message.content or "{}")
                if not validate(data):
                    raise ValueError("LLM 返回 JSON 不完整/缺字段")
                return data
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                print(f"[llm] 模型[{model}] 第 {attempt}/{tries_per_model} 次失败: {exc}",
                      flush=True)
                if attempt < tries_per_model:
                    time.sleep(min(30, 5 * attempt))   # 过载等瞬时错误：耐心退避重试
        if mi < len(models) - 1:
            print(f"[llm] 主模型[{model}]连续失败，自动降级到备用模型[{models[mi + 1]}]…",
                  flush=True)
    raise RuntimeError(f"LLM 所有模型({models})均调用失败") from last_exc


def generate_strategy(cfg: TaskConfig, secrets: Secrets, mem: dict | None = None) -> dict:
    """先让 LLM 当买家画像专家/创意总监想清楚策略，再用它指导写脚本。"""
    if not secrets.llm_api_key:
        return _strategy_fallback(cfg)
    messages = [
        {"role": "system", "content": _STRATEGY_SYSTEM},
        {"role": "user", "content": _strategy_user_prompt(cfg, mem)},
    ]
    try:
        return _complete_json(
            secrets, messages, 0.8,
            validate=lambda d: bool(d.get("buyer_persona") or d.get("hook_angle")),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[llm] 策略生成全部失败，回退模板策略: {exc}", flush=True)
        return _strategy_fallback(cfg)


def _available_refs() -> list[str]:
    d = REPO_ROOT / "media" / "refs"
    if not d.exists():
        return []
    return sorted(p.name for p in d.iterdir() if p.suffix.lower() in _IMAGE_EXT)


def _structure_directive(cfg: TaskConfig) -> str:
    """注入爆款结构：viral_template=auto 时给菜单让 AI 选；钉死某 id 时给详细 beats。"""
    pinned = (cfg.get("viral_template", default="auto") or "auto").strip().lower()
    if pinned and pinned != "auto" and templates.get(pinned):
        return (
            "VIRAL STRUCTURE (pinned):\n"
            f"{templates.spec(pinned)}\n"
            f'Set "template_used" to "{pinned}".'
        )
    return (
        "VIRAL STRUCTURE LIBRARY — choose the ONE structure that best fits this product/"
        "audience, then build the scenes to follow its beats (improvise wording/shots inside):\n"
        f"{templates.menu(cfg.template)}\n"
        'Pick the best-fitting id and set "template_used" to it.'
    )


def _user_prompt(cfg: TaskConfig, strategy: dict | None = None,
                 mem: dict | None = None) -> str:
    brief = cfg.get("brief", default={}) or {}
    n = int(cfg.get("clipgen", "scene_count", default=5))
    refs = _available_refs()
    refs_line = (
        f"Reference photos available (assign relevant ones per scene via ref_images): {refs}\n"
        if refs else
        "No reference photos provided yet; write image_prompt to stand alone.\n"
    )
    strategy_block = ""
    if strategy:
        strategy_block = (
            "Buyer-persona & creative strategy YOU already developed (the script MUST execute "
            "it — hit the biggest_pain, use the hook_angle, show the proof_to_show, avoid the "
            f"do_not traps):\n{json.dumps(strategy, ensure_ascii=False)}\n\n"
        )
    focus = _focus_directive(cfg)
    focus_block = f"{focus}\n\n" if focus else ""
    return (
        f"Persona & format guide:\n{_persona_prompt(cfg.template)}\n\n"
        f"{strategy_block}"
        f"Template: {cfg.template}\n{_lang_directive(cfg)}\n\n"
        f"{focus_block}"
        f"{_diff_block(cfg, mem)}"
        f"{_structure_directive(cfg)}\n\n"
        f"{templates.hook_bank()}\n\n"
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

    pinned = (cfg.get("viral_template", default="auto") or "auto").strip().lower()
    used = pinned if templates.get(pinned) else ("factory_tour" if cfg.template == "factory" else "pas")
    return Script(template=cfg.template, language=cfg.language, hook=hook, cta=cta,
                  scenes=scenes, template_used=used)


def _call_llm(cfg: TaskConfig, secrets: Secrets,
              strategy: dict | None = None, mem: dict | None = None) -> Script:
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _user_prompt(cfg, strategy, mem)},
    ]
    data = _complete_json(
        secrets, messages, 0.9, validate=lambda d: bool(d.get("scenes")),
    )
    data.setdefault("template", cfg.template)
    data.setdefault("language", cfg.language)
    pinned = (cfg.get("viral_template", default="auto") or "auto").strip().lower()
    if templates.get(pinned):
        data.setdefault("template_used", pinned)
    return Script.from_dict(data)


def generate_script(cfg: TaskConfig, secrets: Secrets,
                    strategy: dict | None = None, mem: dict | None = None) -> Script:
    if not secrets.llm_api_key:
        return _template_fallback(cfg)
    return _call_llm(cfg, secrets, strategy=strategy, mem=mem)
