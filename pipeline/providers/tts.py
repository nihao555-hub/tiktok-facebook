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
from pathlib import Path

from ..config import Secrets, TaskConfig


def synth(text: str, out_path: Path, cfg: TaskConfig, secrets: Secrets) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    provider = (secrets.tts_provider or "edge").lower()
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
    mp3 = out_path.with_suffix(".mp3")

    async def _go() -> None:
        comm = edge_tts.Communicate(text, secrets.tts_voice, rate=rate, volume=volume)
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

    voice = secrets.tts_voice or "Rachel"
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    r = requests.post(
        url,
        headers={"xi-api-key": secrets.tts_api_key, "accept": "audio/mpeg"},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=120,
    )
    r.raise_for_status()
    mp3 = out_path.with_suffix(".mp3")
    mp3.write_bytes(r.content)
    return mp3


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
