# AI Assistant — Todo List

## Completed
- [x] FastAPI server with Twilio voice + chat endpoints
- [x] AI agent with 21 MLS/CRM/email/CMA/browser/outbound tools
- [x] VoiceBox TTS/STT integration (Docker on geo2)
- [x] MLS listing search via MarketStats API (CJMLS ~298K + FMLS ~1.2M)
- [x] Market report HTML email with KPIs, narrative, podcast links
- [x] SMTP email sending via Google Workspace (claude@certihomes.com)
- [x] CertiHomes logo in emails (PNG on black background)
- [x] PostgreSQL CRM: contacts, deals, activities, tags
- [x] CRM dashboard UI (list view, filters, search, stats)
- [x] Deal CRUD API (create, read, update, delete)
- [x] Pipeline API endpoint (deals grouped by stage for Kanban)
- [x] Gmail OAuth + contact import
- [x] Auto lead capture after email (lookup CRM -> ask name/cell -> create)
- [x] Portal URL integration (krishnam.tlcengine.com property links)
- [x] Tax data lookup and price forecast tools
- [x] Natural voice greeting (no IVR, mentions Central Jersey)
- [x] MongoDB auth fix for MarketStats
- [x] MLS field mapping (lowercase + CamelCase)
- [x] VoiceBox delete button for failed generation cards
- [x] ETL cron set to hourly
- [x] Systemd service + Nginx reverse proxy + SSL
- [x] Twilio post-call SMS follow-up
- [x] Pre-recorded voice acks (42 MP3s via edge-tts JennyNeural)
- [x] Context-aware ack selection (CMA, market, search, email, tax, forecast, hello, thanks, goodbye, filler)
- [x] Instant goodbye detection (bypasses agent, plays ack_goodbye.mp3)
- [x] Hold music (thinking.wav) while agent processes
- [x] Twilio Gather speech loop with experimental_conversations model
- [x] Async agent processing with /voice-check polling
- [x] "Still here?" prompt after silence
- [x] CMA quick lookup tool (voice_summary for phone calls)
- [x] CMA full report tool (seller/buyer with comp adjustments, AI narratives, net sheet)
- [x] Outbound calls via make_outbound_call tool
- [x] Outbound call DTMF menu (1=AI, 2=Krishna transfer, 3=hangup)
- [x] CRM contact name-to-phone lookup for outbound calls
- [x] Pre-recorded outbound MP3s (options, intro, connect, goodbye)
- [x] Embeddable chat widget (widget.js, Shadow DOM, single script tag)
- [x] Widget voice support (mic button, browser SpeechRecognition + speechSynthesis)
- [x] Widget customization (data-position, data-color)
- [x] Browser agent with headless Chrome (Playwright)
- [x] Browser task queue with async processing
- [x] 12 browser tools (navigate, click, fill, screenshot, search_google, etc.)
- [x] Browser agent email results delivery
- [x] Browser agent email reply loop (need_info -> email question -> user replies -> continues)
- [x] Browser task API (create, list, get, reply, cancel)
- [x] Capabilities guide page (capabilities.html)
- [x] Widget demo page (widget-demo.html)

## Recently Completed (2026-03-18 Post-Reboot)
- [x] Reboot geo2 for GPU Docker support — completed successfully
- [x] VoiceBox blank page fix — fixed by copying frontend dist files into container
- [x] GPU Docker support — working with `--runtime=nvidia` (nvidia is default runtime, RTX 5090 detected, 32GB VRAM, CUDA 13.1)
- [x] Pre-recorded voice files regenerated with edge-tts JennyNeural (+8% rate)
- [x] Varied fillers and hold music created (5 general, 3 CMA, 3 market, 3 search, 2 email, 2 tax, 3 hello, 3 thanks)
- [x] Hold music: 15s WAV with C-Am-F-G chord progression
- [x] Outbound calls verified working (Twilio 201 response confirmed)
- [x] All 18 PM2 apps online after reboot
- [x] End-to-end voice call testing with all tools (CMA, outbound, browser tasks)

## In Progress
- [ ] CRM deal pipeline Kanban UI with drag-and-drop cards (backend done, frontend pending)

## Pending
- [ ] VoiceBox GPU rebuild — currently CPU mode, rebuild with `docker-compose up -d --build`
- [ ] `--gpus all` Docker flag fix (known driver 590 + toolkit 1.19 compat bug, low priority — `--runtime=nvidia` works)
- [ ] Switch model back to Claude Sonnet when quota resets (currently gemini-3-flash)
- [ ] Google OAuth scopes expansion (Gmail read/send, Drive, Contacts, Calendar)
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
- `--gpus all` Docker flag has known bug with NVIDIA driver 590 + toolkit 1.19 (use `--runtime=nvidia` instead)
- VoiceBox running in CPU mode until GPU rebuild
