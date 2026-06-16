"""导出可在 剪映 / CapCut 桌面端继续精修的草稿 (draft_content.json)。

成片渲染（final.mp4）由 FFmpeg 在 Linux 上完成（mixer.py + subtitles.py），原生观感的
卡拉OK字幕/钩子/CTA 已经烧进画面。本模块额外提供"原生可编辑工程"路径——把分镜片段、
配音、花字按时间轴写成剪映草稿，并**预置好转场 / 入场动画 / 滤镜 / 圆角花字 / CTA 按钮**，
你在自己电脑的 剪映/CapCut 打开后基本已经装饰好，点导出即可拿到平台原生级质感。

注意：CapCut/剪映 的转场·贴纸·特效是按资产 id 引用的，只有在桌面端 App 里才会真正渲染，
所以这条路径的"成品 mp4"需要在 App 内点一次导出（Linux 无界面环境无法直接烘焙这些原生特效）。

装饰按"爆款结构"分预设（DECORATION_PRESETS），不同结构用不同转场/动画/滤镜，避免同质化。
"""

from __future__ import annotations

from pathlib import Path

from . import ffmpeg_utils as ff
from .config import TaskConfig
from .script_model import Script

# 每个爆款结构一套装饰预设：转场 / 视频入场动画 / 滤镜 / 花字入场·出场。
# 用「子串」而不是写死枚举名——pyJianYingDraft 的枚举名是中文，按子串匹配更稳，找不到回退首个。
_DEFAULT_PRESET: dict = {
    "transition": ["叠化", "叠", "闪黑", "闪"],
    "v_intro": ["轻微放大", "放大", "渐显"],
    "filter": ["清晰", "通透", "明亮", "奶油"],
    "filter_intensity": 20.0,
    "t_intro": ["弹入", "放大", "渐显"],
    "t_outro": ["渐隐", "缩小"],
}
DECORATION_PRESETS: dict[str, dict] = {
    # 工厂溯源(B2B)：克制、可信，柔和叠化 + 轻微推近 + 通透质感滤镜
    "factory_tour": {**_DEFAULT_PRESET, "transition": ["叠化", "横向拉伸", "推近", "叠"],
                     "filter": ["清晰", "通透", "质感"], "filter_intensity": 16.0,
                     "t_intro": ["放大", "弹入"], "t_outro": ["渐隐", "缩小"]},
    # 老板出镜(B2B)：真实、口播感，花字打字机入场、几乎不加滤镜
    "founder_direct": {**_DEFAULT_PRESET, "t_intro": ["打字机", "弹入"],
                       "filter_intensity": 10.0},
    # 前后对比：强冲击，闪白/闪黑转场 + 放大花字
    "before_after": {**_DEFAULT_PRESET, "transition": ["闪白", "闪黑", "叠化"],
                     "t_intro": ["放大", "弹入"]},
    # 解压/ASMR：丝滑叠化 + 奶油通透
    "satisfying_asmr": {**_DEFAULT_PRESET, "transition": ["叠化", "云", "叠"],
                        "filter": ["奶油", "通透", "清晰"]},
}


def _preset(template_used: str) -> dict:
    return DECORATION_PRESETS.get((template_used or "").strip(), _DEFAULT_PRESET)


def _pick(enum, subs: list[str]):
    """按子串优先级在枚举里挑一个成员，全找不到则回退到第一个（避免崩）。"""
    for s in subs:
        for member in enum:
            if s in member.name:
                return member
    return list(enum)[0]


