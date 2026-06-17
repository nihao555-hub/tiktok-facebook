"""自包含的「剪映/CapCut 草稿装饰核心」——只依赖 pyJianYingDraft + 标准库。

这个模块是装饰逻辑的**唯一真相源**：
- Linux 流水线 (capcut_export.py) 用它生成本地预览草稿 draft_content.json；
- 同一份文件还会被**拷进给用户的 Win/Mac 一键导出包**里，由 make_capcut_draft.py 在用户
  自己的电脑上调用，按本地素材路径重建出完全相同的「做厚」草稿，再在 CapCut 里点导出。

因此本文件**绝不能** import 本仓库其它模块（用户机器上没有本仓库），只能用 pyJianYingDraft
和标准库。所有装饰都用 _safe 容错：某个特效/动画在当前 pyJianYingDraft 版本不可用时跳过，
不让整份草稿崩。

枚举名是中文，按「子串」匹配（_pick），找不到就跳过（返回 None），不会乱套一个错的特效。
泰文用 Kanit 字体（修方块/豆腐），中文辅助行用思源/台北黑体等 CJK 字体。
字幕默认无黑底（描边+阴影融进画面），仅 CTA 用红色按钮底。
"""

from __future__ import annotations

import subprocess
from typing import Any

# ----------------------------------------------------------------------------
# 按「爆款结构」分装饰预设：不同结构用不同转场/入场/滤镜/特效/花字动画，避免同质化。
# 值都是「枚举名子串」的优先级列表（见各 *Type 的中文枚举名）。
# ----------------------------------------------------------------------------
_DEFAULT_PRESET: dict[str, Any] = {
    "transition": ["叠化", "推近", "向右擦除"],
    "v_intro": ["轻微放大", "动感放大", "放大", "渐显"],
    "filter": ["清晰明亮", "自然清晰", "高清明亮", "奶油"],
    "filter_intensity": 18.0,
    "open_fx": ["开幕", "聚焦", "变焦推镜"],     # 开场镜头特效（仅第 1 镜前段）
    "ambient_fx": [],                            # 贯穿全片的氛围特效（克制，可空）
    "ambient_intensity": 35.0,
    "t_intro": ["弹入", "放大", "渐显"],
    "t_outro": ["渐隐", "缩小"],
    "cta_loop": ["心跳", "闪烁"],
    "hook_loop": ["闪烁"],
    "thai_font": ["Kanit_Regular", "Kanit", "Chonburi"],
    "hook_font": ["Kanit_ExtraBold", "Kanit"],
    "cjk_font": ["台北黑体_Regular", "台北黑体", "思源", "妙黑体", "圆体"],
    "accent_rgb": [1.0, 0.898, 0.0],             # 花字关键词主色（亮黄）
}


def _p(**over: Any) -> dict[str, Any]:
    d = dict(_DEFAULT_PRESET)
    d.update(over)
    return d


