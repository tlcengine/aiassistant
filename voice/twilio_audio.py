"""Twilio media stream audio encoding/decoding (mu-law)."""

import audioop
import base64
import json


def decode_twilio_media(message: str) -> bytes | None:
    """Decode a Twilio Media Stream WebSocket message to raw PCM bytes.

    Twilio sends mu-law 8kHz mono audio base64-encoded in JSON.
    Returns 16-bit PCM at 8kHz, or None if the message isn't a media event.
    """
    data = json.loads(message)
    if data.get("event") != "media":
        return None
    payload = base64.b64decode(data["media"]["payload"])
    # Convert mu-law to 16-bit linear PCM
    pcm = audioop.ulaw2lin(payload, 2)
    return pcm


def encode_twilio_media(pcm_audio: bytes, stream_sid: str) -> str:
    """Encode raw 16-bit PCM audio back to a Twilio media message."""
    mulaw = audioop.lin2ulaw(pcm_audio, 2)
    payload = base64.b64encode(mulaw).decode("ascii")
    return json.dumps({
        "event": "media",
        "streamSid": stream_sid,
        "media": {"payload": payload},
    })
