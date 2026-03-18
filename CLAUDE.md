# CLAUDE.md — AI Assistant Project Instructions

## Repository
- **GitHub:** `tlcengine/aiassistant`
- **Server:** geo2.tlcengine.com (71.172.1.247)
- **Domain:** aiassistant.certihomes.com
- **Port:** 8005 (FastAPI/uvicorn)

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
- **MarketStats API:** http://localhost:8000 (PM2, on geo2)
- **VoiceBox TTS/STT:** http://localhost:17493 (Docker, on geo2)
- **LLM Proxy:** http://localhost:8080 (antigravity-proxy)
- **TLCengine API:** https://api.tlcengine.com/V3/swagger/ui/index

### Database
- **PostgreSQL:** localhost:5432, database `aiassistant`, user `aiassistant`, password `aiassistant123`
- **MongoDB (MarketStats):** 172.26.1.151:27017, database `housing-prices`, user `krish`, password in `/home/krish/marketstats/backend/.env`

## Architecture

The AI agent (`agent.py`) uses 17 tools to handle voice calls and chat:
- **MLS tools:** search_listings, get_listing_detail, get_market_stats, get_market_report, get_fast_stats (via MarketStats API → MongoDB)
- **Property tools:** get_tax_data, get_forecast, predict_tax, search_portal_listings
- **Communication:** send_email, send_market_report_email, send_sms, send_market_report_link
- **CRM:** lookup_contact_by_email, create_crm_contact, create_lead, schedule_callback

### Data Flow
```
User (voice/chat) → FastAPI → Claude Agent → Tool calls → MarketStats/MLS/CRM/Email → Response
                                    ↓
                             VoiceBox TTS (for voice calls)
```

## Code Guidelines

### Adding New Tools
1. Define tool schema in `agent.py` TOOLS list
2. Create handler function (async if I/O)
3. Add to TOOL_HANDLERS dict in `agent.py`
4. Update system prompt in `prompts.py`

### CRM Models
- Models in `crm/models.py`: Contact, Deal, Activity, Tag
- Enums: ContactSource (manual, gmail, phone, website, ai_assistant), LeadStatus (new→won/lost), ActivityType
- Routes in `crm/routes.py`, async SQLAlchemy with asyncpg

### Email
- SMTP via Google Workspace (smtp.gmail.com:587)
- From: claude@certihomes.com, Reply-To: krishna@certihomes.com
- Market report emails: `tools/market_report_email.py` (fetches live data, builds HTML)
- Logo: `https://aiassistant.certihomes.com/images/certihomes-logo-email.png`

### Voice Calls
- Twilio streams raw audio via WebSocket to `/voice-stream`
- VoiceBox on Docker (localhost:17493) handles STT/TTS
- Audio buffer: 2 seconds of 8kHz PCM before processing
- Post-call SMS sent via `/call-status` webhook

## Model Configuration
- Currently using `gemini-3-flash` via antigravity-proxy (Claude Sonnet quota exhausted)
- Switch back to `claude-sonnet-4-6` when quota resets
- Model is set in `agent.py` line ~365: `model="gemini-3-flash"`

## Common Issues
- **Port 8005 in use:** `fuser -k -9 8005/tcp` then restart service
- **MongoDB auth:** Password must be in `/home/krish/marketstats/backend/.env` as `MONGODB_PASSWORD`
- **MLS field names:** MarketStats API returns lowercase (address, close_price), Bridge/RETS uses CamelCase — `tools/mls.py` handles both
- **ETL cron:** Runs hourly (`0 * * * *`) for CJMLS/FMLS data sync

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
```
