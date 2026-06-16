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
    words: list[tuple[float, float, str]] | None = None


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


# 泰文组合字符：声调符/上下元音/附标，绝不能作为一个切片的开头（必须跟随它的辅音基字）
_THAI_FOLLOW = set(
    "\u0e31"          # ไม้หันอากาศ ◌ั
    "\u0e34\u0e35\u0e36\u0e37\u0e38\u0e39\u0e3a"  # สระ อิ อี อึ อื อุ อู / พินทุ
    "\u0e47\u0e48\u0e49\u0e4a\u0e4b\u0e4c\u0e4d\u0e4e"  # ◌็ วรรณยุกต์ ทัณฑฆาต นิคหิต ยามักการ
    "\u0e33"          # สระ อำ（跟随基字）
)
# 泰文前置元音：要附到“后一个”辅音上（เ แ โ ใ ไ）
_THAI_LEAD = set("\u0e40\u0e41\u0e42\u0e43\u0e44")


def _clusters(text: str) -> list[str]:
    """把字符串切成“字素簇”：泰文声调/元音符号永远跟随其辅音基字，前置元音并入后一辅音。

    这样按字数切短句 / 做卡拉OK高亮时，绝不会把 ตั้ง 切成 ต + ั + ้ + ง 这种乱码孤儿符号。
    优先用 `regex` 的 \\X（若安装），但它会拆开泰文前置元音，所以泰文场景仍走自带切分。
    """
    if not text:
        return []
    out: list[str] = []
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        # 前置元音 + 后一个辅音 当作一簇的起点
        if ch in _THAI_LEAD and i + 1 < n:
            j = i + 2
        else:
            j = i + 1
        # 吸收后续所有“跟随型”组合符号（泰文声调/元音 + 通用变音符）
        while j < n and (text[j] in _THAI_FOLLOW or (0x0300 <= ord(text[j]) <= 0x036F)):
            j += 1
        out.append(text[i:j])
        i = j
    return out


def _clen(text: str) -> int:
    return len(_clusters(text))


# 拉丁字母/数字：连续的当作一个不可分原子（避免把 30,000 / CO2 / OEM / MOQ / 100 切散）
_ATOM_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
)
# 只有夹在两个原子字符之间时才并入原子（如千分位逗号、小数点、百分号）
_ATOM_JOIN = set(",.%/+-")


def _atoms(text: str) -> list[str]:
    """把文本切成原子单元：连续的拉丁字母/数字（含其中的 ,.%/+-）合成一个不可分原子，
    其余按泰文字素簇切。这样按长度切短句时不会把数字/英文缩写切散成 ",000" / "CO2"→"2"。"""
    cl = _clusters(text)
    out: list[str] = []
    n = len(cl)
    i = 0
    while i < n:
        c = cl[i]
        if len(c) == 1 and c in _ATOM_CHARS:
            run = c
            j = i + 1
            while j < n:
                nx = cl[j]
                if len(nx) == 1 and nx in _ATOM_CHARS:
                    run += nx
                    j += 1
                elif (len(nx) == 1 and nx in _ATOM_JOIN and j + 1 < n
                      and len(cl[j + 1]) == 1 and cl[j + 1] in _ATOM_CHARS):
                    run += nx
                    j += 1
                else:
                    break
            out.append(run)
            i = j
        else:
            out.append(c)
            i += 1
    return out


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


def words_from_script(
    scenes, narr_durs: list[float], field: str = "narration"
) -> list[tuple[float, float, str]]:
    """无空格语言(泰/中/日)：直接用脚本里写好的旁白做字幕，按分镜时长定位。

    避免 whisper 转写无空格语言时出错导致字幕乱码——我们已经知道每句台词的准确文本，
    只需把它放到对应分镜的音频时间段里，后续 `_chunk_nospace` 会按字素簇切成短句弹入。
    `field` 可选 narration（泰语，主）或 narration_zh（中文，副）做中泰双语字幕。
    """
    out: list[tuple[float, float, str]] = []
    t = 0.0
    for s, dur in zip(scenes, narr_durs):
        raw = s.narration_zh if field == "narration_zh" else s.narration
        text = (raw or "").strip()
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
            chunks.append(Chunk(buf[0][0], buf[-1][1], " ".join(x[2] for x in buf), list(buf)))
            buf = []
    if buf:
        chunks.append(Chunk(buf[0][0], buf[-1][1], " ".join(x[2] for x in buf), list(buf)))
    return chunks


