# CLAUDE.md — AI Assistant Project Instructions

## Repository
- **GitHub:** `tlcengine/aiassistant`
- **Server:** geo2.tlcengine.com (71.172.1.247)
- **Domain:** aiassistant.certihomes.com
- **Port:** 8005 (FastAPI/uvicorn)
- **GPU:** RTX 5090 on geo2, nvidia-container-toolkit installed, needs reboot for Docker GPU access

## Quick Reference

### Service Management
```bash
sudo systemctl restart aiassistant
sudo systemctl status aiassistant
sudo journalctl -u aiassistant --since "5 min ago" --no-pager
# If port 8005 stuck: fuser -k -9 8005/tcp
```

### Key URLs
- **App:** https://aiassistant.certihomes.com
- **CRM:** https://aiassistant.certihomes.com/crm
- **Health:** https://aiassistant.certihomes.com/health
- **Widget Demo:** https://aiassistant.certihomes.com/widget-demo.html
- **Capabilities:** https://aiassistant.certihomes.com/capabilities.html
- **CMA API:** https://cmaapi.certihomes.com
- **CMA Reports:** https://cma.certihomes.com/cma/{report_uid}
- **MarketStats API:** http://localhost:8000 (PM2, on geo2)
- **VoiceBox TTS/STT:** http://localhost:17493 (Docker, on geo2)
- **LLM Proxy:** http://localhost:8080 (antigravity-proxy)
- **TLCengine API:** https://api.tlcengine.com/V3/swagger/ui/index

### Database
- **PostgreSQL:** localhost:5432, database `aiassistant`, user `aiassistant`, password `aiassistant123`
- **MongoDB (MarketStats):** 172.26.1.151:27017, database `housing-prices`, user `krish`, password in `/home/krish/marketstats/backend/.env`

## Architecture

The AI agent (`agent.py`) uses 21 tools to handle voice calls, chat, and browser automation:

### MLS Tools
- `search_listings` — Search CJMLS/FMLS by location, price, beds, baths, status
- `get_listing_detail` — Full details for a single MLS listing
- `get_market_stats` — Time-series market stats (13 metrics)
- `get_market_report` — Comprehensive report with KPIs, narrative, trends
- `get_fast_stats` — Quick all-13-metrics snapshot

### Property Tools
- `get_tax_data` — Tax assessment lookup (12.7M NJ records)
- `get_forecast` — Price forecast with confidence bands
- `predict_tax` — Predict tax from comparables
- `search_portal_listings` — CJMLS portal autocomplete search

### CMA Tools
- `cma_quick_lookup` — Quick property snapshot: tax data, MLS listing, sold comps, demographics, flood risk, voice_summary
- `cma_full_report` — Full CMA: comp selection, adjustments, pricing, AI narratives, seller net sheet (seller or buyer type)

### Communication Tools
- `send_email` — HTML email via Google Workspace SMTP
- `send_market_report_email` — Formatted market report email with KPIs
- `send_sms` — SMS via Twilio
- `send_market_report_link` — Report URL via SMS or email
- `make_outbound_call` — Outbound phone call with TTS message + DTMF menu

### CRM Tools
- `lookup_contact_by_email` — Check if email exists in CRM
- `create_crm_contact` — Add new contact to local PostgreSQL CRM
- `create_lead` — Create lead in Close CRM (external)
- `schedule_callback` — Schedule follow-up in Close CRM

### Browser Tools
- `start_browser_task` — Queue async browser automation task (Playwright headless Chrome)

### Data Flow
```
User (voice/chat/widget) --> FastAPI --> AI Agent --> Tool calls --> MarketStats/CMA/CRM/Email/Browser --> Response
                                            |
                              Voice: Pre-recorded ack MP3 (instant)
                              + agent runs in background
                              + hold music while processing
                              + Google Neural2-F TTS for reply
```

## Voice System

