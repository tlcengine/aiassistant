# CertiHomes AI Assistant

AI-powered real estate assistant with voice calls, chat, CRM, browser automation, CMA reports, and MLS data. Handles inbound and outbound phone calls via Twilio, provides an embeddable chat widget for any website, runs headless browser tasks asynchronously, and manages a full CRM with deal pipeline.

## Architecture

```
                         +19084305187 (Twilio)
                               |
                    Inbound    |    Outbound
                    calls      |    calls
                       v       |       v
              /incoming-call   |  /outbound-twiml
                       |       |       |
        Twilio Gather  |       |  TTS message + DTMF menu
        (speech STT)   |       |  (1=AI, 2=Krishna, 3=Bye)
                       v       v
                   /voice-respond
                       |
          Pre-recorded ack MP3 (instant)
                       |
          Agent runs in background
                       |
          /voice-check polls until ready
                       |
          Google Neural2-F TTS delivers reply
                       |
                  Gather loop continues
                       |
                 /call-status (post-call SMS)


Web Chat Widget (any site)            Chat API
<script src=".../widget.js">   --->   POST /chat
  Shadow DOM, mic button,                |
  browser STT/TTS                  AI Agent (Claude/Gemini)
                                         |
                                   21 tool calls
                                    /    |    \
                        MLS/CMA    CRM   Email/SMS   Browser Agent
                           |        |        |             |
                    MarketStats  PostgreSQL  SMTP     Playwright
                    (MongoDB)               Twilio   (headless Chrome)

CRM Dashboard                     Browser Agent
/crm                              /api/browser/tasks
  Contacts, Deals,                  Async task queue
  Pipeline Kanban,                  Email reply loop
  Gmail Import                      Screenshot results
```

## Features

### Voice Calls (Inbound)
- Twilio phone number: +1 (908) 430-5187
- Twilio Gather speech loop with `experimental_conversations` model
- Pre-recorded acknowledgment MP3s for instant response (no TTS delay)
- Context-aware acks: CMA, market, search, email, tax, forecast, hello, thanks, goodbye
- Hold music (`thinking.wav`) while agent processes
- Google Neural2-F TTS for agent responses
- Barge-in support (new speech clears current playback)
- Instant goodbye detection (bypasses agent entirely)
- "Still here?" prompt after silence
- Post-call SMS follow-up via `/call-status`

### Voice Calls (Outbound)
- `make_outbound_call` tool — delivers TTS message to any phone number
- CRM contact name lookup (no phone number needed if contact exists)
- 3-option DTMF menu after message delivery:
  - Press 1: Talk to AI assistant (enters Gather speech loop)
  - Press 2: Connect with Krishna (call transfer)
  - Press 3: Hang up
- Pre-recorded options, intro, connect, and goodbye MP3s

### Chat Widget
- Single script tag installation: `<script src="https://aiassistant.certihomes.com/widget.js"></script>`
- Shadow DOM isolation (no CSS conflicts)
- Floating "C AI" bubble with pulse animation
- Mic button for voice input (browser SpeechRecognition API)
- Text-to-speech for responses (browser speechSynthesis API)
- Configurable position (`data-position`) and accent color (`data-color`)
- Works on any website: Next.js, React, plain HTML, WordPress

### CMA Engine
- **Quick lookup** (`cma_quick_lookup`): Tax data, MLS listing, nearby sold comps, demographics, flood risk, voice-ready summary
- **Full report** (`cma_full_report`): Comp selection, adjustments, pricing recommendation, AI narratives, seller net sheet
- API: `https://cmaapi.certihomes.com/api/v1/cma/quick` and `/api/v1/cma/auto-create`
- Report viewer: `https://cma.certihomes.com/cma/{report_uid}`
- Coverage: NJ (3.47M parcels + CJMLS), GA (942K parcels + FMLS), NYC (50K parcels), demographics/flood nationwide

### MLS Search
- CJMLS: ~298K listings (Central Jersey — Edison, Princeton, Monroe, etc.)
- FMLS: ~1.2M listings (Georgia)
- Search by city, zip, price, beds, baths, property type, status
- Market stats: 13 metrics (MedianSalesPrice, DaysOnMarket, Inventory, AbsorptionRate, etc.)
- Market reports with KPIs, narrative analysis, trends
- Tax data: 12.7M NJ property records
- Price forecasts with confidence bands
- Portal URLs: `https://krishnam.tlcengine.com/propertydetail/{id}/...`

