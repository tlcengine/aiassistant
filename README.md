# CertiHomes AI Assistant

AI-powered real estate assistant for CertiHomes — handles phone calls (Twilio), chat, MLS property searches, market reports, email delivery, and CRM management.

## Architecture

```
Twilio (+19084305187)
  └─ WebSocket media stream
       └─ VoiceBox STT → AI Agent (Claude/Gemini) → VoiceBox TTS
            └─ Tool calls: MLS search, market reports, email, CRM

Web Chat (aiassistant.certihomes.com)
  └─ POST /chat → AI Agent → tool results + reply

CRM Dashboard (aiassistant.certihomes.com/crm)
  └─ Contacts, Deals, Pipeline Kanban, Gmail Import
```

## Stack

- **Runtime:** Python 3.11, FastAPI, uvicorn
- **AI:** Anthropic Claude API (via antigravity-proxy) with 17+ tools
- **Voice:** Twilio WebSocket streams, VoiceBox TTS/STT (Docker on geo2)
- **Data:** MarketStats API (CJMLS ~298K listings, FMLS ~1.2M), MongoDB (housing-prices), PostgreSQL (CRM)
- **Email:** Google Workspace SMTP (claude@certihomes.com, reply-to krishna@certihomes.com)
- **Portal:** krishnam.tlcengine.com (CJMLS property pages), TLCengine V3 API

## Features

### Voice & Chat Agent
- Natural language phone greeting (no IVR menus)
- Property search by city, zip, price, beds/baths
- Market reports with KPIs (median price, DOM, inventory, absorption rate)
- Tax data lookup (12.7M NJ property records)
- Price forecasts with confidence bands
- Email delivery of listings and HTML market reports
- SMS via Twilio
- Auto lead capture: after email send, checks CRM → asks name/cell if new → creates contact

### CRM
- Contact management (CRUD, search, filter by status/source)
- Deal pipeline with Kanban view (drag-and-drop)
- Activity tracking (calls, emails, tasks)
- Tag system
- Gmail import integration
- Dashboard stats (total contacts, pipeline value)
- Lead statuses: New → Contacted → Qualified → Proposal → Negotiation → Won/Lost

### Market Reports
- Beautiful HTML email reports with KPI cards, narrative analysis
- Links to interactive report at marketstats.certihomes.com
- Links to AI-generated podcast
- CertiHomes branding with logo

## Project Structure

```
aiassistant/
├── main.py              # FastAPI server, Twilio webhooks, WebSocket voice stream
├── agent.py             # Claude agent with 17 tool definitions and handlers
├── config.py            # Settings (env vars, API keys)
├── prompts.py           # System prompt for the AI agent
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (not committed)
├── crm/
│   ├── database.py      # SQLAlchemy async engine, session factory
│   ├── models.py        # Contact, Deal, Activity, Tag models
│   ├── routes.py        # CRM REST API endpoints
│   ├── gmail_routes.py  # Gmail OAuth + import routes
│   └── gmail_import.py  # Gmail contact extraction logic
├── tools/
│   ├── mls.py           # MLS listing search, market stats, tax data, forecasts
│   ├── email_sender.py  # SMTP email sending (Google Workspace)
│   ├── market_report_email.py  # HTML market report email builder
│   ├── crm_tools.py     # CRM lookup/create for AI agent
│   ├── sms.py           # Twilio SMS
│   └── close_crm.py     # Close CRM integration (external)
├── voice/
│   ├── twilio_audio.py  # Twilio media stream encode/decode
│   └── voicebox_client.py  # VoiceBox TTS/STT client
├── static/
│   ├── index.html       # Chat UI
│   ├── crm.html         # CRM dashboard with pipeline Kanban
│   └── images/          # Logo assets
└── deploy/
    ├── aiassistant.service  # systemd unit file
    └── nginx-aiassistant.conf  # Nginx reverse proxy config
```

## Deployment

**Server:** geo2.tlcengine.com (71.172.1.247, Ubuntu)
**Port:** 8005
**Domain:** aiassistant.certihomes.com (Nginx reverse proxy with SSL)
**Service:** `systemctl status aiassistant`

### Dependencies
- **antigravity-proxy** on localhost:8080 (LLM API proxy)
- **VoiceBox** Docker container on localhost:17493 (TTS/STT)
- **MarketStats API** on localhost:8000 (PM2 managed, MongoDB backend)
- **PostgreSQL** on localhost:5432 (database: aiassistant)

### Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up .env (see .env.example)
cp .env.example .env

# Initialize database
python -c "from crm.database import init_db; import asyncio; asyncio.run(init_db())"

# Run
uvicorn main:app --host 0.0.0.0 --port 8005 --reload
```

## API Endpoints

### Chat
- `POST /chat` — Text chat with AI agent
- `GET /health` — Health check

### Voice (Twilio)
- `POST /incoming-call` — Twilio webhook, returns TwiML
- `WS /voice-stream` — Twilio media stream (STT → Agent → TTS)
- `POST /call-status` — Post-call SMS follow-up

### CRM
- `GET/POST /api/crm/contacts` — List/create contacts
- `GET/PATCH/DELETE /api/crm/contacts/{id}` — Contact CRUD
- `GET/POST /api/crm/deals` — List/create deals
- `GET/PATCH/DELETE /api/crm/deals/{id}` — Deal CRUD
- `GET /api/crm/pipeline` — Kanban pipeline view
- `GET /api/crm/stats` — Dashboard statistics
- `GET/POST /api/crm/tags` — Tag management
- `POST /api/crm/activities` — Log activities

### Gmail
- `GET /api/crm/gmail/auth` — OAuth flow
- `GET /api/crm/gmail/callback` — OAuth callback
- `POST /api/crm/gmail/import` — Import contacts from Gmail

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
```

## License

Proprietary — TLCengine / CertiHomes
