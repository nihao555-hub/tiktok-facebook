"""创意广告引擎 (creative ad engine) —— 高概念叙事大片的「造创意机器」。

对标拆解过的京东外卖《星球杯·黑牌》那类**高概念创意广告**：不是 UGC 带货，而是
电影质感的品牌创意片(借一个世界观演一个反转故事，把卖点演成剧情高潮，再丝滑从软广
转硬广)。这条片的「好看」可以被工程化成一个公式：

    一条片 = [世界观母题] × [违反常识的奇观] × [反转机制]
             × [卖点的视觉隐喻] × [软广转硬广的道具] × [解说/旁白腔调]

每个轴是一个**变量库**(下方 AXES)。这个模块做三件事，保证「可批量、不同质化」：
1. 抽样 (sample)：每个轴抽一个值，组成一个新创意；可锁定某些轴、可指定随机种子复现。
2. 防同质化硬保证 (novelty)：和历史里**每一条**片至少有 `min_axes_different` 个轴不同，
   做不到就重抽——这是用代码兜底的"每次创意点都不同"，而不是指望 LLM 自觉。
3. 落地 (brief)：把抽到的组合渲染成一段创意指令，注入 LLM 写逐秒脚本(见 providers/llm.py)。

历史持久化在 creative_memory/<line>.json（运行期状态，已 gitignore），按"创作线 line"隔离，
所以同一条线连着跑就会越跑越不撞款。无 LLM key 时仍可用：抽样/批量/防同质化全在本地完成。

命令行：
    python -m pipeline.creative_engine --list                 # 看全部变量轴/可选值
    python -m pipeline.creative_engine --batch 5              # 批量产 5 个互不雷同的创意
    python -m pipeline.creative_engine --batch 5 --selling-point "30分钟必达"
    python -m pipeline.creative_engine --batch 3 --lock world=wuxia --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path

from .config import REPO_ROOT

MEMORY_DIR = REPO_ROOT / "creative_memory"

# --------------------------------------------------------------------------
# 六大变量轴。每个 option: id / zh(短名) / desc(创意指引) / en(喂图/视频模型的英文线索)。
# 库越大、组合空间越大 → 越难同质化。当前 ~ 12×12×10×10×10×8 ≈ 115 万种组合。
# --------------------------------------------------------------------------
AXES: list[dict] = [
    {
        "id": "world",
        "zh": "世界观母题",
        "why": "给片子一张'皮肤'。换皮肤是和上一条片拉开距离最直观的一招。",
        "options": [
            {"id": "scifi_arena", "zh": "星际竞技", "desc": "外星文明 vs 地球队的星球级赛事/对决",
             "en": "epic sci-fi stadium on an alien planet, cosmic crowd, holographic scoreboard"},
            {"id": "wuxia", "zh": "武侠江湖", "desc": "客栈、屋顶轻功、刀光剑影的江湖恩怨",
             "en": "ancient Chinese wuxia world, rooftops, lanterns, swordsmen, misty bamboo forest"},
            {"id": "xianxia_myth", "zh": "东方神话", "desc": "西游/封神/天庭仙界的神魔设定",
             "en": "Chinese mythology realm, heavenly court, immortals on clouds, divine glow"},
            {"id": "apocalypse", "zh": "末日废土", "desc": "灾变后的废墟世界，资源稀缺、最后的希望",
             "en": "post-apocalyptic wasteland, ruined city, dust storms, lone survivors"},
            {"id": "cyberpunk", "zh": "赛博都市", "desc": "霓虹高楼、义体黑客、雨夜的未来城",
             "en": "neon cyberpunk megacity at night, rain, holograms, flying cars"},
            {"id": "spy_noir", "zh": "谍战特工", "desc": "潜入、追车、密码箱的紧张特工任务",
             "en": "spy thriller, sleek agents, night chase, briefcase, dramatic shadows"},
            {"id": "fairytale", "zh": "童话绘本", "desc": "会说话的动物、魔法森林的绘本质感",
             "en": "storybook fairytale, whimsical magical forest, soft painterly light"},
            {"id": "war_epic", "zh": "史诗战场", "desc": "古战场千军万马的宏大战争史诗",
             "en": "epic ancient battlefield, vast armies, banners, cinematic scale"},
            {"id": "deep_ocean", "zh": "深海秘境", "desc": "发光生物、沉船、巨物的幽蓝深海",
             "en": "mysterious deep ocean, bioluminescent creatures, shipwreck, vast blue"},
            {"id": "kaiju_city", "zh": "怪兽都市", "desc": "巨兽来袭、城市保卫战的特摄场面",
             "en": "giant kaiju monster attacking a modern city, scale chaos, hero stand"},
            {"id": "gourmet_jianghu", "zh": "美食江湖", "desc": "厨神对决、深夜食堂的食物江湖",
             "en": "culinary battle world, steaming kitchen arena, dramatic plating, night market"},
            {"id": "time_traveler", "zh": "时空穿越", "desc": "穿越古今/未来的时间旅人设定",
             "en": "time-travel adventure, portals, eras colliding, swirling time vortex"},
        ],
    },
    {
        "id": "spectacle",
        "zh": "违反常识的奇观",
        "why": "0.5 秒钩子。开场就违反物理常识，逼观众'这不可能'而停下。",
        "options": [
            {"id": "time_freeze", "zh": "时间静止", "desc": "全场凝固，只有一人/一物还能动",
             "en": "time frozen mid-action, everyone stuck still, only one subject moving"},
            {"id": "gravity_flip", "zh": "重力反转", "desc": "万物失重上浮 / 重力方向突然翻转",
             "en": "gravity reversed, objects and people floating upward, world flipped"},
            {"id": "self_moving", "zh": "物体自行运动", "desc": "球/物件无人触碰却自己运动",
             "en": "an object moving on its own with no one touching it, eerie precise motion"},
            {"id": "teleport_fold", "zh": "空间折叠", "desc": "空间像纸一样折叠/瞬移传送",
             "en": "space folding like paper, instant teleport between two places"},
            {"id": "multiply", "zh": "复制增殖", "desc": "一变多、分身、万物成倍涌现",
             "en": "one object multiplying into many, clones, swarming duplication"},
            {"id": "giant_shrink", "zh": "巨大化/缩小", "desc": "瞬间变巨/变微缩的尺度反差",
             "en": "sudden giant-scale or miniature shrink, extreme size contrast"},
            {"id": "hyperspeed", "zh": "万物极速", "desc": "一切被加速成残影/子弹时间反向",
             "en": "everything hyper-accelerated into motion blur, reverse bullet-time"},
            {"id": "levitation", "zh": "漂浮失重", "desc": "人与物静静悬浮于半空",
             "en": "people and objects silently levitating in mid-air, weightless"},
            {"id": "mirror_world", "zh": "镜像世界", "desc": "镜中/平行世界与现实错位",
             "en": "mirror world splitting from reality, parallel reflection diverges"},
            {"id": "element_control", "zh": "操控元素", "desc": "凭意念操控水火风/天气",
             "en": "elemental powers bending water fire wind, weather summoned by a gesture"},
            {"id": "body_swap", "zh": "身份互换", "desc": "灵魂/身体互换造成的错位",
             "en": "two characters swapping bodies/souls, mismatched behavior"},
            {"id": "rewind", "zh": "时光倒流", "desc": "画面/事件突然倒带回放",
             "en": "time visibly rewinding, actions playing backward, debris reassembling"},
        ],
    },
    {
        "id": "reversal",
        "zh": "反转机制",
        "why": "持续悬念引擎。每隔几秒一个意外/打脸，观众一直猜不到。",
        "options": [
            {"id": "chain_misdirection", "zh": "连环误导", "desc": "以为A其实B，一层套一层地反转",
             "en": "chained misdirection, each reveal flips the previous assumption"},
            {"id": "identity_flip", "zh": "身份反转", "desc": "不起眼的路人其实是隐藏高手/关键人",
             "en": "an overlooked bystander turns out to be the hidden master / key player"},
            {"id": "fake_crisis", "zh": "假危机真营销", "desc": "看似天大危机，结局其实是个轻巧反转",
             "en": "a seemingly huge crisis resolves into a light, clever twist"},
            {"id": "pov_flip", "zh": "视角反转", "desc": "换一个视角，整件事意义完全反过来",
             "en": "the same event reframed from another POV flips its whole meaning"},
            {"id": "cause_effect_inversion", "zh": "因果倒置", "desc": "先给结果，再揭晓荒诞的起因",
             "en": "show the effect first, then reveal an absurd hidden cause"},
            {"id": "underdog_win", "zh": "弱者逆袭", "desc": "被看扁的一方最后一击逆转打脸",
             "en": "the underdog everyone dismissed lands the final reversal"},
            {"id": "anticlimax", "zh": "反高潮", "desc": "以为要放大招，结果是个日常小动作",
             "en": "buildup to an epic move that turns out to be a tiny everyday action"},
            {"id": "villain_savior", "zh": "反派即救星", "desc": "被当成威胁的角色其实是来帮忙的",
             "en": "the feared 'threat' turns out to be the one who saves the day"},
            {"id": "everyday_origin", "zh": "神迹源于平凡", "desc": "惊天奇观背后是某个超普通的动作",
             "en": "the jaw-dropping spectacle is revealed to come from a mundane act"},
            {"id": "double_twist", "zh": "双重反转", "desc": "刚反转完又再反转一次",
             "en": "a twist that immediately gets twisted again, double rug-pull"},
        ],
    },
    {
        "id": "metaphor",
        "zh": "卖点的视觉隐喻",
        "why": "卖点不口播，用画面'演'出来。这一轴决定怎么把抽象卖点变成剧情。",
        "options": [
            {"id": "superpower", "zh": "卖点=超能力", "desc": "把卖点演成让对手束手无策的超能力",
             "en": "the selling point dramatized as a superpower that leaves rivals helpless"},
            {"id": "key_prop", "zh": "卖点=关键道具", "desc": "把卖点藏成扭转剧情的关键道具",
             "en": "the selling point hidden as the prop that turns the whole plot"},
            {"id": "personified", "zh": "卖点拟人", "desc": "把卖点/产品具象成一个角色登场救场",
             "en": "the selling point personified as a character who enters and saves the scene"},
            {"id": "extreme_contrast", "zh": "极限对比", "desc": "对手拼尽全力，仍输给这个卖点",
             "en": "rivals try everything at full power yet still lose to this one advantage"},
            {"id": "rule_breaker", "zh": "打破规则的变量", "desc": "卖点是唯一能打破奇观规则的东西",
             "en": "the selling point is the ONLY thing that can break the spectacle's rule"},
            {"id": "countdown_savior", "zh": "倒计时救场", "desc": "绝境倒计时里，卖点踩点解决一切",
             "en": "in a last-second countdown, the selling point lands exactly in time"},
            {"id": "world_transform", "zh": "卖点改变世界", "desc": "卖点一出现，世界从坏到好翻转",
             "en": "the moment the selling point appears, the world flips from bad to good"},
            {"id": "invisible_until_needed", "zh": "关键才显形", "desc": "卖点隐形，最关键一刻才现身定乾坤",
             "en": "the selling point stays invisible, revealing itself only at the decisive moment"},
            {"id": "scale_proof", "zh": "规模坐实", "desc": "用夸张的数量/规模把卖点演成奇观",
             "en": "an exaggerated scale/quantity makes the selling point a literal spectacle"},
            {"id": "sensory_amplify", "zh": "感官放大", "desc": "把卖点放大成看得见摸得着的感官冲击",
             "en": "the selling point amplified into a vivid, tangible sensory spectacle"},
        ],
    },
    {
        "id": "transition",
        "zh": "软广转硬广道具",
        "why": "从故事丝滑接到品牌/促销，不突兀。这是'高级感'的关键一招。",
        "options": [
            {"id": "prop_carry", "zh": "道具承接", "desc": "剧中道具顺势变成品牌牌/促销物(如牌→广告牌)",
             "en": "an in-story prop seamlessly becomes the brand card / promo sign"},
            {"id": "pun_line", "zh": "台词双关", "desc": "一句剧情台词同时就是品牌 slogan",
             "en": "a story line of dialogue doubles exactly as the brand slogan"},
            {"id": "camera_through", "zh": "镜头穿越", "desc": "镜头从剧情世界一镜推进到产品/品牌",
             "en": "one continuous camera move pushes from the story world into the product"},
            {"id": "product_persona", "zh": "产品拟人收尾", "desc": "产品/吉祥物作为角色登场点题",
             "en": "the product / brand mascot enters as a character to land the punchline"},
            {"id": "match_cut", "zh": "同形转场", "desc": "剧中物形状匹配，硬切到同形的产品",
             "en": "match-cut on a shared shape from the story object to the product"},
            {"id": "caption_reveal", "zh": "字幕揭示", "desc": "一行字幕揭示'原来这是…'完成反转点题",
             "en": "a single caption reveal recontextualizes the whole scene as the brand"},
            {"id": "reward_reveal", "zh": "奖励揭晓", "desc": "剧情的胜利=观众的优惠/福利到手",
             "en": "the story's victory equals the viewer's coupon / offer unlocked"},
            {"id": "breaking_news", "zh": "伪资讯插入", "desc": "伪新闻/弹窗自然插入促销信息",
             "en": "a faux news flash / notification naturally injects the promo"},
            {"id": "world_to_logo", "zh": "世界坍缩成logo", "desc": "奇观世界收束坍缩成品牌 logo/主视觉",
             "en": "the spectacle world collapses elegantly into the brand logo / key visual"},
            {"id": "mascot_punchline", "zh": "吉祥物点题", "desc": "品牌吉祥物用一个梗收尾点题",
             "en": "the brand mascot delivers a final comedic punchline to tie it together"},
        ],
    },
    {
        "id": "narration",
        "zh": "解说/旁白腔调",
        "why": "声音决定气质，也是悬念引擎。换腔调让同一个奇观气质完全不同。",
        "options": [
            {"id": "sports_commentary", "zh": "体育解说体", "desc": "激情解说，持续制造'接下来呢'的悬念",
             "en": "high-energy live sports commentary voice driving suspense"},
            {"id": "mystery_vo", "zh": "悬疑低语", "desc": "压低声线的悬疑旁白，慢慢揭谜",
             "en": "low, hushed mystery narration slowly unveiling the puzzle"},
            {"id": "storyteller", "zh": "说书评书腔", "desc": "中式说书人抑扬顿挫，'话说…'",
             "en": "classic Chinese storyteller cadence, rhythmic and theatrical"},
            {"id": "news_anchor", "zh": "新闻播报体", "desc": "一本正经的新闻主播口吻报道荒诞事件",
             "en": "deadpan news-anchor delivery reporting an absurd event as breaking news"},
            {"id": "epic_trailer", "zh": "史诗预告腔", "desc": "电影预告片式的低沉宏大旁白",
             "en": "deep, grand movie-trailer voiceover, epic and cinematic"},
            {"id": "asmr_whisper", "zh": "ASMR轻语", "desc": "极近距离的轻柔耳语，沉浸感",
             "en": "intimate close-mic ASMR whisper, immersive and soft"},
            {"id": "rap_flow", "zh": "押韵/rap", "desc": "带节奏押韵的 rap，卡点推进",
             "en": "rhythmic rhyming rap flow synced to the cuts"},
            {"id": "inner_monologue", "zh": "第一人称独白", "desc": "主角内心独白，代入式叙述",
             "en": "first-person inner monologue, intimate and immersive"},
        ],
    },
]

_AX_BY_ID = {a["id"]: a for a in AXES}
_OPT_BY_ID = {a["id"]: {o["id"]: o for o in a["options"]} for a in AXES}

# 逐秒叙事骨架（高概念创意片通用结构；时长按 target_seconds 等比缩放）。
CREATIVE_BEATS: list[dict] = [
    {"t": "0-2s", "goal": "奇观钩子",
     "desc": "用[违反常识的奇观]直接砸开场，0 铺垫，1 秒内让人'这不可能'而停下"},
    {"t": "2-10s", "goal": "立世界观+抛悬念",
     "desc": "用[世界观母题]+[解说腔调]迅速立住设定，抛出一个让人想知道答案的悬念"},
    {"t": "10-35s", "goal": "连环反转升级",
     "desc": "用[反转机制]每 3-6 秒一个意外，危机/赌注不断升级，观众一直猜不到"},
    {"t": "35-50s", "goal": "卖点高潮揭晓",
     "desc": "用[卖点视觉隐喻]把卖点演成扭转全局的关键——这是最大的反转、最爽的一刻"},
    {"t": "50-58s", "goal": "软广转硬广",
     "desc": "用[软广转硬广道具]把剧情丝滑接到品牌/促销，绝不生硬"},
    {"t": "58s+", "goal": "品牌定帧+CTA",
     "desc": "品牌强资产 + 一句记得住的 slogan + 促销/CTA，结尾留个回味钩子"},
]


# --------------------------------------------------------------------------
# 基础查询
# --------------------------------------------------------------------------
def axis_ids() -> list[str]:
    return [a["id"] for a in AXES]


def get_axis(axis_id: str) -> dict | None:
    return _AX_BY_ID.get((axis_id or "").strip().lower())


def get_option(axis_id: str, opt_id: str) -> dict | None:
    return _OPT_BY_ID.get(axis_id, {}).get((opt_id or "").strip().lower())


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", (text or "").strip()).strip("-").lower()
    return s[:40]


# --------------------------------------------------------------------------
# 抽样 + 防同质化
# --------------------------------------------------------------------------
def _diff_count(a: dict, b: dict) -> int:
    """两个组合有多少个轴取值不同。"""
    return sum(1 for ax in axis_ids() if a.get(ax) != b.get(ax))


def is_novel(combo: dict, history: list[dict], min_axes_different: int) -> bool:
    """combo 是否和历史里的每一条都至少差 min_axes_different 个轴。"""
    return all(_diff_count(combo, h) >= min_axes_different for h in history)


def _random_combo(rng: random.Random, lock: dict | None) -> dict:
    lock = {k: v for k, v in (lock or {}).items() if get_option(k, v)}
    combo: dict[str, str] = {}
    for ax in AXES:
        aid = ax["id"]
        if aid in lock:
            combo[aid] = lock[aid].strip().lower()
        else:
            combo[aid] = rng.choice(ax["options"])["id"]
    return combo


def sample(
    history: list[dict] | None = None,
    *,
    seed: int | None = None,
    lock: dict | None = None,
    min_axes_different: int = 3,
    max_tries: int = 4000,
) -> dict:
    """抽一个和历史不撞款的创意组合。

    - lock: 锁定某些轴(如 {"world": "wuxia"})，其余随机。
    - min_axes_different: 和历史每条片至少不同的轴数(防同质化硬阈值)。
      会被自动夹到'可自由变化的轴数'以内(锁太多时阈值自动下调)。
    - seed: 给定则可复现；不给用时间种子。
    返回 {axis_id: option_id}。实在抽不出新组合时返回'与历史平均差异最大'的候选并不报错。
    """
    history = history or []
    lock = {k: v for k, v in (lock or {}).items() if get_option(k, v)}
    free_axes = len(axis_ids()) - len(lock)
    min_diff = max(1, min(min_axes_different, free_axes)) if free_axes else 0
    rng = random.Random(seed if seed is not None else time.time_ns())

    best: dict | None = None
    best_score = -1.0
    for _ in range(max_tries):
        cand = _random_combo(rng, lock)
        if not history or is_novel(cand, history, min_diff):
            return cand
        score = sum(_diff_count(cand, h) for h in history) / len(history)
        if score > best_score:
            best_score, best = score, cand
    return best or _random_combo(rng, lock)


def batch(
    n: int,
    *,
    history: list[dict] | None = None,
    seed: int | None = None,
    lock: dict | None = None,
    min_axes_different: int = 3,
) -> list[dict]:
    """一次产 n 个互不雷同的组合(彼此之间、以及和传入历史之间都满足 novelty)。"""
    history = list(history or [])
    out: list[dict] = []
    for i in range(max(0, n)):
        s = None if seed is None else seed + i
        combo = sample(
            history, seed=s, lock=lock, min_axes_different=min_axes_different
        )
        out.append(combo)
        history.append(combo)
    return out


# --------------------------------------------------------------------------
# 历史持久化（按"创作线 line"隔离；和 brand_memory 同思路）
# --------------------------------------------------------------------------
def line_id(cfg=None) -> str:
    if cfg is not None:
        explicit = cfg.get("creative", "line", default="") or cfg.get("project", default="")
        if explicit:
            return _slug(str(explicit)) or "default"
    return "default"


def _mem_path(line: str) -> Path:
    return MEMORY_DIR / f"{line}.json"


def load_history(cfg=None, line: str | None = None) -> list[dict]:
    lid = line or line_id(cfg)
    p = _mem_path(lid)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return [h.get("combo", h) for h in data.get("runs", [])]
        except (json.JSONDecodeError, OSError):
            pass
    return []


def record(combo: dict, cfg=None, line: str | None = None, meta: dict | None = None) -> Path:
    lid = line or line_id(cfg)
    p = _mem_path(lid)
    runs: list[dict] = []
    if p.exists():
        try:
            runs = json.loads(p.read_text(encoding="utf-8")).get("runs", [])
        except (json.JSONDecodeError, OSError):
            runs = []
    runs.append({"ts": int(time.time()), "combo": combo, **({"meta": meta} if meta else {})})
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"line": lid, "runs": runs[-200:]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return p


# --------------------------------------------------------------------------
# 渲染：组合 -> 人读摘要 / LLM 创意指令
# --------------------------------------------------------------------------
def combo_summary(combo: dict) -> str:
    """一行中文摘要，给控制台打印。"""
    parts = []
    for ax in AXES:
        o = get_option(ax["id"], combo.get(ax["id"], ""))
        parts.append(f"{ax['zh']}={o['zh'] if o else '?'}")
    return " × ".join(parts)


def _selling_points(cfg=None, selling_point: str | None = None) -> list[str]:
    if selling_point:
        return [selling_point]
    if cfg is not None:
        brief = cfg.get("brief", default={}) or {}
        sps = brief.get("selling_points") or []
        if sps:
            return list(sps)
        if brief.get("product_name"):
            return [f"{brief['product_name']} 的核心卖点"]
    return ["你的核心卖点"]


def combo_brief(combo: dict, cfg=None, selling_point: str | None = None) -> str:
    """把组合渲染成注入 LLM 的创意指令块（中英混合，模型可读）。"""
    sps = _selling_points(cfg, selling_point)
    lines = [
        "CREATIVE CONCEPT (high-concept cinematic brand film — execute THIS exact axis "
        "combination; it is engineered to be different from past videos):",
    ]
    for ax in AXES:
        o = get_option(ax["id"], combo.get(ax["id"], ""))
        if not o:
            continue
        lines.append(
            f"  • [{ax['zh']} / {ax['id']}] {o['zh']} — {o['desc']}\n"
            f"      visual cue: {o['en']}"
        )
    lines.append("")
    lines.append(f"SELLING POINT(S) to dramatize (do NOT just say them out loud — make the "
                 f"[卖点视觉隐喻] axis DRAMATIZE them): {', '.join(sps)}")
    return "\n".join(lines)


def structure_directive(target_seconds: int = 50) -> str:
    """逐秒叙事骨架，注入 LLM。时间是相对节奏，按 target_seconds 等比理解。"""
    beats = "\n".join(f"    {b['t']}: {b['goal']} — {b['desc']}" for b in CREATIVE_BEATS)
    return (
        f"NARRATIVE STRUCTURE (target ~{target_seconds}s; treat the timestamps as relative "
        f"pacing and scale them to the real length — keep cuts fast, a new beat every few seconds):\n"
        f"{beats}\n"
        "Build the scenes to follow these beats IN ORDER, but improvise the concrete story, "
        "shots and lines freely inside the chosen axis combination — never canned."
    )


def strategy(cfg=None, *, selling_point: str | None = None) -> dict:
    """创意模式下的'策略'：抽一个不撞款的组合、落历史、并返回 strategy 字典。

    返回的字典既带 creative_combo(给脚本生成用)，也填了若干通用字段让 run.py 能打印。
    """
    crt = (cfg.get("creative", default={}) or {}) if cfg is not None else {}
    lock = crt.get("lock") or {}
    seed = crt.get("seed")
    min_diff = int(crt.get("min_axes_different", 3) or 3)
    history = load_history(cfg)
    combo = sample(history, seed=seed, lock=lock, min_axes_different=min_diff)
    record(combo, cfg, meta={"summary": combo_summary(combo)})

    sps = _selling_points(cfg, selling_point)
    spec = {ax["id"]: combo[ax["id"]] for ax in AXES}
    world = get_option("world", combo["world"]) or {}
    spec_o = get_option("spectacle", combo["spectacle"]) or {}
    return {
        "mode": "creative",
        "creative_combo": spec,
        "creative_summary": combo_summary(combo),
        "market": (cfg.get("brief", "target_market", default="") if cfg else "") or "general",
        "hook_angle": f"{spec_o.get('zh', '')}（{spec_o.get('desc', '')}）",
        "biggest_pain": "刷到广告就划走——必须用奇观+反转在 1 秒内勾住、并把卖点演成剧情",
        "proof_to_show": sps,
        "decisive_trigger": (cfg.get("brief", "cta", default="") if cfg else "") or "结尾品牌+促销+CTA",
        "recommended_template": "creative_narrative",
        "world": world.get("zh", ""),
        "do_not": ["把卖点直接口播", "和最近的片子撞世界观/奇观/反转", "软广转硬广生硬"],
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def overview() -> str:
    out = ["创意广告引擎 · 变量轴总览（每条片从各轴各抽一个值，组合即一个新创意）", ""]
    for ax in AXES:
        out.append(f"[{ax['id']}] {ax['zh']} — {ax['why']}")
        for o in ax["options"]:
            out.append(f"    - {o['id']:<22} {o['zh']}：{o['desc']}")
        out.append("")
    n = 1
    for ax in AXES:
        n *= len(ax["options"])
    out.append(f"组合空间 ≈ {n:,} 种（× '和历史≥N轴不同' 的防同质化约束）")
    return "\n".join(out)


def _parse_lock(items: list[str] | None) -> dict:
    lock: dict[str, str] = {}
    for it in items or []:
        if "=" in it:
            k, v = it.split("=", 1)
            lock[k.strip()] = v.strip()
    return lock


def main() -> None:
    ap = argparse.ArgumentParser(description="创意广告引擎：批量产'不撞款'的高概念创意")
    ap.add_argument("--list", action="store_true", help="列出全部变量轴与可选值后退出")
    ap.add_argument("--batch", type=int, default=0, help="批量产 N 个互不雷同的创意组合")
    ap.add_argument("--selling-point", default="", help="要演的卖点（不填用通用占位）")
    ap.add_argument("--lock", action="append", default=[],
                    help="锁定某轴，如 --lock world=wuxia（可多次）")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（复现）")
    ap.add_argument("--min-diff", type=int, default=3, help="和历史/彼此至少不同的轴数")
    ap.add_argument("--line", default="cli", help="创作线 id（隔离历史，连续跑越跑越不撞）")
    ap.add_argument("--brief", action="store_true", help="同时打印每个创意的 LLM 指令块")
    ap.add_argument("--no-record", action="store_true", help="不写入历史（试跑）")
    args = ap.parse_args()

    if args.list or args.batch <= 0:
        print(overview())
        return

    lock = _parse_lock(args.lock)
    sp = args.selling_point or None
    history = load_history(line=args.line)
    combos = batch(args.batch, history=history, seed=args.seed, lock=lock,
                   min_axes_different=args.min_diff)
    for i, combo in enumerate(combos, 1):
        print(f"\n=== 创意 #{i} ===")
        print(combo_summary(combo))
        if args.brief:
            print("-" * 60)
            print(combo_brief(combo, selling_point=sp))
            print(structure_directive())
        if not args.no_record:
            record(combo, line=args.line, meta={"summary": combo_summary(combo)})
    print(f"\n共 {len(combos)} 个创意" + ("（已写入历史）" if not args.no_record else "（未写入历史）"))


if __name__ == "__main__":
    main()
