"""AI Assistant — FastAPI server handling Twilio voice calls with Claude agent."""

import asyncio
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
from tools.outbound_call import pending_calls
from voice.twilio_audio import decode_twilio_media, encode_twilio_media
from voice.voicebox_client import speech_to_text, text_to_speech

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pre-load thinking music audio for streaming during agent processing
_thinking_audio: bytes | None = None

def _load_thinking_audio() -> bytes:
    """Load and convert thinking.wav to mu-law for Twilio streaming."""
    global _thinking_audio
    if _thinking_audio is not None:
        return _thinking_audio
    import audioop, wave
    try:
        with wave.open("static/thinking.wav", "rb") as f:
            pcm = f.readframes(f.getnframes())
        _thinking_audio = pcm
    except Exception:
        logger.warning("Could not load thinking.wav, using silence")
        _thinking_audio = b'\x00' * 16000  # 1s silence fallback
    return _thinking_audio

from crm.database import init_db
from crm.routes import router as crm_router
from crm.gmail_routes import router as gmail_router
from browser.routes import router as browser_router

app = FastAPI(title="CertiHomes AI Assistant", version="1.0.0")
app.include_router(crm_router)
app.include_router(gmail_router)
app.include_router(browser_router)


@app.on_event("startup")
async def startup():
    await init_db()
    # Start browser agent background services
    import asyncio
    from browser.browser_pool import start_browser
    from browser import task_runner
    await start_browser()
    asyncio.create_task(task_runner.run_forever())

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
    """Twilio webhook — answers the call with speech-based Gather loop.

    Uses Twilio's native speech recognition + Google neural TTS.
    This approach is more reliable than WebSocket streaming and gives
    natural barge-in support.
    """
    # Use pre-recorded greeting for instant playback (no TTS rendering delay)
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/voice-respond" method="POST"
            speechTimeout="2" speechModel="experimental_conversations"
            enhanced="true" language="en-US">
        <Play>https://aiassistant.certihomes.com/voice/greeting.mp3</Play>
    </Gather>
    <Play>https://aiassistant.certihomes.com/voice/ack_didnt_catch.mp3</Play>
    <Redirect>/incoming-call</Redirect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


# In-memory voice conversation store (keyed by CallSid)
voice_conversations: dict[str, list[dict]] = {}

# Pending agent responses (keyed by CallSid)
pending_voice_responses: dict[str, str | None] = {}