### Inbound Call Flow
1. `/incoming-call` — TwiML with Gather speech loop (`experimental_conversations` model)
2. Greeting: pre-recorded `greeting.mp3` (edge-tts JennyNeural)
3. Caller speaks, Twilio transcribes, sends to `/voice-respond`
4. `/voice-respond`:
   - Instant goodbye detection (skips agent, plays `ack_goodbye.mp3`)
   - Context-aware pre-recorded ack MP3 (CMA, market, search, email, tax, forecast, hello, thanks, or generic filler)
   - Agent starts processing in background
   - Redirects to `/voice-check`
5. `/voice-check`:
   - If agent not ready: plays `thinking.wav` (hold music), redirects to self
   - If agent ready: delivers reply via Google Neural2-F TTS in new Gather loop
   - After 4s silence: plays `ack_still_here.mp3`

### Outbound Call Flow
1. `make_outbound_call` tool initiates Twilio call
2. `/outbound-twiml` — Delivers TTS message (Google Journey-F voice), then plays `outbound_options.mp3`
3. `/outbound-action` — Handles DTMF:
   - 1: Enter AI conversation (Gather speech loop with `outbound_intro.mp3`)
   - 2: Transfer to Krishna (+19084305187)
   - 3: Hang up with `outbound_goodbye.mp3`

### WebSocket Stream (Legacy)
- `WS /voice-stream` — Twilio media stream with VoiceBox STT/TTS
- Barge-in, silence detection, thinking music, smart context-aware acks
- Uses Aria voice profile for TTS

### Pre-recorded Voice Files (42 MP3s in `static/voice/`)
Generated with `edge-tts --voice en-US-JennyNeural`:

**Acknowledgments (context-aware):**
- `ack_cma.mp3`, `ack_cma_1.mp3`, `ack_cma_2.mp3`, `ack_cma_3.mp3` — CMA/property value
- `ack_market.mp3`, `ack_market_1.mp3`, `ack_market_2.mp3`, `ack_market_3.mp3` — Market stats
- `ack_search.mp3`, `ack_search_1.mp3`, `ack_search_2.mp3`, `ack_search_3.mp3` — Listing search
- `ack_email.mp3`, `ack_email_1.mp3`, `ack_email_2.mp3` — Email sending
- `ack_tax.mp3`, `ack_tax_1.mp3`, `ack_tax_2.mp3` — Tax lookup
- `ack_forecast.mp3` — Price forecast
- `ack_hello.mp3`, `ack_hello_1.mp3`, `ack_hello_2.mp3`, `ack_hello_3.mp3` — Hello/greeting
- `ack_thanks.mp3`, `ack_thanks_1.mp3`, `ack_thanks_2.mp3`, `ack_thanks_3.mp3` — Thank you
- `ack_goodbye.mp3` — Goodbye (ends call instantly)
- `ack_didnt_catch.mp3` — "I didn't catch that"
- `ack_still_here.mp3` — "Are you still there?"
- `ack_general.mp3`, `ack_working.mp3` — General acks

**Fillers (generic, randomly selected):**
- `filler_1.mp3` through `filler_5.mp3`

**Outbound call:**
- `outbound_options.mp3` — DTMF menu prompt
- `outbound_intro.mp3` — AI conversation intro
- `outbound_connect.mp3` — "Connecting you now"
- `outbound_goodbye.mp3` — Outbound goodbye

**Other:**
- `greeting.mp3` — Inbound call greeting

### Generating New Voice Files
```bash
edge-tts --voice en-US-JennyNeural --text "Your text here" --write-media static/voice/filename.mp3
```

## Widget
- File: `static/widget.js`
- Shadow DOM for CSS isolation
- Mic button with browser SpeechRecognition for voice input
- Browser speechSynthesis for TTS output (prefers Google US English, Microsoft Zira, or Karen voices)
- Configurable: `data-position` (bottom-right/bottom-left), `data-color` (hex accent)
- Generates unique conversation_id per session
- Demo page: `/widget-demo.html`

## Browser Agent
- Module: `browser/`
- Playwright headless Chromium (started on app startup)
- Background task runner (`task_runner.run_forever()`) processes queue
- LLM-driven agent with 12 browser tools: navigate, click, fill, select_option, press_key, scroll, screenshot, read_page_text, search_google, wait, done, need_info
- Screenshots saved to `static/screenshots/`
- Email reply loop: `check_replies.py` monitors for user email responses
- Task statuses: pending, running, completed, failed, waiting_for_input, cancelled
- API: `POST /api/browser/tasks`, `GET /api/browser/tasks`, reply, cancel

