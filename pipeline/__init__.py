"""TikTok / Facebook 投流视频流水线。

阶段: 脚本(LLM) -> AI片段生成 -> 配音(TTS) -> 字幕(ASR) -> 混剪+装饰(FFmpeg)
     -> 可编辑CapCut草稿(pyJianYingDraft) -> 发布(TikTok/Facebook)
"""

__all__ = ["config"]