def _split_long(words: list[tuple[float, float, str]], max_chars: int) -> list[tuple[float, float, str]]:
    """把过长的 token（常见于整句时间戳）按“字素簇”等分，并线性插值时间。

    按字素簇而不是 code point 切，泰文的声调/元音符号永远跟着辅音基字，不会切出乱码孤儿。
    """
    out: list[tuple[float, float, str]] = []
    for s, e, t in words:
        t = t.replace(" ", "")
        atoms = [(a, _clen(a)) for a in _atoms(t)]
        total = sum(ln for _, ln in atoms)
        if total <= max_chars or total == 0:
            if t:
                out.append((s, e, t))
            continue
        # 贪心装箱：累积原子到 max_chars 才换行；绝不切开一个原子（数字/英文缩写）。
        # 时间按“字素簇位置”线性插值，长短句节奏更准。
        cur = ""
        cur_len = 0
        start = 0
        consumed = 0
        for a, ln in atoms:
            if cur and cur_len + ln > max_chars:
                out.append((s + (e - s) * start / total,
                            s + (e - s) * consumed / total, cur))
                cur = ""
                cur_len = 0
                start = consumed
            cur += a
            cur_len += ln
            consumed += ln
        if cur:
            out.append((s + (e - s) * start / total, e, cur))
    return out


def _chunk_nospace(words: list[tuple[float, float, str]], max_chars: int) -> list[Chunk]:
    """泰/中/日等无空格语言：按字素簇数聚合成短句、字间不插空格（否则字幕会断成豆腐块）。"""
    toks = _split_long(words, max_chars)
    chunks: list[Chunk] = []
    buf: list[tuple[float, float, str]] = []
    cnt = 0
    for s, e, t in toks:
        buf.append((s, e, t))
        cnt += _clen(t)
        if cnt >= max_chars:
            chunks.append(Chunk(buf[0][0], buf[-1][1], "".join(x[2] for x in buf), list(buf)))
            buf = []
            cnt = 0
    if buf:
        chunks.append(Chunk(buf[0][0], buf[-1][1], "".join(x[2] for x in buf), list(buf)))
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


def _chunk_secondary(
    words: list[tuple[float, float, str]], max_chars: int, nospace: bool, max_words: int
) -> list[Chunk]:
    """第二语言(辅助字幕)分句：保持每个输入分镜的时间段独立、不跨镜合并，过长才再切。

    这样中文辅助字幕会和主泰文字幕逐镜同步切换，而不是整段挤成一行。
    """
    chunks: list[Chunk] = []
    if nospace:
        for s, e, t in _split_long(words, max_chars):
            if t.strip():
                chunks.append(Chunk(s, e, t, [(s, e, t)]))
        return chunks
    for s, e, t in words:
        toks = t.split()
        if not toks:
            continue
        n = max(1, math.ceil(len(toks) / max_words))
        step = (e - s) / n
        for i in range(n):
            piece = " ".join(toks[i * max_words:(i + 1) * max_words])
            if piece:
                chunks.append(Chunk(s + i * step, s + (i + 1) * step, piece, None))
    return chunks


def _karaoke_units(chunk: Chunk, nospace: bool, group: int) -> list[tuple[int, str]]:
    """把一句字幕拆成卡拉OK高亮单元，返回 [(持续厘秒, 文本)]，让词/字随声音逐个点亮。"""
    dur = max(chunk.end - chunk.start, 0.1)
    if nospace:
        cl = _clusters(chunk.text)
        pieces = ["".join(cl[i:i + group]) for i in range(0, len(cl), group)] or [chunk.text]
        cs = max(1, round(dur * 100 / len(pieces)))
        return [(cs, p) for p in pieces]
    words = [w for w in (chunk.words or []) if w[2].strip()]
    if len(words) >= 2:
        return [(max(1, round((e - s) * 100)), t.strip()) for s, e, t in words]
    toks = chunk.text.split() or [chunk.text]
    cs = max(1, round(dur * 100 / len(toks)))
    return [(cs, t) for t in toks]