DECORATION_PRESETS: dict[str, dict[str, Any]] = {
    # 工厂溯源(B2B)：克制可信，推近/拉伸转场 + 质感电影滤镜 + 开幕聚焦
    "factory_tour": _p(transition=["推近", "向右拉伸", "叠化"],
                       v_intro=["动感放大", "轻微放大"],
                       filter=["质感电影", "高清4K电影", "清晰明亮"], filter_intensity=15.0,
                       open_fx=["开幕", "聚焦"], ambient_fx=["暗角"], ambient_intensity=18.0),
    # 老板出镜(B2B)：真实口播感，打字机花字、几乎不加滤镜、不加循环动画
    "founder_direct": _p(transition=["叠化"], v_intro=["轻微放大"],
                         filter=["自然清晰", "高清明亮"], filter_intensity=10.0,
                         open_fx=["聚焦"], t_intro=["打字机_I", "故障打字机", "弹入"],
                         cta_loop=["闪烁"], hook_loop=[]),
    # 原料→成品(B2B 激光厂常用)：过程感强，推近/水波转场 + 4K 电影滤镜 + 漏光氛围
    "raw_to_finished": _p(transition=["推近", "水波向右", "叠化"],
                          v_intro=["动感放大", "轻微放大"],
                          filter=["高清4K电影", "质感电影"], filter_intensity=16.0,
                          open_fx=["聚焦", "变焦推镜"], ambient_fx=["漏光噪点", "光斑飘落"],
                          ambient_intensity=22.0, t_intro=["放大", "弹入"], cta_loop=["闪烁"]),
    # 前后对比：强冲击，故障/电视故障转场 + 质感暗调 + 心跳花字
    "before_after": _p(transition=["故障", "电视故障", "叠化"], v_intro=["动感放大"],
                       filter=["质感电影", "质感暗调"], open_fx=["变焦推镜"],
                       t_intro=["放大", "弹入"], cta_loop=["心跳"]),
    # 解压/ASMR：丝滑叠化/水波 + 奶油日系滤镜 + 光斑
    "satisfying_asmr": _p(transition=["叠化", "水波向右"], v_intro=["轻微放大"],
                          filter=["奶油", "日系奶油", "京都"], open_fx=["光斑飘落"],
                          ambient_fx=["光斑虚化"], ambient_intensity=20.0,
                          t_intro=["渐显", "波浪弹入"], hook_loop=[]),
    # 质检拷问/能力秀：硬核，故障拼贴 + 高清润白 + 心跳
    "qc_torture": _p(transition=["故障拼贴", "推近", "叠化"], v_intro=["动感放大"],
                     filter=["高清润白", "清晰明亮"], open_fx=["变焦推镜"], cta_loop=["心跳"]),
}


def preset(template_used: str) -> dict[str, Any]:
    return DECORATION_PRESETS.get((template_used or "").strip(), _DEFAULT_PRESET)


def _pick(enum, subs: list[str]):
    """按子串优先级在枚举里挑一个成员；全找不到返回 None（跳过该装饰，不乱套）。"""
    for sub in subs or []:
        for member in enum:
            if sub in member.name:
                return member
    return None


def _duration(path: str) -> float:
    """ffprobe 读时长；失败(无 ffmpeg/坏文件)返回 0，调用方回退到脚本时长。"""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30,
        )
        return float((out.stdout or "0").strip() or 0.0)
    except (subprocess.SubprocessError, ValueError, OSError):
        return 0.0


def describe(meta: dict[str, Any]) -> dict[str, Any]:
    """返回本次实际挑中的装饰枚举名（写进 decoration.json，便于你查看/复现）。"""
    import pyJianYingDraft as draft

    p = preset(meta.get("template_used") or meta.get("template") or "")

    def names(enum, subs):
        m = _pick(enum, subs)
        return m.name if m is not None else None

    return {
        "template_used": meta.get("template_used"),
        "transition": names(draft.TransitionType, p["transition"]),
        "video_intro": names(draft.IntroType, p["v_intro"]),
        "filter": names(draft.FilterType, p["filter"]),
        "filter_intensity": p["filter_intensity"],
        "open_fx": names(draft.VideoSceneEffectType, p["open_fx"]),
        "ambient_fx": names(draft.VideoSceneEffectType, p["ambient_fx"]),
        "text_intro": names(draft.TextIntro, p["t_intro"]),
        "text_outro": names(draft.TextOutro, p["t_outro"]),
        "cta_loop": names(draft.TextLoopAnim, p["cta_loop"]),
        "hook_loop": names(draft.TextLoopAnim, p["hook_loop"]),
        "thai_font": names(draft.FontType, p["thai_font"]),
        "hook_font": names(draft.FontType, p["hook_font"]),
        "cjk_font": names(draft.FontType, p["cjk_font"]),
    }


