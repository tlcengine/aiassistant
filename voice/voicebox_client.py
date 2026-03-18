"""Client for VoiceBox TTS/STT on geo2.tlcengine.com (voicebox.certihomes.com).

STT: Uses VoiceBox Whisper transcription (reliable).
TTS: Falls back to Google Cloud TTS via gTTS if VoiceBox TTS fails,
     then to simple PCM silence as last resort.
"""

import io
import logging
import wave
import httpx
from config import get_settings

logger = logging.getLogger(__name__)

# Default voice profile
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
    """Convert text to speech audio bytes (8kHz 16-bit PCM mono).

    Tries VoiceBox first, falls back to gTTS, then to silence.
    """
    # Try VoiceBox first
    try:
        return await _voicebox_tts(text, profile_id)
    except Exception as e:
        logger.warning(f"VoiceBox TTS failed: {e}")

    # Fallback: gTTS (Google Translate TTS — free, no API key needed)
    try:
        return await _gtts_fallback(text)
    except Exception as e:
        logger.warning(f"gTTS fallback failed: {e}")

    # Last resort: return silence
    logger.error("All TTS engines failed, returning silence")
    return b'\x00' * 16000  # 1 second of silence


async def _voicebox_tts(text: str, profile_id: str) -> bytes:
    """VoiceBox generate → poll status → download audio."""
    async with httpx.AsyncClient(timeout=60) as client:
        # Start generation
        resp = await client.post(
            f"{_base_url()}/generate",
            json={"text": text, "profile_id": profile_id},
        )
        resp.raise_for_status()
        data = resp.json()
        gen_id = data["id"]

        # Poll for completion (VoiceBox generate is async)
        import asyncio
        for _ in range(30):  # Max 30 seconds
            await asyncio.sleep(1)
            status_resp = await client.get(f"{_base_url()}/generate/{gen_id}/status")
            # SSE stream — parse the last data line
            text_content = status_resp.text
            if '"status": "completed"' in text_content or '"status":"completed"' in text_content:
                # Download audio
                audio_resp = await client.get(f"{_base_url()}/audio/{gen_id}")
                audio_resp.raise_for_status()
                return audio_resp.content
            elif '"status": "failed"' in text_content or '"status":"failed"' in text_content:
                raise Exception(f"VoiceBox generation failed: {text_content}")

        raise Exception("VoiceBox TTS timed out")


async def _gtts_fallback(text: str) -> bytes:
    """Use gTTS (Google Translate TTS) as fallback — returns 8kHz PCM."""
    import subprocess
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3f:
        mp3_path = mp3f.name

    wav_path = mp3_path.replace(".mp3", ".wav")

    try:
        # Generate MP3 with gTTS
        from gtts import gTTS
        tts = gTTS(text=text, lang='en', tld='com')
        tts.save(mp3_path)

        # Convert to 8kHz mono WAV PCM using ffmpeg
        subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, "-ar", "8000", "-ac", "1", "-f", "wav", wav_path],
            capture_output=True, timeout=10
        )

        with wave.open(wav_path, "rb") as wf:
            return wf.readframes(wf.getnframes())
    finally:
        for p in (mp3_path, wav_path):
            try:
                os.unlink(p)
            except OSError:
                pass


async def list_profiles() -> list:
    """List all available voice profiles."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{_base_url()}/profiles")
        resp.raise_for_status()
        return resp.json()
