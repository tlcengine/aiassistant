(function() {
  'use strict';

  const API_URL = 'https://aiassistant.certihomes.com';
  const LOGO_URL = API_URL + '/images/certihomes-logo-email.png';

  // Read optional config from script tag attributes
  const currentScript = document.currentScript;
  const position = currentScript ? currentScript.getAttribute('data-position') : null;
  const customColor = currentScript ? currentScript.getAttribute('data-color') : null;

  const isLeft = position === 'bottom-left';
  const accentColor = customColor || '#3b82f6';

  // Generate unique conversation ID
  const conversationId = 'w_' + Math.random().toString(36).substr(2, 9) + Date.now().toString(36);

  // Conversation history (in-memory only)
  const messages = [];

  // Create host element and shadow DOM
  const host = document.createElement('div');
  host.id = 'certihomes-ai-widget';
  document.body.appendChild(host);
  const shadow = host.attachShadow({ mode: 'closed' });

  // Inject styles
  const style = document.createElement('style');
  style.textContent = `
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    @keyframes ch-pulse {
      0% { box-shadow: 0 4px 20px rgba(56, 189, 248, 0.4); }
      50% { box-shadow: 0 4px 30px rgba(56, 189, 248, 0.7), 0 0 40px rgba(129, 140, 248, 0.3); }
      100% { box-shadow: 0 4px 20px rgba(56, 189, 248, 0.4); }
    }

    @keyframes ch-slide-up {
      from { opacity: 0; transform: translateY(20px) scale(0.95); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }

    @keyframes ch-bounce {
      0%, 80%, 100% { transform: translateY(0); }
      40% { transform: translateY(-6px); }
    }

    .ch-bubble {
      position: fixed;
      bottom: 24px;
      ${isLeft ? 'left: 24px;' : 'right: 24px;'}
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: linear-gradient(135deg, #38bdf8, #818cf8);
      box-shadow: 0 4px 20px rgba(56, 189, 248, 0.4);
      cursor: pointer;
      z-index: 99999;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
      animation: ch-pulse 1.5s ease-in-out 3;
      user-select: none;
      border: none;
      outline: none;
      -webkit-tap-highlight-color: transparent;
    }

    .ch-bubble:hover {
      transform: scale(1.1);
      box-shadow: 0 6px 30px rgba(56, 189, 248, 0.6);
    }

    .ch-bubble-c {
      color: white;
      font-size: 20px;
      font-weight: 700;
      line-height: 1;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    .ch-bubble-ai {
      color: white;
      font-size: 12px;
      font-weight: 700;
      line-height: 1;
      letter-spacing: 2px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    .ch-panel {
      position: fixed;
      bottom: 100px;
      ${isLeft ? 'left: 24px;' : 'right: 24px;'}
      width: 400px;
      height: 600px;
      max-height: 80vh;
      border-radius: 16px;
      background: #0f172a;
      border: 1px solid #334155;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
      z-index: 99999;
      display: none;
      flex-direction: column;
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    .ch-panel.ch-open {
      display: flex;
      animation: ch-slide-up 0.25s ease-out;
    }

    .ch-header {
      background: #0f172a;
      height: 56px;
      min-height: 56px;
      display: flex;
      align-items: center;
      padding: 0 16px;
      border-bottom: 1px solid #334155;
    }

    .ch-header-logo {
      height: 28px;
      width: auto;
      margin-right: 10px;
      border-radius: 4px;
    }

    .ch-header-title {
      flex: 1;
      color: #e2e8f0;
      font-size: 15px;
      font-weight: 600;
    }

    .ch-close-btn {
      background: none;
      border: none;
      color: #94a3b8;
      font-size: 22px;
      cursor: pointer;
      padding: 4px 8px;
      border-radius: 6px;
      line-height: 1;
      transition: color 0.15s, background 0.15s;
    }

    .ch-close-btn:hover {
      color: #e2e8f0;
      background: #1e293b;
    }

    .ch-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      background: #1e293b;
    }

    .ch-messages::-webkit-scrollbar {
      width: 6px;
    }

    .ch-messages::-webkit-scrollbar-track {
      background: transparent;
    }

    .ch-messages::-webkit-scrollbar-thumb {
      background: #475569;
      border-radius: 3px;
    }

    .ch-msg {
      max-width: 85%;
      padding: 10px 14px;
      border-radius: 12px;
      font-size: 14px;
      line-height: 1.5;
      word-wrap: break-word;
      overflow-wrap: break-word;
    }

    .ch-msg a {
      color: #93c5fd;
      text-decoration: underline;
    }

    .ch-msg strong, .ch-msg b {
      font-weight: 600;
    }

    .ch-msg-user {
      align-self: flex-end;
      background: ${accentColor};
      color: white;
      border-bottom-right-radius: 4px;
    }

    .ch-msg-ai {
      align-self: flex-start;
      background: #0f172a;
      color: #e2e8f0;
      border-bottom-left-radius: 4px;
    }

    .ch-typing {
      align-self: flex-start;
      display: flex;
      gap: 4px;
      padding: 12px 16px;
      background: #0f172a;
      border-radius: 12px;
      border-bottom-left-radius: 4px;
    }

    .ch-typing-dot {
      width: 7px;
      height: 7px;
      background: #64748b;
      border-radius: 50%;
      animation: ch-bounce 1.4s infinite;
    }

    .ch-typing-dot:nth-child(2) { animation-delay: 0.2s; }
    .ch-typing-dot:nth-child(3) { animation-delay: 0.4s; }

    .ch-input-area {
      display: flex;
      gap: 8px;
      padding: 12px;
      border-top: 1px solid #334155;
      background: #0f172a;
    }

    .ch-input {
      flex: 1;
      background: #1e293b;
      border: 1px solid #475569;
      border-radius: 8px;
      padding: 10px 12px;
      color: #e2e8f0;
      font-size: 14px;
      outline: none;
      font-family: inherit;
      resize: none;
    }

    .ch-input::placeholder {
      color: #64748b;
    }

    .ch-input:focus {
      border-color: ${accentColor};
    }

    .ch-send-btn {
      background: ${accentColor};
      color: white;
      border: none;
      border-radius: 8px;
      padding: 10px 16px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s;
      font-family: inherit;
      white-space: nowrap;
    }

    .ch-send-btn:hover {
      filter: brightness(1.1);
    }

    .ch-send-btn:disabled {
      background: #475569;
      cursor: not-allowed;
    }

    .ch-mic-btn {
      background: transparent;
      color: #94a3b8;
      border: 1px solid #475569;
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 16px;
      cursor: pointer;
      transition: all 0.2s;
      font-family: inherit;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .ch-mic-btn:hover {
      color: #e2e8f0;
      border-color: #64748b;
    }

    .ch-mic-btn.ch-recording {
      color: #ef4444;
      border-color: #ef4444;
      animation: ch-mic-pulse 1s infinite;
    }

    @keyframes ch-mic-pulse {
      0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
      50% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
    }

    .ch-voice-status {
      font-size: 11px;
      color: #94a3b8;
      text-align: center;
      padding: 4px 8px;
      display: none;
    }

    .ch-voice-status.ch-visible {
      display: block;
    }

    .ch-powered {
      text-align: center;
      padding: 6px;
      font-size: 11px;
      color: #475569;
      background: #0f172a;
    }

    .ch-powered a {
      color: #64748b;
      text-decoration: none;
    }

    .ch-powered a:hover {
      color: #94a3b8;
    }

    @media (max-width: 768px) {
      .ch-panel {
        width: calc(100vw - 16px);
        height: calc(100vh - 120px);
        max-height: calc(100vh - 120px);
        ${isLeft ? 'left: 8px;' : 'right: 8px;'}
        bottom: 96px;
        border-radius: 12px;
      }
    }
  `;
  shadow.appendChild(style);

  // Create bubble
  const bubble = document.createElement('button');
  bubble.className = 'ch-bubble';
  bubble.setAttribute('aria-label', 'Open CertiHomes AI Assistant');
  bubble.innerHTML = '<span class="ch-bubble-c">C</span><span class="ch-bubble-ai">AI</span>';
  shadow.appendChild(bubble);

  // Create panel
  const panel = document.createElement('div');
  panel.className = 'ch-panel';
  panel.innerHTML = `
    <div class="ch-header">
      <img class="ch-header-logo" src="${LOGO_URL}" alt="CertiHomes" onerror="this.style.display='none'"/>
      <span class="ch-header-title">AI Assistant</span>
      <button class="ch-close-btn" aria-label="Close chat">&times;</button>
    </div>
    <div class="ch-messages" id="chMessages">
      <div class="ch-msg ch-msg-ai">Hi! I'm the CertiHomes AI assistant. How can I help you today?</div>
    </div>
    <div class="ch-voice-status" id="chVoiceStatus"></div>
    <div class="ch-input-area">
      <button class="ch-mic-btn" aria-label="Voice input" title="Hold to talk">🎙</button>
      <input class="ch-input" type="text" placeholder="Type or hold 🎙 to talk..." autocomplete="off"/>
      <button class="ch-send-btn">Send</button>
    </div>
    <div class="ch-powered"><a href="https://certihomes.com" target="_blank" rel="noopener">Powered by CertiHomes</a></div>
  `;
  shadow.appendChild(panel);

  // Element refs
  const closeBtn = panel.querySelector('.ch-close-btn');
  const messagesEl = panel.querySelector('.ch-messages');
  const inputEl = panel.querySelector('.ch-input');
  const sendBtn = panel.querySelector('.ch-send-btn');
  const micBtn = panel.querySelector('.ch-mic-btn');
  const voiceStatus = panel.querySelector('#chVoiceStatus');

  let isOpen = false;
  let isSending = false;

  // --- Voice (STT via browser SpeechRecognition + TTS via browser speechSynthesis) ---
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let isRecording = false;

  function setVoiceStatus(text) {
    voiceStatus.textContent = text;
    voiceStatus.classList.toggle('ch-visible', !!text);
  }

  function speakReply(text) {
    if (!window.speechSynthesis) return;
    // Cancel any ongoing speech
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;
    // Prefer a natural female voice
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(v =>
      v.name.includes('Samantha') || v.name.includes('Google US English') ||
      v.name.includes('Microsoft Zira') || v.name.includes('Karen')
    ) || voices.find(v => v.lang.startsWith('en') && v.name.includes('Female'))
      || voices[0];
    if (preferred) utterance.voice = preferred;
    window.speechSynthesis.speak(utterance);
  }

  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = function() {
      isRecording = true;
      micBtn.classList.add('ch-recording');
      setVoiceStatus('🎙 Listening...');
    };

    recognition.onresult = function(event) {
      let transcript = '';
      for (let i = 0; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      inputEl.value = transcript;
      if (event.results[0] && event.results[0].isFinal) {
        setVoiceStatus('');
      } else {
        setVoiceStatus('🎙 ' + transcript);
      }
    };

    recognition.onend = function() {
      isRecording = false;
      micBtn.classList.remove('ch-recording');
      setVoiceStatus('');
      // Auto-send if we got text
      const text = inputEl.value.trim();
      if (text) {
        sendMessageVoice(text);
      }
    };

    recognition.onerror = function(event) {
      isRecording = false;
      micBtn.classList.remove('ch-recording');
      if (event.error === 'not-allowed') {
        setVoiceStatus('⚠ Microphone access denied');
      } else if (event.error !== 'aborted') {
        setVoiceStatus('⚠ ' + event.error);
      }
      setTimeout(() => setVoiceStatus(''), 3000);
    };

    micBtn.addEventListener('click', function() {
      if (isRecording) {
        recognition.stop();
      } else {
        // Stop any ongoing speech
        if (window.speechSynthesis) window.speechSynthesis.cancel();
        recognition.start();
      }
    });
  } else {
    // No speech recognition support — hide mic button
    micBtn.style.display = 'none';
  }

  async function sendMessageVoice(text) {
    // Same as sendMessage but also speaks the reply
    if (!text || isSending) return;
    isSending = true;
    sendBtn.disabled = true;
    inputEl.value = '';
    addMessage(text, 'user');
    showTyping();

    try {
      const resp = await fetch(API_URL + '/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, conversation_id: conversationId })
      });
      const data = await resp.json();
      hideTyping();
      const reply = data.reply || 'Sorry, I could not generate a response.';
      addMessage(reply, 'ai');
      // Speak the reply aloud
      speakReply(reply);
    } catch (err) {
      hideTyping();
      addMessage('Sorry, something went wrong. Please try again.', 'ai');
    } finally {
      isSending = false;
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  // Toggle panel
  function togglePanel() {
    isOpen = !isOpen;
    if (isOpen) {
      panel.classList.add('ch-open');
      bubble.style.display = 'none';
      inputEl.focus();
    } else {
      panel.classList.remove('ch-open');
      bubble.style.display = 'flex';
    }
  }

  bubble.addEventListener('click', togglePanel);
  closeBtn.addEventListener('click', togglePanel);

  // Format basic markdown
  function formatMessage(text) {
    if (!text) return '';
    let html = text
      // Escape HTML
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      // Bold: **text** or __text__
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/__(.+?)__/g, '<strong>$1</strong>')
      // Italic: *text* or _text_
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/_(.+?)_/g, '<em>$1</em>')
      // Links: [text](url)
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      // Plain URLs
      .replace(/(https?:\/\/[^\s<]+)/g, function(match) {
        // Don't double-wrap URLs already in <a> tags
        return '<a href="' + match + '" target="_blank" rel="noopener">' + match + '</a>';
      })
      // Line breaks
      .replace(/\n/g, '<br>');
    return html;
  }

  // Fix double-linked URLs: the plain URL regex can wrap URLs that are already inside href=""
  // We handle this by running plain URL replacement only on text not already in a tag
  function formatMessageSafe(text) {
    if (!text) return '';
    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/__(.+?)__/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      .replace(/\n/g, '<br>');
    return html;
  }

  function addMessage(text, type) {
    const div = document.createElement('div');
    div.className = 'ch-msg ' + (type === 'user' ? 'ch-msg-user' : 'ch-msg-ai');
    if (type === 'user') {
      div.textContent = text;
    } else {
      div.innerHTML = formatMessageSafe(text);
    }
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function showTyping() {
    const div = document.createElement('div');
    div.className = 'ch-typing';
    div.id = 'ch-typing-indicator';
    div.innerHTML = '<div class="ch-typing-dot"></div><div class="ch-typing-dot"></div><div class="ch-typing-dot"></div>';
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function hideTyping() {
    const el = messagesEl.querySelector('#ch-typing-indicator');
    if (el) el.remove();
  }

  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text || isSending) return;

    isSending = true;
    sendBtn.disabled = true;
    inputEl.value = '';
    addMessage(text, 'user');
    showTyping();

    try {
      const resp = await fetch(API_URL + '/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId
        })
      });
      const data = await resp.json();
      hideTyping();
      addMessage(data.reply || 'Sorry, I could not generate a response.', 'ai');
    } catch (err) {
      hideTyping();
      addMessage('Sorry, something went wrong. Please try again.', 'ai');
      console.error('[CertiHomes Widget]', err);
    } finally {
      isSending = false;
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  sendBtn.addEventListener('click', sendMessage);
  inputEl.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

})();
