"""流水线编排 CLI。

用法:
    python -m pipeline.run --config config.yaml
    python -m pipeline.run --config config.yaml --no-capcut   # 不导出剪映草稿
    python -m pipeline.run --config config.yaml --publish     # 强制按 config 发布

产物默认在 output/<project>/ 下：
    final.mp4              主成片
    variant_*.mp4          A/B 多版本
    script.json            脚本
    capcut_draft/          可在剪映/CapCut 打开继续精修的草稿
"""

from __future__ import annotations

import argparse
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import ffmpeg_utils as ff
from . import mixer, subtitles, templates
from .config import REPO_ROOT, Secrets, TaskConfig
from .providers import clipgen, llm, tts
from .script_model import Script


def _prepare_assets(script: Script, cfg: TaskConfig, secrets: Secrets, work: Path):
    """配音(决定每个分镜时长，并发) -> 生成片段(并发) -> 拼接底片 -> 抽人声 -> 转写。"""
    audio_dir = work / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    scenes = script.scenes
    n = len(scenes)

    def _tts_one(s) -> tuple[int, Path, float]:
        existing = (audio_dir / f"a_{s.index:02d}").with_suffix(".mp3")
        if existing.exists() and existing.stat().st_size > 512:
            dur = ff.duration(existing)
            print(f"  [配音 {s.index + 1}/{n}] 复用 {dur:.1f}s", flush=True)
            return s.index, existing, dur
        ap = tts.synth(s.narration, audio_dir / f"a_{s.index:02d}", cfg, secrets)
        dur = ff.duration(ap)
        print(f"  [配音 {s.index + 1}/{n}] 完成 {dur:.1f}s", flush=True)
        return s.index, ap, dur

    # ElevenLabs 低层套餐并发上限低，限 2；EdgeTTS 等免费接口可放宽
    tts_workers = 2 if (secrets.tts_provider or "edge").lower() == "elevenlabs" else 4
    by_idx: dict[int, tuple[Path, float]] = {}
    with ThreadPoolExecutor(max_workers=min(n, tts_workers)) as ex:
        for idx, ap, dur in ex.map(_tts_one, scenes):
            by_idx[idx] = (ap, dur)
    audio_paths: list[Path] = []
    narr_durs: list[float] = []
    for s in scenes:
        ap, dur = by_idx[s.index]
        # 先声后画：分镜时长贴着该句配音的真实长度(配音已裁首尾静音)，只留很小的尾部留白，
        # 避免每镜结尾出现明显空档(听感上像“卡住”)。
        s.seconds = round(max(1.5, dur + 0.18), 3)
        audio_paths.append(ap)
        narr_durs.append(dur)

    video_paths = clipgen.generate_clips(script, cfg, secrets, work / "clips")
    base = mixer.assemble(script, video_paths, audio_paths, cfg, work)
    voice = mixer.extract_voiceover(base, work)

    words: list[tuple[float, float, str]] = []
    words2: list[tuple[float, float, str]] = []
    if cfg.get("subtitles", "enabled", default=True):
        sub = cfg.get("subtitles", default={}) or {}
        if subtitles.is_nospace(cfg.language):
            # 泰/中/日等：用脚本原文做字幕（whisper 对无空格语言易转写出错）
            words = subtitles.words_from_script(script.scenes, narr_durs)
        else:
            words = subtitles.transcribe_words(
                voice, sub.get("whisper_model", "small"), cfg.language
            )
        # 中泰双语：第二行中文辅助字幕（取脚本里每个分镜的 narration_zh）
        if sub.get("bilingual", False) and any(s.narration_zh.strip() for s in scenes):
            words2 = subtitles.words_from_script(script.scenes, narr_durs, field="narration_zh")
    return base, voice, words, words2


def _render_variant(base: Path, words, total, cfg, out: Path, work: Path,
                    hook: str, cta: str, bgm_override: str | None,
                    words2: list | None = None) -> Path:
    fontsdir = None
    ass = None
    if cfg.get("subtitles", "enabled", default=True):
        ass_path = work / f"{out.stem}.ass"
        ass, fontsdir = subtitles.render_ass(
            words, total, cfg, ass_path, hook=hook, cta=cta, words2=words2)
    if ass is None:
        # 没字幕也要能出片：用一个空 ASS
        ass_path = work / f"{out.stem}.ass"
        ass_path.write_text(
            "[Script Info]\nScriptType: v4.00+\n[V4+ Styles]\n[Events]\n", encoding="utf-8"
        )
        ass = ass_path
    return mixer.render_final(base, ass, fontsdir, cfg, out, bgm_override=bgm_override)


def _print_strategy(strategy: dict) -> None:
    bp = strategy.get("buyer_persona") or {}
    print("[0/5] 买家画像 & 策略（gpt-5.5 先当买家画像专家/创意总监思考）：", flush=True)
    print(f"    🎯 买家：{bp.get('who', '')}（{bp.get('role', '')}）| 市场：{strategy.get('market', '')}")
    print(f"    😣 最大痛点：{strategy.get('biggest_pain', '')}")
    print(f"    🪝 钩子角度：{strategy.get('hook_angle', '')}")
    print(f"    ✅ 要展示的硬证据：{strategy.get('proof_to_show', [])}")
    print(f"    📲 促成行动：{strategy.get('decisive_trigger', '')}")
    print(f"    🧩 建议结构：{strategy.get('recommended_template', '')}", flush=True)


