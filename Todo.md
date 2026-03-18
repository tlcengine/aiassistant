# AI Assistant — Todo List

## Completed
- [x] FastAPI server with Twilio voice + chat endpoints
- [x] AI agent with 17 MLS/CRM/email tools
- [x] VoiceBox TTS/STT integration (Docker on geo2)
- [x] MLS listing search via MarketStats API (CJMLS + FMLS)
- [x] Market report HTML email with KPIs, narrative, podcast links
- [x] SMTP email sending via Google Workspace (claude@certihomes.com)
- [x] CertiHomes logo in emails (PNG on black background)
- [x] PostgreSQL CRM: contacts, deals, activities, tags
- [x] CRM dashboard UI (list view, filters, search, stats)
- [x] Deal CRUD API (create, read, update, delete)
- [x] Pipeline API endpoint (deals grouped by stage for Kanban)
- [x] Gmail OAuth + contact import
- [x] Auto lead capture after email (lookup CRM → ask name/cell → create)
- [x] Portal URL integration (krishnam.tlcengine.com property links)
- [x] Tax data lookup and price forecast tools
- [x] Natural voice greeting (no IVR, mentions Central Jersey)
- [x] MongoDB auth fix for MarketStats
- [x] MLS field mapping (lowercase + CamelCase)
- [x] VoiceBox delete button for failed generation cards
- [x] ETL cron set to hourly
- [x] Systemd service + Nginx reverse proxy + SSL
- [x] Twilio post-call SMS follow-up

## In Progress
- [ ] CRM deal pipeline Kanban UI with drag-and-drop cards (backend done, frontend pending)

## Pending
- [ ] Switch model back to Claude Sonnet when quota resets
- [ ] End-to-end voice call test with real phone call
- [ ] Google OAuth scopes expansion (Gmail read/send, Drive, Contacts, Calendar, Tasks)
- [ ] Email analysis engine for CRM relationship scoring
- [ ] Contact detail page with activity timeline and deals
- [ ] Deal edit modal in pipeline view
- [ ] Bulk email/SMS campaigns from CRM
- [ ] Webhook for Twilio call recordings
- [ ] Analytics dashboard (call volume, email opens, conversion rates)
- [ ] Mobile-responsive CRM improvements
- [ ] Import contacts from CSV/Excel
- [ ] CRM notes/activity logging from AI calls
- [ ] Automated follow-up sequences (drip emails)
- [ ] Calendar integration for showings/callbacks

## Known Issues
- Port 8005 occasionally sticks on restart — use `fuser -k -9 8005/tcp`
- Claude Sonnet quota exhausted — currently using gemini-3-flash as fallback
- Systemd restarts need sudo password
