"""AI Assistant — FastAPI server handling Twilio voice calls with Claude agent."""

import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from agent import run_agent
from config import get_settings
from tools.sms import send_sms
from voice.twilio_audio import decode_twilio_media, encode_twilio_media
from voice.voicebox_client import speech_to_text, text_to_speech

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from crm.database import init_db
from crm.routes import router as crm_router
from crm.gmail_routes import router as gmail_router

app = FastAPI(title="CertiHomes AI Assistant", version="1.0.0")
app.include_router(crm_router)
app.include_router(gmail_router)


@app.on_event("startup")
async def startup():
    await init_db()

# In-memory conversation store (keyed by conversation_id)
conversations: dict[str, list[dict]] = {}


class ChatRequest(BaseModel):
    message: str
    conversation_id: str


@app.post("/chat")
async def chat(req: ChatRequest):
    """Text chat endpoint — used by the web frontend."""
    history = conversations.setdefault(req.conversation_id, [])
    reply, tool_results = await run_agent(req.message, history)
    tool_calls = [
        {"tool": tr["tool"], "summary": f"Called {tr['tool']}"}
        for tr in tool_results
    ]
    return {"reply": reply, "tool_calls": tool_calls}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/incoming-call")
async def incoming_call(request: Request):
    """Twilio webhook — answers the call and opens a WebSocket media stream."""
    settings = get_settings()
    host = request.headers.get("host", "aiassistant.tlcengine.com")
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">Welcome to CertiHomes. How can I help you today?</Say>
    <Connect>
        <Stream url="wss://{host}/voice-stream"/>
    </Connect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/voice-stream")
async def voice_stream(ws: WebSocket):
    """Handle the Twilio media stream — STT → Agent → TTS loop."""
    await ws.accept()
    conversation_history: list[dict] = []
    stream_sid: str | None = None
    audio_buffer = bytearray()
    caller_phone: str | None = None

    logger.info("Voice stream connected")

    try:
        async for raw_message in ws.iter_text():
            data = json.loads(raw_message)
            event = data.get("event")

            if event == "start":
                stream_sid = data["start"]["streamSid"]
                caller_phone = data["start"].get("customParameters", {}).get("from")
                logger.info(f"Stream started: {stream_sid}")
                continue

            if event == "stop":
                logger.info("Stream ended")
                break

            if event != "media":
                continue

            # Decode incoming audio
            pcm = decode_twilio_media(raw_message)
            if pcm is None:
                continue
            audio_buffer.extend(pcm)

            # Process when we have ~2 seconds of audio (8kHz * 2 bytes * 2s = 32000)
            if len(audio_buffer) < 32000:
                continue

            chunk = bytes(audio_buffer)
            audio_buffer.clear()

            # 1. Speech-to-text
            transcript = await speech_to_text(chunk)
            if not transcript.strip():
                continue
            logger.info(f"Caller said: {transcript}")

            # 2. Run the AI agent
            reply, tool_results = await run_agent(transcript, conversation_history)
            logger.info(f"Agent reply: {reply}")

            # 3. Text-to-speech
            reply_audio = await text_to_speech(reply)

            # 4. Stream audio back
            if stream_sid:
                media_msg = encode_twilio_media(reply_audio, stream_sid)
                await ws.send_text(media_msg)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception:
        logger.exception("Error in voice stream")


@app.post("/call-status")
async def call_status(request: Request):
    """Twilio status callback — fires after the call ends. Send follow-up SMS."""
    form = await request.form()
    caller = form.get("From", "")
    if caller:
        try:
            send_sms(
                to=caller,
                body=(
                    "Thanks for calling CertiHomes! "
                    "Browse listings at https://certihomes.com "
                    "or reply to this text with any questions."
                ),
            )
        except Exception:
            logger.exception("Failed to send follow-up SMS")
    return Response(content="<Response/>", media_type="application/xml")


# Serve static frontend (must be last — catches all unmatched routes)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