@app.post("/voice-respond")
async def voice_respond(request: Request):
    """Process caller speech via AI agent and respond with TTS.

    Flow: Twilio sends SpeechResult → we start agent in background →
    immediately respond with "working on it" + hold music loop →
    /voice-check polls until agent is done → delivers response.
    """
    form = await request.form()
    transcript = form.get("SpeechResult", "").strip()
    confidence = form.get("Confidence", "0")
    call_sid = form.get("CallSid", "unknown")

    logger.info(f"Caller said: '{transcript}' (confidence: {confidence}, CallSid: {call_sid})")

    if not transcript:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/voice-respond" method="POST"
            speechTimeout="2" speechModel="experimental_conversations"
            enhanced="true" language="en-US">
        <Play>https://aiassistant.certihomes.com/voice/ack_didnt_catch.mp3</Play>
    </Gather>
    <Redirect>/incoming-call</Redirect>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    # Get or create conversation history for this call
    history = voice_conversations.setdefault(call_sid, [])

    # Pre-seed with voice context on first turn
    if not history:
        context = (
            "[SYSTEM CONTEXT]: This is a PHONE call. Keep ALL responses concise — 1-3 sentences max. "
            "Speak naturally like a helpful friend. Never use markdown, bullets, lists, or URLs in speech. "
            "Summarize data verbally. After giving info, ask if they want it emailed. "
            "Available tools: search_listings, search_portal_listings, get_market_report, "
            "send_market_report_email, send_email, get_tax_data, get_forecast, cma_quick_lookup, "
            "cma_full_report, make_outbound_call, submit_browser_task. "
            "For property lookups, prefer cma_quick_lookup — use its voice_summary field. "
            "Keep it conversational and warm. Never say URLs aloud."
        )
        history.append({"role": "user", "content": context})
        history.append({"role": "assistant", "content": "Ready to help!"})

    # Mark as pending and start agent in background
    pending_voice_responses[call_sid] = None

    async def _run_agent_bg():
        try:
            reply, _ = await run_agent(transcript, history)
            pending_voice_responses[call_sid] = reply
            logger.info(f"Agent reply ready ({len(reply)} chars): {reply[:80]}...")
        except Exception:
            logger.exception("Agent error during voice call")
            pending_voice_responses[call_sid] = "I ran into a hiccup. Could you try saying that again?"

    asyncio.create_task(_run_agent_bg())

    # Pick pre-recorded acknowledgment MP3 — randomly selects from variations
    import random
    lower = transcript.lower()
    voice_base = "https://aiassistant.certihomes.com/voice"

    # Handle goodbye immediately — don't run agent, just hang up
    if any(w in lower for w in ("bye", "goodbye", "that's all", "hang up", "i'm done", "that's it", "no thanks", "nothing else")):
        # Cancel the background agent task (it's not needed)
        pending_voice_responses.pop(call_sid, None)
        voice_conversations.pop(call_sid, None)
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{voice_base}/ack_goodbye.mp3</Play>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    if "cma" in lower or "value" in lower or "worth" in lower:
        ack_file = random.choice(["ack_cma_1.mp3", "ack_cma_2.mp3", "ack_cma_3.mp3"])
    elif "market" in lower or "stats" in lower or "report" in lower:
        ack_file = random.choice(["ack_market_1.mp3", "ack_market_2.mp3", "ack_market_3.mp3"])
    elif "search" in lower or "homes" in lower or "bedroom" in lower or "house" in lower:
        ack_file = random.choice(["ack_search_1.mp3", "ack_search_2.mp3", "ack_search_3.mp3"])
    elif "email" in lower or "send" in lower:
        ack_file = random.choice(["ack_email_1.mp3", "ack_email_2.mp3"])
    elif "tax" in lower or "assessment" in lower:
        ack_file = random.choice(["ack_tax_1.mp3", "ack_tax_2.mp3"])
    elif "forecast" in lower or "predict" in lower:
        ack_file = "ack_forecast.mp3"
    elif any(w in lower for w in ("hello", "hi ", "hey", "good morning", "good afternoon")):
        ack_file = random.choice(["ack_hello_1.mp3", "ack_hello_2.mp3", "ack_hello_3.mp3"])
    elif any(w in lower for w in ("thank", "thanks", "appreciate")):
        ack_file = random.choice(["ack_thanks_1.mp3", "ack_thanks_2.mp3", "ack_thanks_3.mp3"])
    else:
        ack_file = random.choice(["filler_1.mp3", "filler_2.mp3", "filler_3.mp3", "filler_4.mp3", "filler_5.mp3"])

    # Respond INSTANTLY with pre-recorded ack + poll for agent result
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{voice_base}/{ack_file}</Play>
    <Redirect>/voice-check?sid={call_sid}</Redirect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.post("/voice-check")