def build_script(meta: dict[str, Any], scenes: list[dict[str, Any]], script=None):
    """按分镜 + 装饰预设构建一个 pyJianYingDraft.ScriptFile（已做厚装饰）。

    meta:   {width,height,fps, hook, cta, template_used, template}
    scenes: [{clip, audio, on_screen_text, narration_th, narration_zh, seconds}, ...]
            clip/audio 为可读的本地路径（不存在则该项跳过）。
    script: 可传入一个已有 ScriptFile（如 DraftFolder.create_draft 返回的草稿）来填充；
            不传则新建一个独立 ScriptFile（用于 Linux 端 dump 预览）。
    """
    from pyJianYingDraft import (
        AudioMaterial,
        AudioSegment,
        ClipSettings,
        ScriptFile,
        TextBorder,
        TextSegment,
        TextShadow,
        TextStyle,
        TrackType,
        VideoMaterial,
        VideoSegment,
        trange,
    )
    import pyJianYingDraft as draft

    width = int(meta.get("width", 1080))
    height = int(meta.get("height", 1920))
    fps = int(meta.get("fps", 30))
    p = preset(meta.get("template_used") or meta.get("template") or "")

    trans = _pick(draft.TransitionType, p["transition"])
    v_intro = _pick(draft.IntroType, p["v_intro"])
    filt = _pick(draft.FilterType, p["filter"])
    open_fx = _pick(draft.VideoSceneEffectType, p["open_fx"])
    ambient_fx = _pick(draft.VideoSceneEffectType, p["ambient_fx"])
    t_intro = _pick(draft.TextIntro, p["t_intro"])
    t_outro = _pick(draft.TextOutro, p["t_outro"])
    cta_loop = _pick(draft.TextLoopAnim, p["cta_loop"])
    hook_loop = _pick(draft.TextLoopAnim, p["hook_loop"])
    thai_font = _pick(draft.FontType, p["thai_font"])
    hook_font = _pick(draft.FontType, p["hook_font"])
    cjk_font = _pick(draft.FontType, p["cjk_font"])
    accent = tuple(p["accent_rgb"])

    s = script if script is not None else ScriptFile(width, height, fps, True)
    s.add_track(TrackType.video)
    s.add_track(TrackType.effect, "fx")          # 开场镜头特效轨
    s.add_track(TrackType.effect, "fx_ambient")  # 贯穿氛围特效轨（与开场分轨，避免重叠）
    s.add_track(TrackType.audio)
    s.add_track(TrackType.text, "sub_th")        # 泰文口播字幕（大，主）
    s.add_track(TrackType.text, "sub_zh")        # 中文口播字幕（小，辅）
    s.add_track(TrackType.text, "caption")       # 屏幕大字花字（关键词）
    s.add_track(TrackType.text, "hook")          # 开场钩子
    s.add_track(TrackType.text, "cta")           # 结尾 CTA 按钮

    def _safe(fn) -> None:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            print(f"  [capcut] 跳过一个装饰: {e}", flush=True)

    def _cap(path: str, target: float) -> float:
        mat = _duration(path)
        if mat <= 0:
            return round(target, 3)
        return round(min(target, mat - 0.05), 3)

    def _add_text(text: str, start: float, dur: float, *, size: float,
                  color: tuple, font, y: float, track: str,
                  loop=None, bg_hex: str | None = None, bg_alpha: float = 0.0,
                  border_w: float = 26.0) -> None:
        from pyJianYingDraft import TextBackground

        if not text or dur <= 0:
            return
        kw: dict[str, Any] = dict(
            style=TextStyle(size=size, bold=True, color=color, align=1, max_line_width=0.82),
            border=TextBorder(alpha=0.9, color=(0.0, 0.0, 0.0), width=border_w),
            shadow=TextShadow(alpha=0.55, color=(0.0, 0.0, 0.0),
                              diffuse=18.0, distance=6.0, angle=-45.0),
            clip_settings=ClipSettings(transform_y=y),
        )
        if font is not None:
            kw["font"] = font
        if bg_hex:   # 仅 CTA 用底色按钮；其余字幕无底，融进画面
            kw["background"] = TextBackground(color=bg_hex, alpha=bg_alpha,
                                              round_radius=0.5, height=0.16, width=0.14)
        seg = TextSegment(text, trange(f"{start}s", f"{dur}s"), **kw)
        if t_intro is not None:
            _safe(lambda: seg.add_animation(t_intro, "0.5s"))
        if t_outro is not None:
            _safe(lambda: seg.add_animation(t_outro, "0.4s"))
        if loop is not None:
            _safe(lambda: seg.add_animation(loop))
        s.add_segment(seg, track_name=track)

    total = sum(float(sc.get("seconds", 0) or 0) for sc in scenes)
    t = 0.0
    n = len(scenes)
    for i, sc in enumerate(scenes):
        dur = float(sc.get("seconds", 0) or 0)
        if dur <= 0:
            continue
        clip = sc.get("clip")
        audio = sc.get("audio")
        if clip:
            vdur = _cap(clip, dur)
            vseg = VideoSegment(VideoMaterial(str(clip)), trange(f"{t}s", f"{vdur}s"))
            if filt is not None:
                _safe(lambda v=vseg: v.add_filter(filt, p["filter_intensity"]))
            if v_intro is not None:
                _safe(lambda v=vseg: v.add_animation(v_intro, "0.6s"))
            if trans is not None and i < n - 1:
                _safe(lambda v=vseg: v.add_transition(trans, duration="0.4s"))
            s.add_segment(vseg)
        if audio:
            adur = _cap(audio, dur)
            _safe(lambda: s.add_segment(
                AudioSegment(AudioMaterial(str(audio)), trange(f"{t}s", f"{adur}s"))))

        # 泰文口播字幕（大，主）+ 中文（小，辅）：同进同出、贴该镜时长，无黑底
        narr_th = (sc.get("narration_th") or "").strip()
        narr_zh = (sc.get("narration_zh") or "").strip()
        sub_dur = _cap(audio, dur) if audio else min(dur, 4.0)
        if narr_th:
            _add_text(narr_th, t, sub_dur, size=7.5, color=(1.0, 1.0, 1.0),
                      font=thai_font, y=-0.66, track="sub_th")
        if narr_zh:
            _add_text(narr_zh, t, sub_dur, size=5.2, color=(0.86, 0.86, 0.86),
                      font=cjk_font, y=-0.80, track="sub_zh", border_w=20.0)
        # 屏幕大字花字（关键词）：亮黄、上中、带循环抖动感
        kw_txt = (sc.get("on_screen_text") or "").strip()
        if kw_txt:
            _add_text(kw_txt, t, min(dur, 3.0), size=10.5, color=accent,
                      font=hook_font or thai_font, y=0.40, track="caption", loop=hook_loop)
        t += dur

    # 开场镜头特效（仅第 1 镜前段）
    if open_fx is not None and total > 0:
        _safe(lambda: s.add_effect(open_fx, trange("0s", f"{min(1.2, total)}s"),
                                   track_name="fx"))
    # 贯穿氛围特效（克制）
    if ambient_fx is not None and total > 1.5:
        _safe(lambda: s.add_effect(ambient_fx, trange("0s", f"{total}s"),
                                   track_name="fx_ambient",
                                   params=[p.get("ambient_intensity", 30.0)]))

    # 钩子：开头顶部大字，闪烁吸睛
    hook = (meta.get("hook") or "").strip()
    if hook and total > 0:
        _add_text(hook, 0.0, min(2.6, total), size=11.5, color=(1.0, 1.0, 1.0),
                  font=hook_font or thai_font, y=0.72, track="hook", loop=hook_loop)
    # CTA：结尾红色按钮，心跳/闪烁脉冲
    cta = (meta.get("cta") or "").strip()
    if cta and total > 1:
        cta_dur = min(4.2, total)
        _add_text(cta, max(total - cta_dur, 0.0), cta_dur, size=8.0, color=(1.0, 1.0, 1.0),
                  font=thai_font, y=-0.40, track="cta", loop=cta_loop,
                  bg_hex="#FE2C55", bg_alpha=0.96, border_w=14.0)

    return s