def export(script: Script, cfg: TaskConfig, work: Path, draft_dir: Path) -> Path:
    from pyJianYingDraft import (
        AudioMaterial,
        AudioSegment,
        ClipSettings,
        FilterType,
        IntroType,
        ScriptFile,
        TextBackground,
        TextIntro,
        TextOutro,
        TextSegment,
        TextStyle,
        TrackType,
        TransitionType,
        VideoMaterial,
        VideoSegment,
        trange,
    )

    p = _preset(script.template_used or script.template)
    trans = _pick(TransitionType, p["transition"])
    v_intro = _pick(IntroType, p["v_intro"])
    filt = _pick(FilterType, p["filter"])
    t_intro = _pick(TextIntro, p["t_intro"])
    t_outro = _pick(TextOutro, p["t_outro"])

    s = ScriptFile(cfg.width, cfg.height, cfg.fps, True)
    s.add_track(TrackType.video)
    s.add_track(TrackType.audio)
    # 三条独立文字轨：分镜花字 / 钩子 / CTA，避免时间重叠（剪映同轨不允许重叠）
    s.add_track(TrackType.text, "caption")
    s.add_track(TrackType.text, "hook")
    s.add_track(TrackType.text, "cta")

    def _safe(fn) -> None:
        """装饰是尽力而为的：某个特效/动画在当前 pyJianYingDraft 版本不可用时跳过，不让整份草稿崩。"""
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            print(f"  [capcut] 跳过一个装饰: {e}", flush=True)

    def _cap(path: Path, target: float) -> float:
        """把片段时长夹到不超过素材真实时长（留 50ms 余量，避开 µs 取整溢出）。"""
        mat = ff.duration(path)
        if mat <= 0:
            return target
        return round(min(target, mat - 0.05), 3)

    def _add_text(text: str, start: float, dur: float, *, size: float,
                  color: tuple[float, float, float], bg_hex: str, bg_alpha: float,
                  y: float, round_r: float = 0.28, track: str = "caption") -> None:
        if not text or dur <= 0:
            return
        seg = TextSegment(
            text,
            trange(f"{start}s", f"{dur}s"),
            style=TextStyle(size=size, bold=True, color=color, align=1, max_line_width=0.82),
            background=TextBackground(color=bg_hex, alpha=bg_alpha, round_radius=round_r,
                                      height=0.16, width=0.14),
            clip_settings=ClipSettings(transform_y=y),
        )
        _safe(lambda: seg.add_animation(t_intro, "0.5s"))
        _safe(lambda: seg.add_animation(t_outro, "0.4s"))
        s.add_segment(seg, track_name=track)

    scenes = list(script.scenes)
    total = sum(float(sc.seconds) for sc in scenes)
    t = 0.0
    for i, scene in enumerate(scenes):
        vid = work / "clips" / f"scene_{scene.index:02d}.mp4"
        aud = work / "audio" / f"a_{scene.index:02d}.mp3"
        dur = float(scene.seconds)
        if vid.exists():
            vdur = _cap(vid, dur)
            vseg = VideoSegment(VideoMaterial(str(vid)), trange(f"{t}s", f"{vdur}s"))
            _safe(lambda v=vseg: v.add_filter(filt, p["filter_intensity"]))
            _safe(lambda v=vseg: v.add_animation(v_intro, "0.6s"))
            if i < len(scenes) - 1:
                _safe(lambda v=vseg: v.add_transition(trans, duration="0.4s"))
            s.add_segment(vseg)
        if aud.exists():
            adur = _cap(aud, dur)
            s.add_segment(AudioSegment(AudioMaterial(str(aud)), trange(f"{t}s", f"{adur}s")))
        # 分镜大字（花字）：白字 + 半透明圆角黑底，放下三分之一
        _add_text(scene.on_screen_text, t, min(dur, 3.2), size=8.0, color=(1.0, 1.0, 1.0),
                  bg_hex="#000000", bg_alpha=0.55, y=-0.78)
        t += dur

    # 钩子：开头大字，放上三分之一
    if script.hook:
        _add_text(script.hook, 0.0, min(2.6, total or 2.6), size=11.0, color=(1.0, 1.0, 1.0),
                  bg_hex="#000000", bg_alpha=0.42, y=0.66, track="hook")
    # CTA：结尾红色按钮，放下方（高于字幕）
    if script.cta and total > 1:
        cta_dur = min(4.2, total)
        _add_text(script.cta, max(total - cta_dur, 0.0), cta_dur, size=8.5,
                  color=(1.0, 1.0, 1.0), bg_hex="#FE2C55", bg_alpha=0.96, y=-0.6, round_r=0.5,
                  track="cta")

    draft_dir.mkdir(parents=True, exist_ok=True)
    s.dump(str(draft_dir / "draft_content.json"))
    (draft_dir / "HOW_TO_OPEN.txt").write_text(
        "把 draft_content.json 放进 剪映/CapCut 的一个草稿文件夹中（替换其 draft_content.json），\n"
        "或用 pyJianYingDraft 的 DraftFolder 写入你的草稿库目录后，在桌面端打开继续精修。\n"
        "草稿已预置：转场 / 入场动画 / 滤镜 / 圆角花字 / 红色 CTA 按钮，打开后点导出即可。\n"
        "若泰文显示为方块，在 CapCut 里把文字字体换成任一支持泰文的字体（如 Kanit/Sarabun），\n"
        "或直接用 CapCut 的『自动字幕』识别配音生成口播字幕。\n",
        encoding="utf-8",
    )
    return draft_dir