@app.get("/voice-check")
async def voice_check(request: Request):
    """Poll for agent response. Once ready, deliver it and loop back to Gather."""
    # Get CallSid from query param or form
    params = request.query_params
    call_sid = params.get("sid", "")
    if not call_sid:
        form = await request.form()
        call_sid = form.get("CallSid", "unknown")

    reply = pending_voice_responses.get(call_sid)

    if reply is None:
        # Not ready yet — play thinking music and check again
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>https://aiassistant.certihomes.com/thinking.wav</Play>
    <Redirect>/voice-check?sid={call_sid}</Redirect>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    # Agent response is ready! Clean up and deliver
    pending_voice_responses.pop(call_sid, None)

    import html
    safe_reply = html.escape(reply)

    # Use en-US-Neural2-F for consistent warm female voice (matches Jenny Neural)
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/voice-respond" method="POST"
            speechTimeout="3" speechModel="experimental_conversations"
            enhanced="true" language="en-US">
        <Say voice="Google.en-US-Neural2-F">{safe_reply}</Say>
    </Gather>
    <Pause length="4"/>
    <Play>https://aiassistant.certihomes.com/voice/ack_still_here.mp3</Play>
    <Gather input="speech" action="/voice-respond" method="POST"
            speechTimeout="8" speechModel="experimental_conversations"
            enhanced="true" language="en-US">
        <Play>https://aiassistant.certihomes.com/thinking.wav</Play>
    </Gather>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/voice-stream")
