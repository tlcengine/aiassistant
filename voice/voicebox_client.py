"""Client for VoiceBox TTS/STT on geo2.tlcengine.com (voicebox.certihomes.com)."""

import io
import wave
import httpx
from config import get_settings

# Default Krishna voice profile on VoiceBox
KRISHNA_PROFILE_ID = "1e5c7975-014a-48f1-97b4-b87eeabf8e35"


def _base_url() -> str:
    return get_settings().voicebox_url


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 8000, channels: int = 1, sample_width: int = 2) -> bytes:
    """Wrap raw PCM audio bytes in a proper WAV header."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


async def speech_to_text(audio_bytes: bytes) -> str:
    """Send audio to VoiceBox transcribe endpoint and return transcript.

    Wraps raw PCM in a WAV header since VoiceBox expects a proper audio file.
    """
    # If it's raw PCM (no RIFF header), wrap it in WAV
    if not audio_bytes[:4] == b'RIFF':
        audio_bytes = _pcm_to_wav(audio_bytes)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_base_url()}/transcribe",
            files={"file": ("audio.wav", audio_bytes, "audio/wav")},
        )
        resp.raise_for_status()
        return resp.json().get("text", "")


async def text_to_speech(text: str, profile_id: str = KRISHNA_PROFILE_ID) -> bytes:
    """Send text to VoiceBox generate endpoint and return audio bytes."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{_base_url()}/generate",
            json={"text": text, "profile_id": profile_id},
        )
        resp.raise_for_status()
        data = resp.json()
        # Download the generated audio
        audio_resp = await client.get(f"{_base_url()}/audio/{data['id']}")
        audio_resp.raise_for_status()
        return audio_resp.content


async def list_profiles() -> list:
    """List all available voice profiles."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{_base_url()}/profiles")
        resp.raise_for_status()
        return resp.json()