### Market Report Emails
- Beautiful HTML emails with KPI cards, narrative, supply/demand analysis
- Links to interactive report at `marketstats.certihomes.com`
- Links to AI-generated podcast
- CertiHomes branding with logo
- Plain text fallback

### Browser Agent
- Headless Chrome via Playwright
- Async task queue (tasks run in background)
- 12 browser tools: navigate, click, fill, select, press_key, scroll, screenshot, read_page_text, search_google, wait, done, need_info
- Email results to user when complete
- Email reply loop: if agent needs more info, emails a question, user replies, agent continues
- Screenshot capture and storage
- Use cases: restaurant reservations, web research, form filling, competitor analysis

### CRM
- **Contacts**: CRUD, search, filter by status/source, social profiles, real estate interests
- **Deals**: Pipeline with value tracking, property address, MLS ID, expected close date
- **Pipeline**: Kanban view grouped by stage (New, Contacted, Qualified, Proposal, Negotiation, Won)
- **Activities**: Calls, emails, SMS, meetings, notes, tasks
- **Tags**: Color-coded, many-to-many with contacts
- **Gmail Import**: OAuth flow, contact extraction, dedup by gmail_contact_id
- **Dashboard stats**: Total contacts, pipeline value, contacts by status
- **Lead sources**: Manual, Gmail, Phone, LinkedIn, Facebook, Instagram, Twitter, Website, Referral, AI Assistant
- **Auto lead capture**: After email send, checks CRM, asks for name/cell if new, creates contact

### Email & SMS
- SMTP via Google Workspace (smtp.gmail.com:587)
- From: claude@certihomes.com, Reply-To: krishna@certihomes.com
- SMS via Twilio (+19084305187)
- Post-call follow-up SMS

## Tech Stack

- **Runtime:** Python 3.12, FastAPI, uvicorn
- **AI:** Claude/Gemini via antigravity-proxy (localhost:8080), currently `gemini-3-flash`
- **Voice:** Twilio (Gather speech + WebSocket streams), VoiceBox TTS/STT (Docker, localhost:17493), edge-tts (JennyNeural for pre-recorded files), Google Neural2-F (live TTS)
- **Browser:** Playwright (headless Chromium)
- **Data:** MarketStats API (localhost:8000, PM2), MongoDB (housing-prices), PostgreSQL (CRM)
- **Email:** Google Workspace SMTP, Twilio SMS
- **Frontend:** Vanilla HTML/JS (chat UI, CRM dashboard, widget)

## API Endpoints

### Chat
- `POST /chat` — Text chat with AI agent (JSON: `{message, conversation_id}`)
- `GET /health` — Health check

### Voice (Inbound)
- `POST /incoming-call` — Twilio webhook, returns TwiML with Gather speech loop
- `POST /voice-respond` — Processes caller speech, starts agent, returns ack + redirect
- `POST /voice-check` / `GET /voice-check` — Polls for agent response, delivers via TTS
- `WS /voice-stream` — Twilio media stream (WebSocket STT/TTS loop, legacy)
- `POST /call-status` — Post-call SMS follow-up

### Voice (Outbound)
- `POST /outbound-twiml` — TwiML for answered outbound calls (message + DTMF menu)
- `POST /outbound-action` — Handles DTMF input (1=AI, 2=transfer, 3=hangup)

### CRM Contacts
- `GET /api/crm/contacts` — List contacts (query: `q`, `status`, `source`, `limit`, `offset`)
- `POST /api/crm/contacts` — Create contact
- `GET /api/crm/contacts/{id}` — Get contact with activities and deals
- `PATCH /api/crm/contacts/{id}` — Update contact
- `DELETE /api/crm/contacts/{id}` — Delete contact
- `POST /api/crm/contacts/{id}/tags/{tag_id}` — Add tag to contact

### CRM Deals
- `GET /api/crm/deals` — List deals (query: `status`, `limit`)
- `POST /api/crm/deals` — Create deal
- `GET /api/crm/deals/{id}` — Get deal
- `PATCH /api/crm/deals/{id}` — Update deal
- `DELETE /api/crm/deals/{id}` — Delete deal
- `GET /api/crm/pipeline` — Kanban pipeline view (deals grouped by stage)

### CRM Other
- `GET /api/crm/stats` — Dashboard statistics
- `GET /api/crm/tags` — List tags
- `POST /api/crm/tags` — Create tag
- `POST /api/crm/activities` — Log activity

