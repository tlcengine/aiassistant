"""Client for the VoiceBox/VoxForge service running on geo.tlcengine.com:8004."""

import httpx
from config import get_settings


async def speech_to_text(audio_bytes: bytes) -> str:
    """Send PCM audio to VoiceBox STT and return transcript."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.voicebox_url}/stt",
            content=audio_bytes,
            headers={"Content-Type": "audio/pcm"},
        )
        resp.raise_for_status()
        return resp.json().get("text", "")


async def text_to_speech(text: str) -> bytes:
    """Send text to VoiceBox TTS and return PCM audio bytes."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.voicebox_url}/tts",
            json={"text": text},
        )
        resp.raise_for_status()
        return resp.content
