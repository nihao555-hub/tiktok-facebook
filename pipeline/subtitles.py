"""字幕：用 faster-whisper 对配音做词级时间戳，生成 TikTok 风格逐词/短句 ASS 字幕，
并把"前 3 秒大钩子"和"结尾 CTA"也作为大字事件写进同一个 ASS（避免 drawtext 转义/emoji 问题）。
"""

from __future__ import annotations

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
        for w in (seg.words or []):
            txt = (w.word or "").strip()
            if txt:
                words.append((float(w.start), float(w.end), txt))
    return words


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


def _font_setup(font: str) -> tuple[str, str | None]:
    """返回 (FontName, fontsdir)。font 可以是字体名或 .ttf/.otf 路径。"""
    p = Path(font)
    if not p.is_absolute():
        p = REPO_ROOT / font
    if p.exists() and p.suffix.lower() in {".ttf", ".otf"}:
        return p.stem, str(p.parent)
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
    """从已有词级时间戳渲染 ASS（A/B 多版本可复用同一份 words，只换 hook/cta）。"""
    sub = cfg.get("subtitles", default={}) or {}
    chunks = _chunk(words, int(sub.get("max_words", 3)))

    font_name, fontsdir = _font_setup(sub.get("font", "DejaVu Sans"))
    size = int(sub.get("font_size", 64))
    primary = sub.get("primary_color", "&H00FFFFFF")
    outline = "&H00000000"
    margin_v = int(sub.get("margin_v", 320))
    w, h = cfg.width, cfg.height
    big = int(size * 1.25)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 1
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Caps,{font_name},{size},{primary},{outline},&H64000000,1,0,1,4,1,2,60,60,{margin_v}
Style: Hook,{font_name},{big},&H0000FFFF,{outline},&H64000000,1,0,1,5,1,8,60,60,260
Style: Cta,{font_name},{big},&H00FFFFFF,{outline},&H64000000,1,0,1,5,2,5,60,60,0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for c in chunks:
        lines.append(
            f"Dialogue: 0,{_fmt_ts(c.start)},{_fmt_ts(c.end)},Caps,,0,0,0,,"
            f"{{\\fad(60,60)}}{_esc(c.text)}"
        )
    if hook:
        lines.append(
            f"Dialogue: 1,{_fmt_ts(0)},{_fmt_ts(min(3.0, max(total, 0.1)))},Hook,,0,0,0,,"
            f"{{\\fad(0,150)}}{_esc(hook)}"
        )
    if cta and total > 1:
        lines.append(
            f"Dialogue: 1,{_fmt_ts(max(total - 4, 0))},{_fmt_ts(total)},Cta,,0,0,0,,"
            f"{{\\fad(150,0)}}{_esc(cta)}"
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
