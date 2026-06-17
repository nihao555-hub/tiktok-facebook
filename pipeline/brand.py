"""创意差异化层 (anti-homogenization layer)。

目标：换一个工厂就不要撞款。做三件事——
1. 品牌母题档案 (brand signature)：每个工厂一份"招牌母题/品牌性格/英雄产品/独家证据/
   创始故事"，第一次生成时由 LLM 产出并**持久化**，之后每条片子都注入它，保证同一个
   工厂的视频是"同一个有辨识度的品牌"，而不是千篇一律的模板。
2. 钩子轮换 (hook rotation)：记录该工厂最近用过的"钩子心理类别"，下次优先从还没用过的
   类别里挑，避免每条都"无中间商/源头直供"。
3. 反重复记忆 (anti-repeat)：记录最近用过的爆款结构、开场钩子文案、开场画面，注入提示词
   让 LLM"必须明显不同"。

记忆持久化在 brand_memory/<brand_id>.json（运行期状态，已 gitignore）。
没有 LLM key 时本层自动降级为"只记录、不注入"，不影响流水线跑通。
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from . import templates
from .config import REPO_ROOT, TaskConfig
from .script_model import Script

MEMORY_DIR = REPO_ROOT / "brand_memory"


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", (text or "").strip()).strip("-").lower()
    return s[:40]


def brand_id(cfg: TaskConfig) -> str:
    """工厂身份 id：优先用 config 的 brand.id；否则由 brief 的工厂名/产品名派生（稳定可复现）。"""
    explicit = cfg.get("brand", "id", default="")
    if explicit:
        return _slug(str(explicit)) or "brand"
    brief = cfg.get("brief", default={}) or {}
    identity = str(
        brief.get("factory_name")
        or brief.get("product_name")
        or cfg.project
        or "brand"
    )
    h = hashlib.md5(identity.encode("utf-8")).hexdigest()[:6]
    slug = _slug(identity)
    return f"{slug}-{h}" if slug else f"brand-{h}"


def _path(bid: str) -> Path:
    return MEMORY_DIR / f"{bid}.json"


def load_memory(cfg: TaskConfig) -> dict:
    bid = brand_id(cfg)
    p = _path(bid)
    if p.exists():
        try:
            mem = json.loads(p.read_text(encoding="utf-8"))
            mem.setdefault("brand_id", bid)
            mem.setdefault("profile", {})
            mem.setdefault("history", [])
            return mem
        except (json.JSONDecodeError, OSError):
            pass
    return {"brand_id": bid, "profile": {}, "history": []}


def save_memory(mem: dict) -> Path:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(mem["brand_id"])
    mem["history"] = mem.get("history", [])[-50:]
    p.write_text(json.dumps(mem, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def profile(mem: dict) -> dict:
    return mem.get("profile") or {}


def _recent(mem: dict, window: int) -> list[dict]:
    return (mem.get("history") or [])[-window:]


def _used(mem: dict, window: int) -> dict:
    rec = _recent(mem, window)
    return {
        "hook_categories": [h.get("hook_category", "") for h in rec if h.get("hook_category")],
        "templates": [h.get("template_used", "") for h in rec if h.get("template_used")],
        "hooks": [h.get("hook", "") for h in rec if h.get("hook")],
        "openings": [h.get("opening", "") for h in rec if h.get("opening")],
    }


def _hook_category_ids() -> list[str]:
    return [c["id"] for c in templates.HOOK_CATEGORIES]


def profile_directive(mem: dict) -> str:
    """把持久化的品牌母题注入提示词，让同一工厂的片子保持一致的辨识度。"""
    prof = profile(mem)
    if not prof:
        return ""
    return (
        "BRAND SIGNATURE (this factory's persistent identity — keep it CONSISTENT across every "
        "video so the brand is recognizable; weave the signature_motif / visual_motifs / tone "
        "through this script, but DO NOT just repeat a previous script):\n"
        f"{json.dumps(prof, ensure_ascii=False)}"
    )


def antirepeat_directive(cfg: TaskConfig, mem: dict) -> str:
    """反重复 + 钩子轮换：列出最近用过的，强制这条明显不同。"""
    window = int(cfg.get("differentiation", "recent_window", default=6) or 6)
    used = _used(mem, window)
    all_hooks = _hook_category_ids()
    all_tpls = [t["id"] for t in templates.for_persona(cfg.template)]
    fresh_hooks = [h for h in all_hooks if h not in used["hook_categories"]] or all_hooks
    fresh_tpls = [t for t in all_tpls if t not in used["templates"]] or all_tpls

    if not used["hooks"] and not used["templates"]:
        return (
            "FIRST VIDEO FOR THIS FACTORY: establish a distinctive brand signature (a memorable "
            "motif, personality and hero angle) that we will keep CONSISTENT and rotate fresh "
            "angles around in future videos — make it stand out from generic factory ads. "
            'Report which hook category you used in "hook_category" (one of: '
            f"{', '.join(all_hooks)})."
        )
    return (
        "ANTI-REPEAT (HARD REQUIREMENT — this factory already has videos; this one MUST be clearly "
        "different so multiple videos don't homogenize):\n"
        f"- Recently used HOOK categories — DO NOT use these again now: {used['hook_categories']}\n"
        f"- Recently used STRUCTURES — avoid these: {used['templates']}\n"
        f"- Recent opening hook lines — DO NOT echo or paraphrase these: {used['hooks']}\n"
        f"- Recent opening shots — shoot a DIFFERENT opening this time: {used['openings']}\n"
        f"- PREFER a still-fresh hook category from: {fresh_hooks}\n"
        f"- PREFER a structure not used recently from: {fresh_tpls}\n"
        'Report which hook category you used in "hook_category".'
    )


def directives(cfg: TaskConfig, mem: dict) -> str:
    """合并 品牌母题 + 反重复轮换 两段指令（供 llm.py 注入）。"""
    if not bool(cfg.get("differentiation", "enabled", default=True)):
        return ""
    parts = [profile_directive(mem), antirepeat_directive(cfg, mem)]
    return "\n\n".join(p for p in parts if p)


def _opening(script: Script) -> str:
    if not script.scenes:
        return ""
    s0 = script.scenes[0]
    return (s0.on_screen_text or s0.img_prompt or "")[:90]


def record_run(mem: dict, strategy: dict, script: Script) -> dict:
    """把本次生成写进记忆：首次落地品牌母题 + 追加一条历史（钩子类别/结构/开场）。"""
    if not profile(mem):
        sig = (strategy or {}).get("brand_signature") or {}
        if sig:
            mem["profile"] = sig
    mem.setdefault("history", []).append({
        "ts": int(time.time()),
        "template_used": script.template_used or "",
        "hook_category": script.hook_category or "",
        "hook": script.hook or "",
        "opening": _opening(script),
    })
    return mem


def summary_line(mem: dict, cfg: TaskConfig) -> str:
    """给控制台打印的一行差异化摘要。"""
    prof = profile(mem)
    motif = prof.get("signature_motif") or prof.get("tagline") or "（待建立）"
    n = len(mem.get("history") or [])
    return f"品牌母题=[{mem['brand_id']}] {motif} · 历史片数={n}"
