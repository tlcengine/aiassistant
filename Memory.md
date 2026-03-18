# Memory — AI Assistant Project Context

## Project Identity
- **Name:** CertiHomes AI Assistant
- **Repo:** tlcengine/aiassistant (GitHub)
- **Server:** geo2.tlcengine.com (71.172.1.247, internal 172.26.1.151)
- **Domain:** aiassistant.certihomes.com
- **Port:** 8005
- **Owner:** Krish (krishna@certihomes.com)

## Infrastructure
- **LLM Proxy:** antigravity-proxy on localhost:8080 (supports Claude, Gemini, etc.)
- **Current Model:** gemini-3-flash (Claude Sonnet quota exhausted, resets periodically)
- **Preferred Model:** claude-sonnet-4-6
- **VoiceBox:** Docker container on localhost:17493 (TTS/STT, Chatterbox engine)
- **MarketStats API:** PM2 on localhost:8000 (Python FastAPI, MongoDB backend)
- **MongoDB:** 172.26.1.151:27017 (database: housing-prices, user: krish)
- **PostgreSQL:** localhost:5432 (database: aiassistant, user: aiassistant)
- **Twilio Phone:** +19084305187
- **Email:** claude@certihomes.com (SMTP via smtp.gmail.com:587, App Password)
- **Reply-To:** krishna@certihomes.com

## Key API Endpoints
- **TLCengine V3:** https://api.tlcengine.com/V3/api/km (Swagger at /V3/swagger/docs/v2)
- **Property Portal:** https://krishnam.tlcengine.com (React SPA on prod.tlcengine.com)
- **Next.js Portal:** https://nextjs.tlcengine.com (on geo2:6969)
- **Market Reports:** https://marketstats.certihomes.com/report?city={slug}&state=new-jersey
- **Podcasts:** marketstats.certihomes.com (linked in market report emails)

## Data Sources
- **CJMLS:** Central Jersey MLS (~298K listings) — Edison, Princeton, Monroe, New Brunswick, etc.
- **FMLS:** Broader MLS feed (~1.2M listings)
- **Tax Records:** 12.7M NJ property assessment records
- **ETL:** Hourly cron job (`0 * * * *`) syncs CJMLS/FMLS to MongoDB

## CRM Schema
- **LeadStatus enum:** new, contacted, qualified, proposal, negotiation, won, lost
- **ContactSource enum:** manual, gmail, phone, website, ai_assistant, referral
- **ActivityType enum:** call, email, meeting, task, note, sms
- **Models:** Contact, Deal, Activity, Tag (with many-to-many contact_tags)

## Email Logo
- **URL:** https://aiassistant.certihomes.com/images/certihomes-logo-email.png
- **Specs:** 660x320px PNG, CertiHomes logo on black background, 200px height in emails

## Voice Call Flow
1. Twilio hits POST /incoming-call → TwiML with greeting + WebSocket connect
2. Audio streams to WS /voice-stream → VoiceBox STT → transcript
3. Transcript → AI agent with tool calls → reply text
4. Reply → VoiceBox TTS → audio → stream back to Twilio
5. On call end → POST /call-status → sends follow-up SMS

## Agent Lead Capture Flow
1. User requests email to someone → agent sends email
2. Agent calls lookup_contact_by_email → checks CRM
3. If not found → asks for name ("Who should I say this is from?")
4. Optionally asks for cell number
5. Calls create_crm_contact with name, email, phone, interest, notes

## Session Decisions
- Natural greeting (no IVR 1/2/3 menu) — "Welcome to CertiHomes! What would you like to do?"
- Emails can go to ANY address, not just CRM contacts
- Market report emails include interactive report link + podcast link
- Central Jersey coverage noted in greeting
- Voice responses kept under 3 sentences
- Confirm what caller said before executing ("Just to make sure I heard you right...")

## File Locations
- **Agent:** /home/krish/aiassistant/agent.py (17 tools, handlers)
- **Prompts:** /home/krish/aiassistant/prompts.py (system prompt)
- **MLS Tools:** /home/krish/aiassistant/tools/mls.py
- **Email:** /home/krish/aiassistant/tools/email_sender.py
- **Market Email:** /home/krish/aiassistant/tools/market_report_email.py
- **CRM Tools:** /home/krish/aiassistant/tools/crm_tools.py
- **CRM Models:** /home/krish/aiassistant/crm/models.py
- **CRM Routes:** /home/krish/aiassistant/crm/routes.py
- **CRM UI:** /home/krish/aiassistant/static/crm.html
- **Chat UI:** /home/krish/aiassistant/static/index.html
- **Deploy:** /home/krish/aiassistant/deploy/ (systemd + nginx configs)
- **MarketStats:** /home/krish/marketstats/ (separate PM2 app)
- **VoiceBox:** Docker container (voicebox), source at /DataDrive/krish/krish/voicebox/

## Network Reference
- geo2: 71.172.1.247 (internal 172.26.1.151) — this server
- geo: 71.172.1.245 (internal 172.26.1.45) — main Ubuntu server
- prod: 71.172.1.248 (internal 172.26.1.80) — krishnam.tlcengine.com
- tfs: 71.172.1.244 (internal 172.26.1.20) — Windows source server