def _print_script(script: Script) -> None:
    print(f"    —— gpt-5.5 脚本（hook=\"{script.hook}\" / cta=\"{script.cta}\"）——", flush=True)
    for s in script.scenes:
        face = "🙂正脸" if s.show_face else "🚫不出正脸"
        print(f"    #{s.index + 1} [{face}] 大字:{s.on_screen_text}", flush=True)
        print(f"        口播(泰): {s.narration}", flush=True)
        if s.narration_zh.strip():
            print(f"        中文译: {s.narration_zh}", flush=True)
        print(f"        图: {s.img_prompt[:90]}", flush=True)
        print(f"        运镜: {s.mov_prompt[:70]}", flush=True)


def build(cfg: TaskConfig, secrets: Secrets, outdir: Path, do_capcut: bool,
          resume: bool = False) -> list[Path]:
    work = outdir / "_work"
    work.mkdir(parents=True, exist_ok=True)

    script_path = outdir / "script.json"
    strategy_path = outdir / "strategy.json"
    if resume and script_path.exists():
        strategy = (
            json.loads(strategy_path.read_text(encoding="utf-8"))
            if strategy_path.exists() else {}
        )
        script = Script.from_dict(json.loads(script_path.read_text(encoding="utf-8")))
        print("[resume] 复用已有 strategy.json / script.json，不再调用 LLM", flush=True)
        _print_strategy(strategy)
    else:
        strategy = llm.generate_strategy(cfg, secrets)
        strategy_path.write_text(
            json.dumps(strategy, ensure_ascii=False, indent=2), encoding="utf-8")
        _print_strategy(strategy)

        script = llm.generate_script(cfg, secrets, strategy=strategy)
        script_path.write_text(script.to_json(), encoding="utf-8")
    tpl = templates.get(script.template_used)
    tpl_name = tpl["name_zh"] if tpl else (script.template_used or "auto")
    print(f"[1/5] 脚本就绪：{len(script.scenes)} 个分镜，"
          f"爆款结构=[{script.template_used or 'auto'}]{tpl_name}，hook=\"{script.hook}\"", flush=True)
    _print_script(script)

    base, voice, words, words2 = _prepare_assets(script, cfg, secrets, work)
    total = ff.duration(base)
    print(f"[2/5] 底片+配音就绪：{total:.1f}s")

    results: list[Path] = []
    final = _render_variant(base, words, total, cfg, outdir / "final.mp4", work,
                            hook=script.hook, cta=script.cta, bgm_override=None, words2=words2)
    results.append(final)
    print(f"[3/5] 主成片：{final}")

    # A/B 多版本（换 hook / 换 bgm）
    hooks = cfg.get("variants", "hooks", default=[]) or []
    bgms = cfg.get("variants", "bgms", default=[]) or []
    vi = 0
    for hk in hooks:
        vi += 1
        out = outdir / f"variant_{vi:02d}_hook.mp4"
        _render_variant(base, words, total, cfg, out, work, hook=hk, cta=script.cta, bgm_override=None, words2=words2)
        results.append(out)
    for bg in bgms:
        vi += 1
        out = outdir / f"variant_{vi:02d}_bgm.mp4"
        _render_variant(base, words, total, cfg, out, work, hook=script.hook, cta=script.cta, bgm_override=bg, words2=words2)
        results.append(out)
    if vi:
        print(f"[4/5] A/B 多版本：{vi} 条")

    if do_capcut:
        try:
            from . import capcut_export

            draft_dir = outdir / "capcut_draft"
            capcut_export.export(script, cfg, work, draft_dir)
            print(f"[5/5] 剪映/CapCut 草稿：{draft_dir}")
        except Exception as exc:  # noqa: BLE001
            print(f"[5/5] 跳过 CapCut 草稿导出：{exc}")

    return results


def _publish(cfg: TaskConfig, secrets: Secrets, video: Path) -> None:
    brief = cfg.get("brief", default={}) or {}
    caption = (cfg.get("publish", "caption", default="") or "").format(**brief)
    if cfg.get("publish", "tiktok", default=False):
        from .publish import tiktok

        print("发布 TikTok:", tiktok.publish(video, caption, secrets.tiktok_access_token))
    if cfg.get("publish", "facebook", default=False):
        from .publish import facebook

        print("发布 Facebook:", facebook.publish(
            video, caption, secrets.fb_page_id, secrets.fb_page_access_token, secrets.fb_api_version
        ))


def main() -> None:
    ap = argparse.ArgumentParser(description="TikTok/Facebook 投流视频流水线")
    ap.add_argument("--config", default=str(REPO_ROOT / "config.yaml"))
    ap.add_argument("--no-capcut", action="store_true", help="不导出剪映/CapCut 草稿")
    ap.add_argument("--resume", action="store_true",
                    help="复用已有产物（script/clips/audio），只补齐缺失分镜后重新合成")
    ap.add_argument("--publish", action="store_true", help="强制发布（覆盖 config 开关）")
    ap.add_argument("--list-templates", action="store_true",
                    help="列出全部爆款通用接口模版后退出")
    args = ap.parse_args()

    if args.list_templates:
        for t in templates.VIRAL_TEMPLATES:
            applies = "/".join(t["applies_to"])
            print(f"[{t['id']}] {t['name']}（{t['name_zh']}） · 适用: {applies}")
            print(f"    {t['best_for']}")
        return

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        cfg_path = REPO_ROOT / "config.example.yaml"
        print(f"未找到 {args.config}，使用示例配置 {cfg_path.name}")
    cfg = TaskConfig.load(cfg_path)
    secrets = Secrets.load()

    outdir = REPO_ROOT / "output" / cfg.project
    if outdir.exists() and not args.resume:
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    results = build(cfg, secrets, outdir, do_capcut=not args.no_capcut, resume=args.resume)
    print("完成：", *[str(p) for p in results], sep="\n  ")

    if args.publish or cfg.get("publish", "tiktok", default=False) or cfg.get("publish", "facebook", default=False):
        _publish(cfg, secrets, results[0])


if __name__ == "__main__":
    main()