def render_ass(
    words: list[tuple[float, float, str]],
    total: float,
    cfg: TaskConfig,
    out_ass: Path,
    hook: str = "",
    cta: str = "",
    words2: list[tuple[float, float, str]] | None = None,
) -> tuple[Path, str | None]:
    """从词级时间戳渲染原生风格 ASS（A/B 多版本复用同一份 words，只换 hook/cta）。

    设计对标 TikTok/Reels 真实爆款字幕：
    - 正文：Montserrat 粗体、白字+黑描边+柔和阴影、短句(2~3词)逐句弹入(pop-in)、下三分之一；
    - 钩子：纯白粗体大字+厚黑描边(无彩色色块)，上三分之一，前 ~2.6s；
    - CTA：左下角 TikTok 红圆角按钮样式(模拟原生购物按钮)，结尾 ~4.5s 弹入。
    - words2：可选第二语言（中泰双语时=中文），渲染成主字幕正下方一行更小的辅助字幕。
    尺寸/边距按分辨率自适应(基准 720x1280)。
    """
    sub = cfg.get("subtitles", default={}) or {}
    nospace = _is_nospace(cfg.language)
    if nospace:
        chunks = _chunk_nospace(words, int(sub.get("max_chars", 16)))
    else:
        chunks = _chunk(words, int(sub.get("max_words", 3)))

    font_name, fontsdir = _font_setup(sub.get("font", "assets/fonts/Montserrat-Bold.ttf"))
    w, h = cfg.width, cfg.height
    sf = w / 720.0   # 横向缩放因子
    hf = h / 1280.0  # 纵向缩放因子

    white = "&H00FFFFFF"
    accent = sub.get("accent_color", "&H0000E5FF")    # 卡拉OK高亮(默认亮黄, ASS 为 BGR)
    box = sub.get("box_color", "&H59000000")           # 字幕半透明黑底(药丸)
    box_hook = "&H40000000"                             # 钩子底色(更透)
    shadow_c = "&H64000000"
    cta_red = sub.get("cta_color", "&H00552CFE")        # TikTok 红 #FE2C55 (BGR)
    ko_group = max(1, int(sub.get("karaoke_chars", 2)))

    cap_sz = int(sub.get("font_size", round(52 * sf)))
    cap_pad = max(3, round(8 * sf))     # BorderStyle=3 时 Outline 充当药丸内边距
    cap_sh = max(1, round(2 * sf))
    cap_mv = int(sub.get("margin_v", round(300 * hf)))

    # 第二语言（中泰双语：中文辅助字幕）——更小、贴在主字幕正下方
    sub2_font_name = sub.get("secondary_font", "WenQuanYi Zen Hei")  # 中文需 CJK 字体
    sub2_lang = (sub.get("secondary_lang", "zh") or "zh").strip().lower()
    sub2_sz = int(sub.get("secondary_font_size", round(33 * sf)))
    sub2_pad = max(2, round(6 * sf))
    sub2_mv = max(round(60 * hf), cap_mv - round((cap_sz + 26) * hf))

    hook_sz = round(58 * sf)
    hook_pad = max(4, round(11 * sf))
    hook_mv = round(248 * hf)

    cta_sz = round(40 * sf)
    cta_pad = max(5, round(13 * sf))
    cta_ml = round(40 * sf)
    cta_mv = round(172 * hf)

    fmt = (
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding"
    )
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 1
ScaledBorderAndShadow: yes

[V4+ Styles]
{fmt}
Style: Caps,{font_name},{cap_sz},{accent},{white},{box},{shadow_c},1,0,0,0,100,100,0,0,3,{cap_pad},{cap_sh},2,60,60,{cap_mv},1
Style: Sub2,{sub2_font_name},{sub2_sz},{white},{white},{box},{shadow_c},0,0,0,0,100,100,0,0,3,{sub2_pad},{cap_sh},2,60,60,{sub2_mv},1
Style: Hook,{font_name},{hook_sz},{white},{white},{box_hook},{shadow_c},1,0,0,0,100,100,0,0,3,{hook_pad},{cap_sh},8,70,70,{hook_mv},1
Style: Cta,{font_name},{cta_sz},{white},{white},{cta_red},&H00000000,1,0,0,0,100,100,0,0,3,{cta_pad},0,2,{cta_ml},60,{cta_mv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    cap_anim = r"{\fad(50,40)\fscx86\fscy86\t(0,110,\fscx100\fscy100)}"
    sub2_anim = r"{\fad(60,40)}"
    hook_anim = r"{\fad(60,140)\fscx88\fscy88\t(0,150,\fscx100\fscy100)}"
    cta_anim = r"{\fad(150,0)\fscx80\fscy80\t(0,170,\fscx108\fscy108)\t(170,340,\fscx100\fscy100)}"

    lines = [header]
    sep = "" if nospace else " "
    for c in chunks:
        units = _karaoke_units(c, nospace, ko_group)
        body = "".join(f"{{\\k{cs}}}{_esc(t)}{sep}" for cs, t in units).rstrip()
        if not body:
            continue
        lines.append(
            f"Dialogue: 0,{_fmt_ts(c.start)},{_fmt_ts(c.end)},Caps,,0,0,0,,{cap_anim}{body}"
        )
    # 第二语言（中泰双语：中文辅助字幕，主字幕正下方一行，逐镜与泰文同步）
    if words2:
        nospace2 = _is_nospace(sub2_lang)
        chunks2 = _chunk_secondary(
            words2,
            int(sub.get("max_chars_secondary", 18)),
            nospace2,
            int(sub.get("max_words_secondary", 6)),
        )
        for c in chunks2:
            txt = _esc(c.text)
            if not txt:
                continue
            lines.append(
                f"Dialogue: 0,{_fmt_ts(c.start)},{_fmt_ts(c.end)},Sub2,,0,0,0,,{sub2_anim}{txt}"
            )
    if hook:
        lines.append(
            f"Dialogue: 1,{_fmt_ts(0)},{_fmt_ts(min(2.6, max(total, 0.1)))},Hook,,0,0,0,,"
            f"{hook_anim}{_esc(hook)}"
        )
    if cta and total > 1:
        lines.append(
            f"Dialogue: 1,{_fmt_ts(max(total - 4.5, 0))},{_fmt_ts(total)},Cta,,0,0,0,,"
            f"{cta_anim}{_esc(cta)}"
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