### Gmail
- `GET /api/crm/gmail/auth` — Start OAuth flow
- `GET /api/crm/gmail/callback` — OAuth callback
- `GET /api/crm/gmail/status` — Check if Gmail is connected
- `POST /api/crm/gmail/import` — Import contacts from Gmail

### Browser Agent
- `POST /api/browser/tasks` — Create browser task
- `GET /api/browser/tasks` — List tasks (query: `status`, `limit`)
- `GET /api/browser/tasks/{id}` — Get task status
- `POST /api/browser/tasks/{id}/reply` — Reply to task waiting for input
- `POST /api/browser/tasks/{id}/cancel` — Cancel task

### Static Pages
- `/` — Chat UI (index.html)
- `/crm` — CRM dashboard
- `/widget-demo.html` — Widget demo page
- `/capabilities.html` — Capabilities guide

## Pre-recorded Voice Files (42 MP3s in `static/voice/`)

Generated with `edge-tts` using the `en-US-JennyNeural` voice.

| File | Purpose |
|------|---------|
| `greeting.mp3` | Inbound call greeting |
| `ack_cma.mp3`, `ack_cma_1-3.mp3` | CMA/property value acknowledgments |
| `ack_market.mp3`, `ack_market_1-3.mp3` | Market stats acknowledgments |
| `ack_search.mp3`, `ack_search_1-3.mp3` | Listing search acknowledgments |
| `ack_email.mp3`, `ack_email_1-2.mp3` | Email sending acknowledgments |
| `ack_tax.mp3`, `ack_tax_1-2.mp3` | Tax lookup acknowledgments |
| `ack_forecast.mp3` | Price forecast acknowledgment |
| `ack_hello.mp3`, `ack_hello_1-3.mp3` | Hello/greeting responses |
| `ack_thanks.mp3`, `ack_thanks_1-3.mp3` | Thank you responses |
| `ack_goodbye.mp3` | Goodbye (ends call) |
| `ack_didnt_catch.mp3` | "I didn't catch that" |
| `ack_still_here.mp3` | "Are you still there?" |
| `ack_general.mp3` | General acknowledgment |
| `ack_working.mp3` | Working on it |
| `filler_1-5.mp3` | Generic filler phrases |
| `outbound_options.mp3` | DTMF menu options |
| `outbound_intro.mp3` | Outbound call AI intro |
| `outbound_connect.mp3` | "Connecting you now" |
| `outbound_goodbye.mp3` | Outbound call goodbye |

## AI Agent Tools (21 tools)

| Tool | Description |
|------|-------------|
| `search_listings` | Search CJMLS/FMLS listings by location, price, beds, baths |
| `get_listing_detail` | Full details for a single MLS listing |
| `get_market_stats` | Time-series market stats (13 metrics) |
| `get_market_report` | Comprehensive market report with KPIs and narrative |
| `get_fast_stats` | Quick all-13-metrics snapshot |
| `get_tax_data` | Property tax assessment lookup (12.7M records) |
| `get_forecast` | Price forecast with confidence bands |
| `predict_tax` | Predict property tax from comparables |
| `send_email` | Send HTML email via Google Workspace |
| `send_market_report_email` | Send formatted market report email |
| `send_sms` | Send SMS via Twilio |
| `send_market_report_link` | Send report URL via SMS or email |
| `search_portal_listings` | Search CJMLS portal (autocomplete) |
| `lookup_contact_by_email` | Check if email exists in CRM |
| `create_crm_contact` | Add new contact to CRM |
| `create_lead` | Create lead in Close CRM (external) |
| `schedule_callback` | Schedule follow-up in Close CRM |
| `cma_quick_lookup` | Quick property snapshot with voice summary |
| `cma_full_report` | Full CMA report (seller/buyer) |
| `start_browser_task` | Async browser automation task |
| `make_outbound_call` | Outbound phone call with message delivery |

## Project Structure