## CMA Engine
- Quick lookup: `POST https://cmaapi.certihomes.com/api/v1/cma/quick` — returns voice_summary field ready for phone calls
- Full report: `POST https://cmaapi.certihomes.com/api/v1/cma/auto-create` — takes 10-30s, returns report_uid
- Report URL: `https://cma.certihomes.com/cma/{report_uid}`
- Types: seller (pricing + net sheet) or buyer (offer strategy)
- Coverage: NJ 3.47M parcels, GA 942K parcels, NYC 50K parcels, demographics/flood nationwide

## Code Guidelines

### Adding New Tools
1. Define tool schema in `agent.py` TOOLS list
2. Create handler function (async if I/O)
3. Add to `TOOL_HANDLERS` dict in `agent.py`
4. Update system prompt in `prompts.py`

### CRM Models
- Models in `crm/models.py`: Contact, Deal, Activity, Tag
- Enums: ContactSource (manual, gmail, phone, linkedin, facebook, instagram, twitter, website, referral, ai_assistant), LeadStatus (new, contacted, qualified, proposal, negotiation, won, lost), ActivityType (call, email, sms, meeting, note, task)
- Routes in `crm/routes.py`, async SQLAlchemy with asyncpg
- Contact fields: name, email, phone, company, title, address, social profiles (linkedin, facebook, instagram, twitter), interest, budget, desired beds/area

### Email
- SMTP via Google Workspace (smtp.gmail.com:587)
- From: claude@certihomes.com, Reply-To: krishna@certihomes.com
- Market report emails: `tools/market_report_email.py` (fetches live data, builds HTML with KPI cards, narrative, CTA buttons)
- Logo: `https://aiassistant.certihomes.com/images/certihomes-logo-email.png`

### Outbound Calls
- Tool: `make_outbound_call` in `tools/outbound_call.py`
- CRM contact name lookup (auto-resolves name to phone number)
- Pending calls stored in memory dict: `CallSid -> {message, contact_name}`
- Webhook endpoints: `/outbound-twiml`, `/outbound-action`
- Krishna's forwarding number: +19084305187

## Model Configuration
- Currently using `gemini-3-flash` via antigravity-proxy (Claude Sonnet quota exhausted)
- Switch back to `claude-sonnet-4-6` when quota resets
- Model is set in `agent.py` line ~503: `model="gemini-3-flash"`
- Proxy URL: `http://localhost:8080`

## Common Issues
- **Port 8005 in use:** `fuser -k -9 8005/tcp` then restart service
- **MongoDB auth:** Password must be in `/home/krish/marketstats/backend/.env` as `MONGODB_PASSWORD`
- **MLS field names:** MarketStats API returns lowercase (address, close_price), Bridge/RETS uses CamelCase — `tools/mls.py` handles both
- **ETL cron:** Runs hourly (`0 * * * *`) for CJMLS/FMLS data sync
- **VoiceBox blank page:** Needs geo2 reboot to fix
- **GPU Docker:** RTX 5090 installed, nvidia-container-toolkit installed, needs reboot for Docker GPU support

## Testing
```bash
# Chat test
curl -s -X POST https://aiassistant.certihomes.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is the median home price in Edison NJ?","conversation_id":"test1"}'

# CRM test
curl -s https://aiassistant.certihomes.com/api/crm/stats

# MLS test
curl -s "http://127.0.0.1:8000/api/listings/?state=New+Jersey&geo_type=City&geo_values=Edison&page_size=2&status=Closed"

# Browser task test
curl -s -X POST https://aiassistant.certihomes.com/api/browser/tasks \
  -H "Content-Type: application/json" \
  -d '{"description":"Search for Edison NJ homes on Zillow","user_email":"test@example.com"}'

# Health check
curl -s https://aiassistant.certihomes.com/health
```
