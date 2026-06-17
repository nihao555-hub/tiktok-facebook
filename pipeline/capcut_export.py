"""导出可在 剪映 / CapCut 桌面端继续精修的「做厚」草稿 + 一份 Win/Mac 一键导出包。

成片渲染（final.mp4）由 FFmpeg 在 Linux 上完成（mixer.py + subtitles.py），原生观感的
双语字幕/钩子/CTA 已经烧进画面。本模块额外提供「原生可编辑工程」路径——把分镜片段、配音、
双语口播字幕、花字、CTA 按时间轴写成剪映草稿，并**预置好转场 / 入场动画 / 场景特效 / 滤镜 /
花字入出场+循环动画 / 描边阴影 / 动效 CTA 按钮**（按爆款结构分预设，避免同质化）。

⚠️ 硬限制：CapCut / 剪映 桌面端只有 Windows / macOS，没有 Linux 版。本流水线跑在 Linux 上，
**无法在这台机器里打开 App 把这些原生特效烘焙成 mp4**。因此本模块产出两样东西：
  1. draft_content.json —— Linux 端构建的预览草稿（引用的是 Linux 素材路径，仅供查看/校验）；
  2. capcut_bundle/    —— **给你的 Win/Mac 一键导出包**：内含拷贝好的素材 + scenes.json +
     decoration.json + 自包含重建脚本 make_capcut_draft.py（用本地路径在你电脑的 CapCut/剪映
     草稿库里重建出完全相同的「做厚」草稿）+ 一键导出_Windows.bat / 一键导出_Mac.command +
     说明。你在自己电脑上双击一键脚本，它会把草稿装进 CapCut，打开后点导出即得顶级装饰版。

装饰逻辑的唯一真相源是 capcut_core.py（自包含、只依赖 pyJianYingDraft），它会被一并拷进包里，
保证 Linux 预览草稿与你电脑上重建的草稿装饰**完全一致**。
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from . import capcut_core
from .config import TaskConfig
from .script_model import Script

# 给 Win/Mac 重建用的自包含脚本（不依赖本仓库，只 import 同目录的 capcut_core）。
# 它读取 meta.json + scenes.json，把素材按本地路径在 CapCut/剪映 草稿库里重建出做厚草稿。
_REBUILD_PY = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 在你自己的 Windows / macOS 电脑上运行：把「做厚」草稿装进 CapCut/剪映 草稿库。
# 用法：双击 一键导出_Windows.bat / 一键导出_Mac.command，或手动：
#     python make_capcut_draft.py [可选:你的草稿库目录]
# 跑完打开 CapCut/剪映 → 在草稿列表看到本草稿 → 检查后点「导出」即得顶级装饰版 mp4。
import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

try:
    import pyJianYingDraft  # noqa: F401
except Exception:
    print("缺少依赖 pyJianYingDraft，请先安装：")
    print("    python -m pip install pyJianYingDraft")
    sys.exit(1)

import capcut_core
from pyJianYingDraft import DraftFolder

meta = json.loads((BASE / "meta.json").read_text(encoding="utf-8"))
scenes = json.loads((BASE / "scenes.json").read_text(encoding="utf-8"))

# 把分镜里的相对素材路径解析为本地绝对路径
for sc in scenes:
    for k in ("clip", "audio"):
        if sc.get(k):
            sc[k] = str((BASE / sc[k]).resolve())

# CapCut / 剪映 草稿库常见位置（按 OS 探测；也可在命令行第 1 个参数手动指定）
def candidate_roots():
    home = Path.home()
    la = os.environ.get("LOCALAPPDATA", "")
    roots = []
    if la:
        roots += [
            Path(la) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft",
            Path(la) / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft",
        ]
    roots += [
        home / "Movies" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft",
        home / "Movies" / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft",
    ]
    return roots

root = None
if len(sys.argv) > 1 and sys.argv[1].strip():
    root = Path(sys.argv[1].strip())
else:
    for r in candidate_roots():
        if r.exists():
            root = r
            break
if root is None:
    root = BASE / "_CapCut_drafts"
    root.mkdir(parents=True, exist_ok=True)
    print("没自动找到 CapCut/剪映 草稿库，已先生成到本地文件夹：")
    print("   ", root)
    print("若要直接进 CapCut 草稿列表，请把该目录的内容拷进你的草稿库，")
    print("或重跑并把草稿库路径作为参数传入：python make_capcut_draft.py <你的草稿库目录>")

draft_name = meta.get("draft_name") or "tiktok_factory_draft"
folder = DraftFolder(str(root))
s = folder.create_draft(draft_name, int(meta["width"]), int(meta["height"]),
                        int(meta.get("fps", 30)), allow_replace=True)
capcut_core.build_script(meta, scenes, script=s)
s.save()
print("已生成做厚草稿：", draft_name)
print("草稿库：", root)
print("现在打开 CapCut / 剪映，在草稿列表里找到它，检查无误后点『导出』即可。")
'''

_BAT = (
    "@echo off\r\n"
    "chcp 65001 >nul\r\n"
    "cd /d \"%~dp0\"\r\n"
    "echo 正在把做厚草稿装进 CapCut/剪映 草稿库...\r\n"
    "py -3 make_capcut_draft.py %*\r\n"
    "if errorlevel 1 python make_capcut_draft.py %*\r\n"
    "echo.\r\n"
    "echo 完成后请打开 CapCut/剪映，在草稿列表里找到草稿，检查后点导出。\r\n"
    "pause\r\n"
)

_COMMAND = (
    "#!/bin/bash\n"
    "cd \"$(dirname \"$0\")\"\n"
    "echo '正在把做厚草稿装进 CapCut/剪映 草稿库...'\n"
    "python3 make_capcut_draft.py \"$@\"\n"
    "echo '完成后请打开 CapCut/剪映，在草稿列表里找到草稿，检查后点导出。'\n"
)


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]+", "_", (text or "").strip()).strip("_")
    return s[:48] or "draft"


def _scene_data(script: Script, work: Path, assets_rel: str | None = None) -> list[dict]:
    """把脚本分镜整理成 capcut_core 需要的结构。

    assets_rel 给定时返回相对路径（用于打包，路径相对 bundle 根）；否则返回 Linux 绝对路径。
    """
    out: list[dict] = []
    for scene in script.scenes:
        clip = work / "clips" / f"scene_{scene.index:02d}.mp4"
        aud = work / "audio" / f"a_{scene.index:02d}.mp3"
        if assets_rel is not None:
            clip_v = f"{assets_rel}/{clip.name}" if clip.exists() else None
            aud_v = f"{assets_rel}/{aud.name}" if aud.exists() else None
        else:
            clip_v = str(clip) if clip.exists() else None
            aud_v = str(aud) if aud.exists() else None
        out.append({
            "clip": clip_v,
            "audio": aud_v,
            "on_screen_text": scene.on_screen_text,
            "narration_th": scene.narration,
            "narration_zh": scene.narration_zh,
            "seconds": float(scene.seconds),
        })
    return out


def _meta(script: Script, cfg: TaskConfig, draft_name: str) -> dict:
    return {
        "draft_name": draft_name,
        "width": cfg.width,
        "height": cfg.height,
        "fps": cfg.fps,
        "hook": script.hook,
        "cta": script.cta,
        "template_used": script.template_used or script.template,
        "template": script.template,
        "language": cfg.language,
    }


def _build_bundle(script: Script, cfg: TaskConfig, work: Path, bundle: Path,
                  draft_name: str) -> None:
    """生成 Win/Mac 一键导出包（拷素材 + json + 重建脚本 + 一键脚本 + 说明）。"""
    assets = bundle / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for scene in script.scenes:
        for src in (work / "clips" / f"scene_{scene.index:02d}.mp4",
                    work / "audio" / f"a_{scene.index:02d}.mp3"):
            if src.exists():
                shutil.copy2(src, assets / src.name)

    meta = _meta(script, cfg, draft_name)
    (bundle / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (bundle / "scenes.json").write_text(
        json.dumps(_scene_data(script, work, assets_rel="assets"),
                   ensure_ascii=False, indent=2), encoding="utf-8")
    # 实际挑中的装饰枚举（便于查看/复现）
    deco = {}
    try:
        deco = capcut_core.describe(meta)
    except Exception as e:  # noqa: BLE001
        deco = {"error": str(e)}
    (bundle / "decoration.json").write_text(
        json.dumps(deco, ensure_ascii=False, indent=2), encoding="utf-8")

    # 自包含装饰核心 + 重建脚本 + 一键脚本
    shutil.copy2(Path(capcut_core.__file__), bundle / "capcut_core.py")
    (bundle / "make_capcut_draft.py").write_text(_REBUILD_PY, encoding="utf-8")
    bat = bundle / "一键导出_Windows.bat"
    bat.write_text(_BAT, encoding="utf-8-sig")
    cmd = bundle / "一键导出_Mac.command"
    cmd.write_text(_COMMAND, encoding="utf-8")
    try:
        cmd.chmod(0o755)
    except OSError:
        pass

    (bundle / "README_一键导出.txt").write_text(
        "【Win/Mac 一键导出顶级装饰版】\n\n"
        "为什么需要这一步：CapCut/剪映 只有 Windows/macOS 版，生成视频的服务器是 Linux，\n"
        "没法在服务器里打开 App 渲染原生转场/特效/花字。所以把草稿+素材打包给你，在你自己\n"
        "电脑上一键重建并导出。\n\n"
        "步骤：\n"
        "1) 先装好 CapCut（或剪映）桌面版，并打开过一次（让它建好草稿库目录）。\n"
        "2) 装 Python 3（python.org），然后装依赖：python -m pip install pyJianYingDraft\n"
        "3) Windows：双击『一键导出_Windows.bat』；  Mac：双击『一键导出_Mac.command』。\n"
        "   （脚本会把做厚草稿装进 CapCut/剪映 的草稿库。若没自动找到草稿库，可在命令行把\n"
        "    草稿库目录作为参数传入：python make_capcut_draft.py <你的草稿库目录>）\n"
        "4) 打开 CapCut/剪映 → 草稿列表里找到这个草稿 → 检查（转场/花字/特效都已摆好）→ 点『导出』。\n\n"
        "草稿里已预置：按爆款结构选的转场、片段入场动画、场景特效、滤镜、泰文(大)+中文(小)\n"
        "双语口播字幕（描边阴影、无黑底）、花字关键词（循环动画）、红色动效 CTA 按钮。\n"
        "泰文已指定 Kanit 字体、中文用思源/台北黑体，避免方块豆腐。\n"
        "decoration.json 记录了本片实际用到的转场/特效/字体名称，便于你查看或微调。\n",
        encoding="utf-8",
    )


def export(script: Script, cfg: TaskConfig, work: Path, draft_dir: Path) -> Path:
    draft_dir.mkdir(parents=True, exist_ok=True)
    draft_name = f"{_slug(cfg.project)}_{_slug(script.template_used or script.template)}"

    # 1) Linux 端预览草稿（引用 Linux 素材路径，仅供查看/校验装饰是否正确构建）
    meta = _meta(script, cfg, draft_name)
    scenes_data = _scene_data(script, work)
    s = capcut_core.build_script(meta, scenes_data)
    s.dump(str(draft_dir / "draft_content.json"))

    # 2) 给你的 Win/Mac 一键导出包
    bundle = draft_dir / "capcut_bundle"
    _build_bundle(script, cfg, work, bundle, draft_name)

    (draft_dir / "HOW_TO_OPEN.txt").write_text(
        "本目录有两样东西：\n"
        "1) draft_content.json —— Linux 端构建的预览草稿（引用服务器素材路径，仅供查看）。\n"
        "2) capcut_bundle/    —— 给你 Windows/Mac 的『一键导出顶级装饰版』包。\n\n"
        "要拿到顶级装饰成片：把 capcut_bundle/ 整个文件夹拷到你自己的电脑，按里面的\n"
        "README_一键导出.txt 操作（双击一键脚本→打开 CapCut/剪映→点导出）。\n\n"
        "说明：CapCut/剪映 没有 Linux 版，服务器无法直接把原生特效烘焙成 mp4，所以最终\n"
        "导出这一步需要在你自己的 Windows/Mac 上完成。Linux 上已经能出『烧字版』final.mp4。\n",
        encoding="utf-8",
    )
    return draft_dir
