"""字幕：用 faster-whisper 对配音做词级时间戳，生成 TikTok 风格逐词/短句 ASS 字幕，
并把"前 3 秒大钩子"和"结尾 CTA"也作为大字事件写进同一个 ASS（避免 drawtext 转义/emoji 问题）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from . import ffmpeg_utils as ff
from .config import REPO_ROOT, TaskConfig


@dataclass
class Chunk:
    start: float
    end: float
    text: str


def _fmt_ts(t: float) -> str:
    t = max(t, 0.0)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    cs = int(round((t - int(t)) * 100))
    if cs == 100:
        cs = 0
        s += 1
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def transcribe_words(audio: Path, model_size: str, language: str) -> list[tuple[float, float, str]]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        str(audio), language=language or None, word_timestamps=True, vad_filter=True
    )
    words: list[tuple[float, float, str]] = []
    for seg in segments:
        seg_words = seg.words or []
        got = False
        for w in seg_words:
            txt = (w.word or "").strip()
            if txt:
                words.append((float(w.start), float(w.end), txt))
                got = True
        # 泰语/中文等无空格语言常拿不到词级时间戳，退化为整句时间戳，后面再按字数切分
        if not got:
            txt = (seg.text or "").strip()
            if txt:
                words.append((float(seg.start), float(seg.end), txt))
    return words


# 无空格分词的语言（泰/中/日/老挝/高棉/缅甸）：字幕按字数切分、不插空格
_NOSPACE_LANGS = {"th", "zh", "ja", "lo", "km", "my"}


def is_nospace(language: str) -> bool:
    return (language or "").strip().lower()[:2] in _NOSPACE_LANGS


# 兼容内部旧名
_is_nospace = is_nospace


def words_from_script(scenes, narr_durs: list[float]) -> list[tuple[float, float, str]]:
    """无空格语言(泰/中/日)：直接用脚本里写好的旁白做字幕，按分镜时长定位。

    避免 whisper 转写无空格语言时出错导致字幕乱码——我们已经知道每句台词的准确文本，
    只需把它放到对应分镜的音频时间段里，后续 `_chunk_nospace` 会按字数切成短句弹入。
    """
    out: list[tuple[float, float, str]] = []
    t = 0.0
    for s, dur in zip(scenes, narr_durs):
        text = (s.narration or "").strip()
        seconds = float(s.seconds or dur)
        if text:
            span = max(min(float(dur), seconds), 0.3)
            out.append((t, t + span, text))
        t += seconds
    return out


def _chunk(words: list[tuple[float, float, str]], max_words: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    buf: list[tuple[float, float, str]] = []
    for w in words:
        buf.append(w)
        ends_sentence = w[2].endswith((".", "!", "?", ",", "。", "！", "？", "，"))
        if len(buf) >= max_words or ends_sentence:
            chunks.append(Chunk(buf[0][0], buf[-1][1], " ".join(x[2] for x in buf)))
            buf = []
    if buf:
        chunks.append(Chunk(buf[0][0], buf[-1][1], " ".join(x[2] for x in buf)))
    return chunks


def _split_long(words: list[tuple[float, float, str]], max_chars: int) -> list[tuple[float, float, str]]:
    """把过长的 token（常见于整句时间戳）按字数等分，并线性插值时间。"""
    out: list[tuple[float, float, str]] = []
    for s, e, t in words:
        t = t.replace(" ", "")
        if len(t) <= max_chars:
            if t:
                out.append((s, e, t))
            continue
        n = max(1, math.ceil(len(t) / max_chars))
        step = (e - s) / n
        for i in range(n):
            piece = t[i * max_chars:(i + 1) * max_chars]
            if piece:
                out.append((s + i * step, s + (i + 1) * step, piece))
    return out


def _chunk_nospace(words: list[tuple[float, float, str]], max_chars: int) -> list[Chunk]:
    """泰/中/日等无空格语言：按字数聚合成短句、字间不插空格（否则字幕会断成豆腐块）。"""
    toks = _split_long(words, max_chars)
    chunks: list[Chunk] = []
    buf: list[tuple[float, float, str]] = []
    cnt = 0
    for s, e, t in toks:
        buf.append((s, e, t))
        cnt += len(t)
        if cnt >= max_chars:
            chunks.append(Chunk(buf[0][0], buf[-1][1], "".join(x[2] for x in buf)))
            buf = []
            cnt = 0
    if buf:
        chunks.append(Chunk(buf[0][0], buf[-1][1], "".join(x[2] for x in buf)))
    return chunks


def _font_setup(font: str) -> tuple[str, str | None]:
    """返回 (FontName, fontsdir)。font 可以是字体名或 .ttf/.otf 路径。

    传路径时用真实的字体家族名（不是文件名）作为 FontName，否则 libass 匹配不到会回退到
    DejaVu，字幕就不是我们想要的原生粗体了。
    """
    p = Path(font)
    if not p.is_absolute():
        p = REPO_ROOT / font
    if p.exists() and p.suffix.lower() in {".ttf", ".otf"}:
        family = p.stem
        try:
            from PIL import ImageFont

            family = ImageFont.truetype(str(p), 32).getname()[0] or p.stem
        except Exception:
            pass
        return family, str(p.parent)
    return font, None


def _esc(text: str) -> str:
    return text.replace("\n", " ").replace("{", "(").replace("}", ")").strip()


def render_ass(
    words: list[tuple[float, float, str]],
    total: float,
    cfg: TaskConfig,
    out_ass: Path,
    hook: str = "",
    cta: str = "",
) -> tuple[Path, str | None]:
    """从词级时间戳渲染原生风格 ASS（A/B 多版本复用同一份 words，只换 hook/cta）。

    设计对标 TikTok/Reels 真实爆款字幕：
    - 正文：Montserrat 粗体、白字+黑描边+柔和阴影、短句(2~3词)逐句弹入(pop-in)、下三分之一；
    - 钩子：纯白粗体大字+厚黑描边(无彩色色块)，上三分之一，前 ~2.6s；
    - CTA：左下角 TikTok 红圆角按钮样式(模拟原生购物按钮)，结尾 ~4.5s 弹入。
    尺寸/边距按分辨率自适应(基准 720x1280)。
    """
    sub = cfg.get("subtitles", default={}) or {}
    if _is_nospace(cfg.language):
        chunks = _chunk_nospace(words, int(sub.get("max_chars", 16)))
    else:
        chunks = _chunk(words, int(sub.get("max_words", 3)))

    font_name, fontsdir = _font_setup(sub.get("font", "assets/fonts/Montserrat-Bold.ttf"))
    w, h = cfg.width, cfg.height
    sf = w / 720.0   # 横向缩放因子
    hf = h / 1280.0  # 纵向缩放因子

    cap_sz = int(sub.get("font_size", round(54 * sf)))
    cap_out = max(2, round(3 * sf))
    cap_sh = max(1, round(1 * sf))
    cap_mv = int(sub.get("margin_v", round(300 * hf)))
    primary = sub.get("primary_color", "&H00FFFFFF")
    black = "&H00000000"
    shadow = "&H96000000"

    hook_sz = round(60 * sf)
    hook_out = max(2, round(4 * sf))
    hook_mv = round(250 * hf)

    cta_sz = round(40 * sf)
    cta_pad = max(4, round(8 * sf))
    cta_ml = round(44 * sf)
    cta_mv = round(150 * hf)
    cta_red = "&H00552CFE"  # TikTok 红 #FE2C55 (ASS 为 BGR)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 1
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Caps,{font_name},{cap_sz},{primary},{black},{shadow},1,0,1,{cap_out},{cap_sh},2,70,70,{cap_mv}
Style: Hook,{font_name},{hook_sz},{primary},{black},{shadow},1,0,1,{hook_out},2,8,80,80,{hook_mv}
Style: Cta,{font_name},{cta_sz},{primary},{cta_red},&H00000000,1,0,3,{cta_pad},0,1,{cta_ml},70,{cta_mv}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    cap_tag = r"{\fad(70,50)\fscx84\fscy84\t(0,120,\fscx100\fscy100)}"
    hook_tag = r"{\fad(60,140)\fscx88\fscy88\t(0,150,\fscx100\fscy100)}"
    cta_tag = r"{\fad(160,0)\fscx92\fscy92\t(0,150,\fscx100\fscy100)}"

    lines = [header]
    for c in chunks:
        lines.append(
            f"Dialogue: 0,{_fmt_ts(c.start)},{_fmt_ts(c.end)},Caps,,0,0,0,,"
            f"{cap_tag}{_esc(c.text)}"
        )
    if hook:
        lines.append(
            f"Dialogue: 1,{_fmt_ts(0)},{_fmt_ts(min(2.6, max(total, 0.1)))},Hook,,0,0,0,,"
            f"{hook_tag}{_esc(hook)}"
        )
    if cta and total > 1:
        lines.append(
            f"Dialogue: 1,{_fmt_ts(max(total - 4.5, 0))},{_fmt_ts(total)},Cta,,0,0,0,,"
            f"{cta_tag}{_esc(cta)}"
        )
    out_ass.parent.mkdir(parents=True, exist_ok=True)
    out_ass.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_ass, fontsdir


def build_ass(
    audio: Path,
    cfg: TaskConfig,
    out_ass: Path,
    hook: str = "",
    cta: str = "",
) -> tuple[Path, str | None]:
    """便捷封装：转写音频 + 渲染 ASS。"""
    sub = cfg.get("subtitles", default={}) or {}
    words = transcribe_words(audio, sub.get("whisper_model", "small"), cfg.language)
    return render_ass(words, ff.duration(audio), cfg, out_ass, hook, cta)
