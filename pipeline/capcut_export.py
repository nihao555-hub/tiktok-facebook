"""导出可在 剪映 / CapCut 桌面端继续精修的草稿 (draft_content.json)。

注意：本仓库的"成片渲染"由 FFmpeg 在 Linux 上完成（mixer.py）。
本模块是额外提供的"原生可编辑工程"路径——把分镜片段/配音/大字按时间轴写成剪映草稿，
你在自己电脑的 剪映/CapCut 里打开即可套用原生模板、转场、贴纸、热门音乐后导出。
"""

from __future__ import annotations

from pathlib import Path

from . import ffmpeg_utils as ff
from .config import TaskConfig
from .script_model import Script


def export(script: Script, cfg: TaskConfig, work: Path, draft_dir: Path) -> Path:
    from pyJianYingDraft import (
        AudioMaterial,
        AudioSegment,
        ScriptFile,
        TextSegment,
        TrackType,
        VideoMaterial,
        VideoSegment,
        trange,
    )

    s = ScriptFile(cfg.width, cfg.height, cfg.fps, True)
    s.add_track(TrackType.video)
    s.add_track(TrackType.audio)
    s.add_track(TrackType.text)

    t = 0.0
    for scene in script.scenes:
        vid = work / "clips" / f"scene_{scene.index:02d}.mp4"
        aud = work / "audio" / f"a_{scene.index:02d}.mp3"
        dur = float(scene.seconds)
        if vid.exists():
            s.add_segment(VideoSegment(VideoMaterial(str(vid)), trange(f"{t}s", f"{dur}s")))
        if aud.exists():
            adur = min(ff.duration(aud), dur) or dur
            s.add_segment(AudioSegment(AudioMaterial(str(aud)), trange(f"{t}s", f"{adur}s")))
        if scene.on_screen_text:
            s.add_segment(TextSegment(scene.on_screen_text, trange(f"{t}s", f"{min(dur, 3.0)}s")))
        t += dur

    draft_dir.mkdir(parents=True, exist_ok=True)
    s.dump(str(draft_dir / "draft_content.json"))
    (draft_dir / "HOW_TO_OPEN.txt").write_text(
        "把 draft_content.json 放进 剪映/CapCut 的一个草稿文件夹中（替换其 draft_content.json），"
        "或用 pyJianYingDraft 的 DraftFolder 写入你的草稿库目录后，在桌面端打开继续精修。\n",
        encoding="utf-8",
    )
    return draft_dir
