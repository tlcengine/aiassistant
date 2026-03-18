# Add CertiHomes AI Assistant Widget

## Instructions for Claude Code

Add the CertiHomes AI Assistant chat widget to this website.

### Quick Install (1 line)
Add this script tag before the closing `</body>` tag on every page (or in the main layout/template):

```html
<script src="https://aiassistant.certihomes.com/widget.js"></script>
```

### That's it!
The widget automatically:
- Shows a floating "C AI" chat bubble in the bottom-right corner
- Opens a chat panel when clicked
- Connects to the CertiHomes AI Assistant API
- Uses Shadow DOM so it never conflicts with your site's CSS
- Works on any page with no configuration needed

### Voice Features
The widget includes built-in voice support:
- **Mic button**: A microphone button next to the text input lets users speak instead of type
- **Speech-to-text**: Uses the browser's SpeechRecognition API (Chrome, Edge, Safari) to transcribe voice input
- **Text-to-speech**: AI responses are read aloud using the browser's speechSynthesis API
- **Voice status indicator**: Shows "Listening..." while recording speech
- Preferred TTS voices: Google US English, Microsoft Zira, Karen (falls back to default)
- Hold the mic button to talk, release to send

### Optional: Custom positioning
```html
<script src="https://aiassistant.certihomes.com/widget.js"
  data-position="bottom-left"
  data-color="#38bdf8">
</script>
```

**Supported attributes:**
- `data-position` — `"bottom-right"` (default) or `"bottom-left"`
- `data-color` — Hex color for accent/send button (default `"#3b82f6"`)

### Where to add it:

- **Next.js (App Router)**: In `app/layout.tsx`, add inside the `<body>` tag:
  ```tsx
  import Script from 'next/script';
  // Inside <body>:
  <Script src="https://aiassistant.certihomes.com/widget.js" strategy="afterInteractive" />
  ```

- **Next.js (Pages Router)**: In `pages/_app.tsx`:
  ```tsx
  import Script from 'next/script';
  // Inside the component return:
  <Script src="https://aiassistant.certihomes.com/widget.js" strategy="afterInteractive" />
  ```

- **React (Create React App / Vite)**: Add to `public/index.html` before `</body>`:
  ```html
  <script src="https://aiassistant.certihomes.com/widget.js"></script>
  ```
  Or in your App component:
  ```tsx
  useEffect(() => {
    const script = document.createElement('script');
    script.src = 'https://aiassistant.certihomes.com/widget.js';
    document.body.appendChild(script);
    return () => { document.body.removeChild(script); };
  }, []);
  ```

- **Plain HTML**: Add before `</body>` tag:
  ```html
  <script src="https://aiassistant.certihomes.com/widget.js"></script>
  ```

- **WordPress**: Add to `footer.php` before `</body>`, or use a plugin like "Insert Headers and Footers" to add the script tag to the footer.

- **Nginx**: Not applicable — add the script to the HTML files being served, not the Nginx config.

### Browser Compatibility for Voice Features
- **Chrome/Edge**: Full support (SpeechRecognition + speechSynthesis)
- **Safari**: Full support (webkitSpeechRecognition + speechSynthesis)
- **Firefox**: Text-to-speech only (speechSynthesis supported, SpeechRecognition not supported — mic button hidden)
- If SpeechRecognition is not available, the mic button is automatically hidden and the widget works as text-only chat.