async def voice_stream(ws: WebSocket):
    """Handle the Twilio media stream — STT → Agent → TTS loop.

    Key features for natural conversation:
    - Smaller audio buffer (1.2s) for faster response
    - Silence detection to trigger processing early
    - Thinking music plays while agent is processing
    - Quick "Got it!" confirmation before long tasks
    - Barge-in: new audio clears current playback
    """
    await ws.accept()
    conversation_history: list[dict] = []
    stream_sid: str | None = None
    audio_buffer = bytearray()
    caller_phone: str | None = None
    is_playing = False  # Track if we're currently playing audio back
    silence_frames = 0  # Count consecutive silent frames

    logger.info("Voice stream connected")

    # Use Aria voice for TTS (energetic, conversational)
    VOICE_PROFILE = "cfe9ef50-307d-42c9-bd84-235ecc812aec"  # Aria

    async def send_audio(pcm_data: bytes):
        """Stream PCM audio back to Twilio."""
        nonlocal is_playing
        if stream_sid:
            is_playing = True
            media_msg = encode_twilio_media(pcm_data, stream_sid)
            await ws.send_text(media_msg)
            is_playing = False

    async def send_clear():
        """Send clear message to stop any playing audio (barge-in)."""
        if stream_sid:
            await ws.send_text(json.dumps({
                "event": "clear",
                "streamSid": stream_sid,
            }))

    async def play_thinking_music():
        """Loop thinking music while agent processes."""
        thinking_pcm = _load_thinking_audio()
        if stream_sid and thinking_pcm:
            media_msg = encode_twilio_media(thinking_pcm, stream_sid)
            await ws.send_text(media_msg)

    async def send_quick_ack(transcript: str):
        """Send a smart, context-aware voice acknowledgment with details from the transcript.

        Instead of generic "Got it!", generates dynamic phrases like:
        "Let me pull up the CMA for 100 River Road in Piscataway!"
        "Looking up homes in Edison for you!"
        """
        import re
        lower = transcript.lower()
        ack = "Got it, one moment!"

        # Extract location/address from transcript for personalized ack
        # Common patterns: "123 Main St in Edison" / "Edison NJ" / "for Piscataway"
        address_match = re.search(r'(\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|court|ct|boulevard|blvd|way|place|pl))', lower)
        city_match = re.search(r'(?:in|for|about)\s+([a-z\s]+?)(?:\s+(?:nj|new jersey|ga|georgia|ny|new york)|\s*[,.]|\s*$)', lower)
        city_name = ""
        if city_match:
            city_name = city_match.group(1).strip().title()

        if "cma" in lower or "value" in lower or "worth" in lower:
            if address_match:
                addr = address_match.group(1).strip().title()
                ack = f"Let me pull up the CMA for {addr}!"
            elif city_name:
                ack = f"Running a CMA analysis for {city_name}!"
            else:
                ack = "Running that CMA analysis now!"
        elif "market" in lower or "stats" in lower or "report" in lower:
            if city_name:
                ack = f"Pulling up market stats for {city_name}!"
            else:
                ack = "Pulling up those market stats!"
        elif "search" in lower or "homes" in lower or "house" in lower or "bedroom" in lower:
            if city_name:
                ack = f"Searching for homes in {city_name}!"
            else:
                ack = "Searching listings for you!"
        elif "email" in lower or "send" in lower:
            ack = "On it, sending that right now!"
        elif "call" in lower and ("them" in lower or "him" in lower or "her" in lower):
            ack = "Setting up that call!"
        elif "tax" in lower or "assessment" in lower:
            if address_match:
                addr = address_match.group(1).strip().title()
                ack = f"Looking up tax data for {addr}!"
            else:
                ack = "Checking the tax records!"
        elif "forecast" in lower or "predict" in lower:
            ack = "Running the price forecast!"
        elif address_match or city_name:
            # They mentioned a location but no specific action — property lookup
            loc = address_match.group(1).strip().title() if address_match else city_name
            ack = f"Let me look into {loc} for you!"
        else:
            # General question — keep it casual
            ack = "Great question, let me think about that!"

        try:
            ack_audio = await text_to_speech(ack, profile_id=VOICE_PROFILE)
            await send_audio(ack_audio)
        except Exception:
            logger.warning("Failed to send quick ack")

    def is_silence(pcm_chunk: bytes, threshold: int = 500) -> bool:
        """Check if audio chunk is mostly silence (low RMS energy)."""
        if len(pcm_chunk) < 2:
            return True
        import struct
        samples = struct.unpack(f'<{len(pcm_chunk)//2}h', pcm_chunk)
        rms = (sum(s*s for s in samples) / len(samples)) ** 0.5
        return rms < threshold

    try:
        async for raw_message in ws.iter_text():
            data = json.loads(raw_message)
            event = data.get("event")

            if event == "start":
                stream_sid = data["start"]["streamSid"]
                params = data["start"].get("customParameters", {})
                caller_phone = params.get("from")
                # Pre-seed conversation with capabilities context
                context_prompt = (
                    "A caller just connected via phone. Keep ALL responses concise and conversational — "
                    "this is a VOICE call, not a chat. Use short sentences. Never use markdown, bullets, "
                    "or lists. Speak naturally like a helpful friend on the phone. "
                    "Available tools: search_listings, search_portal_listings, get_market_report, "
                    "send_market_report_email, send_email, get_tax_data, get_forecast, cma_quick_lookup, "
                    "cma_full_report, make_outbound_call, submit_browser_task. "
                    "For property lookups, prefer cma_quick_lookup — it has a voice_summary field. "
                    "Always offer to email details after giving a verbal summary. "
                    "Keep responses under 3 sentences for voice. If data-heavy, summarize the top "
                    "2-3 points and offer to email the full report."
                )
                conversation_history.append({"role": "user", "content": f"[SYSTEM CONTEXT]: {context_prompt}"})
                conversation_history.append({"role": "assistant", "content": "Ready to help!"})
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

            # Barge-in: if caller speaks while we're playing audio, clear playback
            if is_playing and not is_silence(pcm):
                await send_clear()
                audio_buffer.clear()
                silence_frames = 0
                logger.info("Barge-in detected — cleared playback")

            audio_buffer.extend(pcm)

            # Track silence for end-of-utterance detection
            if is_silence(pcm):
                silence_frames += 1
            else:
                silence_frames = 0

            # Process when:
            # 1. We have at least 1.2s of audio AND 0.6s of trailing silence (natural pause), OR
            # 2. We have 3s of audio (hard cap, don't wait forever)
            buffer_len = len(audio_buffer)
            min_audio = 19200    # 1.2s at 8kHz * 2 bytes
            silence_threshold = 4800  # 0.3s of silence frames (each ~160 bytes)
            hard_cap = 48000    # 3s hard cap

            has_enough = buffer_len >= min_audio
            has_pause = silence_frames * 160 >= silence_threshold  # ~160 bytes per frame
            at_hard_cap = buffer_len >= hard_cap

            if not ((has_enough and has_pause) or at_hard_cap):
                continue

            chunk = bytes(audio_buffer)
            audio_buffer.clear()
            silence_frames = 0

            # 1. Speech-to-text (with error recovery — don't crash the call)
            try:
                transcript = await speech_to_text(chunk)
            except Exception as stt_err:
                logger.warning(f"STT failed (continuing): {stt_err}")
                continue
            if not transcript.strip():
                continue
            logger.info(f"Caller said: {transcript}")

            # 2. Quick acknowledgment + thinking music (in parallel)
            ack_task = asyncio.create_task(send_quick_ack(transcript))

            # 3. Run the AI agent (concurrent with ack)
            agent_task = asyncio.create_task(run_agent(transcript, conversation_history))

            # Wait for ack to finish first
            await ack_task

            # Play thinking music while agent works
            music_task = asyncio.create_task(play_thinking_music())

            # Wait for agent response
            reply, tool_results = await agent_task
            logger.info(f"Agent reply: {reply[:100]}...")

            # Clear thinking music
            await send_clear()

            # 4. Text-to-speech the reply
            reply_audio = await text_to_speech(reply, profile_id=VOICE_PROFILE)

            # 5. Stream audio back
            await send_audio(reply_audio)

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