```
aiassistant/
├── main.py                  # FastAPI server, Twilio webhooks, voice endpoints
├── agent.py                 # AI agent with 21 tool definitions and handlers
├── config.py                # Settings (env vars, API keys, Pydantic)
├── prompts.py               # System prompt for the AI agent
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (not committed)
├── crm/
│   ├── database.py          # SQLAlchemy async engine, session factory
│   ├── models.py            # Contact, Deal, Activity, Tag models
│   ├── routes.py            # CRM REST API endpoints
│   ├── gmail_routes.py      # Gmail OAuth + import routes
│   └── gmail_import.py      # Gmail contact extraction logic
├── tools/
│   ├── mls.py               # MLS listing search, market stats, tax, forecasts
│   ├── email_sender.py      # SMTP email sending (Google Workspace)
│   ├── market_report_email.py  # HTML market report email builder
│   ├── crm_tools.py         # CRM lookup/create for AI agent
│   ├── sms.py               # Twilio SMS
│   ├── outbound_call.py     # Outbound voice calls via Twilio
│   └── close_crm.py         # Close CRM integration (external)
├── voice/
│   ├── twilio_audio.py      # Twilio media stream encode/decode (mu-law PCM)
│   └── voicebox_client.py   # VoiceBox TTS/STT client (with gTTS fallback)
├── browser/
│   ├── browser_agent.py     # LLM-driven browser automation agent
│   ├── browser_pool.py      # Playwright browser lifecycle management
│   ├── browser_tools.py     # 12 browser tool definitions and handlers
│   ├── models.py            # BrowserTask SQLAlchemy model
│   ├── prompts.py           # Browser agent system prompt
│   ├── routes.py            # Browser task API endpoints
│   ├── task_runner.py       # Background task queue processor
│   └── check_replies.py     # Email reply loop checker
├── static/
│   ├── index.html           # Chat UI
│   ├── crm.html             # CRM dashboard with pipeline Kanban
│   ├── widget.js            # Embeddable chat widget (Shadow DOM)
│   ├── widget-demo.html     # Widget demo page
│   ├── capabilities.html    # Capabilities guide
│   ├── thinking.wav         # Hold music for voice calls
│   ├── voice/               # 42 pre-recorded MP3 acknowledgments
│   ├── images/              # Logo assets
│   └── screenshots/         # Browser agent screenshots
└── deploy/
    ├── aiassistant.service   # systemd unit file
    └── nginx-aiassistant.conf  # Nginx reverse proxy config
```

## Deployment

**Server:** geo2.tlcengine.com (71.172.1.247, Ubuntu)
**Port:** 8005
**Domain:** aiassistant.certihomes.com (Nginx reverse proxy with SSL)
**Service:** `systemctl status aiassistant`

### Service Management

```bash
sudo systemctl restart aiassistant
sudo systemctl status aiassistant
sudo journalctl -u aiassistant --since "5 min ago" --no-pager

# If port 8005 stuck after restart:
fuser -k -9 8005/tcp
```

### Dependencies
- **antigravity-proxy** on localhost:8080 (LLM API proxy)
- **VoiceBox** Docker container on localhost:17493 (TTS/STT)
- **MarketStats API** on localhost:8000 (PM2 managed, MongoDB backend)
- **PostgreSQL** on localhost:5432 (database: aiassistant)
- **CMA API** at cmaapi.certihomes.com (external)

### Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set up .env (see Environment Variables below)
cp .env.example .env

# Initialize database
python -c "from crm.database import init_db; import asyncio; asyncio.run(init_db())"

# Run
uvicorn main:app --host 0.0.0.0 --port 8005 --reload
```

## Environment Variables

```
ANTHROPIC_API_KEY=...
CLAUDE_PROXY_URL=http://localhost:8080
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+19084305187
SMTP_APP_PASSWORD=...
TLCENGINE_API_URL=https://api.tlcengine.com/V3/api/km
DATABASE_URL=postgresql+asyncpg://aiassistant:aiassistant123@localhost:5432/aiassistant
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
VOICEBOX_URL=http://127.0.0.1:17493
CLOSE_API_KEY=...
```

## Widget Installation

Add one line before `</body>` on any page:

```html
<script src="https://aiassistant.certihomes.com/widget.js"></script>
```

See [WIDGET_INSTALL.md](WIDGET_INSTALL.md) for framework-specific instructions.

## Testing

```bash
# Chat test
curl -s -X POST https://aiassistant.certihomes.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is the median home price in Edison NJ?","conversation_id":"test1"}'

# CRM stats
curl -s https://aiassistant.certihomes.com/api/crm/stats

# MLS search
curl -s "http://127.0.0.1:8000/api/listings/?state=New+Jersey&geo_type=City&geo_values=Edison&page_size=2&status=Closed"

# Browser task
curl -s -X POST https://aiassistant.certihomes.com/api/browser/tasks \
  -H "Content-Type: application/json" \
  -d '{"description":"Search Google for Edison NJ real estate trends","user_email":"test@example.com"}'

# Health check
curl -s https://aiassistant.certihomes.com/health
```

## License

Proprietary — TLCengine / CertiHomes
