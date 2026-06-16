"""配音 (TTS)。

provider:
  edge       : 微软 Edge TTS，免 key，默认，质量足够投流（推荐先用它打通）
  openai     : OpenAI / 兼容接口的 TTS
  elevenlabs : ElevenLabs
  azure      : Azure 认知语音
返回生成的音频文件路径（mp3/wav）。
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from ..config import Secrets, TaskConfig


# 各语言的原生 EdgeTTS 神经音色（真母语发音）。
# th 男/女声分开列出——ElevenLabs 的 multilingual_v2 配英文音色念泰文是“假泰语/乱码”，
# 泰语一律走这里的原生泰语音色。
_EDGE_VOICE_BY_LANG = {
    "th": "th-TH-PremwadeeNeural",   # 泰语 女声（默认）
    "th-f": "th-TH-PremwadeeNeural",
    "th-m": "th-TH-NiwatNeural",     # 泰语 男声
    "zh": "zh-CN-XiaoxiaoNeural",
    "en": "en-US-AriaNeural",
    "id": "id-ID-GadisNeural",
    "vi": "vi-VN-HoaiMyNeural",
    "ms": "ms-MY-YasminNeural",
}
# ElevenLabs 的 eleven_multilingual_v2 不真正支持的语言——强制改用原生 EdgeTTS。
_EDGE_ONLY_LANGS = {"th", "lo", "km", "my"}


def _edge_voice(cfg: TaskConfig, secrets: Secrets) -> str:
    """优先 config.yaml 的 tts.voice；否则按目标语言选原生音色；都没有再退回 secrets。"""
    code = (cfg.language or "en").strip().lower()[:2]
    cfg_voice = (cfg.get("tts", "voice", default="") or "").strip()
    if cfg_voice:
        return cfg_voice
    configured = (secrets.tts_voice or "").strip()
    # 已配置且与目标语言一致就沿用；否则按语言挑原生音色（避免英文音色念泰文=乱码）
    if configured and configured.lower().startswith(code):
        return configured
    gender = (cfg.get("tts", "gender", default="") or "").strip().lower()
    key = f"{code}-{gender[:1]}" if gender and f"{code}-{gender[:1]}" in _EDGE_VOICE_BY_LANG else code
    return _EDGE_VOICE_BY_LANG.get(key, _EDGE_VOICE_BY_LANG.get(code, configured or "en-US-AriaNeural"))


def synth(text: str, out_path: Path, cfg: TaskConfig, secrets: Secrets) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    provider = (secrets.tts_provider or "edge").lower()
    code = (cfg.language or "en").strip().lower()[:2]
    # 泰语等：ElevenLabs/OpenAI 英文音色会“硬念”成乱码 -> 强制走原生 EdgeTTS 泰语音色
    if code in _EDGE_ONLY_LANGS and provider in ("elevenlabs", "openai"):
        print(f"  [TTS] {code} 语言不走 {provider}（会念成乱码），改用原生 EdgeTTS 音色", flush=True)
        provider = "edge"
    if provider == "edge":
        return _edge(text, out_path, cfg, secrets)
    if provider == "openai":
        return _openai(text, out_path, secrets)
    if provider == "elevenlabs":
        return _elevenlabs(text, out_path, secrets)
    if provider == "azure":
        return _azure(text, out_path, cfg, secrets)
    raise ValueError(f"未知 TTS_PROVIDER={provider}")


def _edge(text: str, out_path: Path, cfg: TaskConfig, secrets: Secrets) -> Path:
    import edge_tts

    rate = cfg.get("tts", "rate", default="+0%")
    volume = cfg.get("tts", "volume", default="+0%")
    voice = _edge_voice(cfg, secrets)
    mp3 = out_path.with_suffix(".mp3")

    async def _go() -> None:
        comm = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
        await comm.save(str(mp3))

    asyncio.run(_go())
    return mp3


def _openai(text: str, out_path: Path, secrets: Secrets) -> Path:
    from openai import OpenAI

    client = OpenAI(api_key=secrets.tts_api_key, base_url=secrets.tts_base_url or None)
    mp3 = out_path.with_suffix(".mp3")
    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts", voice=secrets.tts_voice or "alloy", input=text
    ) as resp:
        resp.stream_to_file(str(mp3))
    return mp3


def _elevenlabs(text: str, out_path: Path, secrets: Secrets) -> Path:
    import requests

    voice = secrets.tts_voice or "21m00Tcm4TlvDq8ikWAM"
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    payload = {
        "text": text,
        "model_id": secrets.tts_model or "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.4, "similarity_boost": 0.8, "style": 0.3},
    }
    headers = {"xi-api-key": secrets.tts_api_key, "accept": "audio/mpeg"}
    last: Exception | None = None
    for attempt in range(1, 7):
        r = requests.post(url, headers=headers, json=payload, timeout=120)
        if r.status_code in (429, 500, 502, 503, 504):
            wait = float(r.headers.get("retry-after") or 0) or min(2 ** attempt, 30)
            last = RuntimeError(f"ElevenLabs {r.status_code}")
            time.sleep(wait)
            continue
        r.raise_for_status()
        mp3 = out_path.with_suffix(".mp3")
        mp3.write_bytes(r.content)
        return mp3
    raise RuntimeError(f"ElevenLabs 多次限流/失败: {last}")


def _azure(text: str, out_path: Path, cfg: TaskConfig, secrets: Secrets) -> Path:
    import requests

    region = secrets.azure_tts_region
    endpoint = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    ssml = (
        f"<speak version='1.0' xml:lang='{cfg.language}'>"
        f"<voice name='{secrets.tts_voice}'>{text}</voice></speak>"
    )
    r = requests.post(
        endpoint,
        headers={
            "Ocp-Apim-Subscription-Key": secrets.tts_api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
        },
        data=ssml.encode("utf-8"),
        timeout=120,
    )
    r.raise_for_status()
    mp3 = out_path.with_suffix(".mp3")
    mp3.write_bytes(r.content)
    return mp3