@app.post("/outbound-twiml")
async def outbound_twiml(request: Request):
    """Twilio webhook — called when an outbound call is answered.

    Delivers the TTS message then offers DTMF options.
    """
    form = await request.form()
    call_sid = form.get("CallSid", "")
    call_info = pending_calls.pop(call_sid, {})
    contact_name = call_info.get("contact_name", "")
    message = call_info.get("message", "You have a message from CertiHomes.")

    greeting = f"Hi {contact_name}, " if contact_name else "Hi, "

    # Dynamic message must use <Say>, but options use pre-recorded for consistency
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Google.en-US-Journey-F">{greeting}this is CertiHomes AI Assistant calling. {message}</Say>
    <Gather numDigits="1" action="/outbound-action" method="POST">
        <Play>https://aiassistant.certihomes.com/voice/outbound_options.mp3</Play>
    </Gather>
    <Play>https://aiassistant.certihomes.com/voice/outbound_goodbye.mp3</Play>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.post("/outbound-action")
async def outbound_action(request: Request):
    """Handle DTMF input from the outbound call recipient."""
    form = await request.form()
    digit = form.get("Digits", "")
    host = request.headers.get("host", "aiassistant.certihomes.com")

    if digit == "1":
        # Start AI conversation via Gather speech loop with pre-recorded intro
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/voice-respond" method="POST"
            speechTimeout="2" speechModel="experimental_conversations"
            enhanced="true" language="en-US">
        <Play>https://aiassistant.certihomes.com/voice/outbound_intro.mp3</Play>
    </Gather>
    <Play>https://aiassistant.certihomes.com/voice/ack_didnt_catch.mp3</Play>
    <Redirect>/incoming-call</Redirect>
</Response>"""
    elif digit == "2":
        # Transfer to Krishna's phone
        from tools.outbound_call import KRISHNA_PHONE
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>https://aiassistant.certihomes.com/voice/outbound_connect.mp3</Play>
    <Dial callerId="{get_settings().twilio_phone_number}">
        <Number>{KRISHNA_PHONE}</Number>
    </Dial>
</Response>"""
    else:
        # Digit 3 or anything else — hang up
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>https://aiassistant.certihomes.com/voice/outbound_goodbye.mp3</Play>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


# Named page routes (before static mount)
@app.get("/crm")
async def crm_page():
    from fastapi.responses import FileResponse
    return FileResponse("static/crm.html")


# Serve static frontend (must be last — catches all unmatched routes)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
