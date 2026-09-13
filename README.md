# NOVA — Futuristic AI Voice Assistant for Windows

> A personal AI command center inspired by JARVIS, with its own original identity.

NOVA is a futuristic female AI voice assistant for Windows built around a
premium dark UI, a central animated orb, and a fully provider-swappable voice
pipeline. This is **Phase 1: UI + Voice Foundation**.

---

## 1. Project Overview

NOVA is a desktop application written in Python + PyQt6. It provides:

- A **futuristic dark command-center UI** with a central animated orb and
  state-reactive waveform.
- A **voice pipeline** (microphone → speech recognition → brain → response
  text → text-to-speech → speaker) that runs entirely in background threads
  so the UI never freezes.
- **Multilingual awareness** — English, Hindi and Hinglish commands are
  recognized and answered without translating the user's own words.
- A **modular brain** with replaceable speech-recognition and TTS providers,
  ready for real automation and, later, LLM integration.

## 2. NOVA Vision

NOVA's end goal is to feel like a companion AI — not a chatbot glued to a
dashboard. It will eventually:

- Understand natural, mixed-language voice commands ("NOVA, Chrome kholo aur
  YouTube open karo").
- Automate Windows (apps, files, settings), browsers, and multi-step tasks.
- See the screen and act on it.
- Remember context and adapt to the user.
- Respond in natural, expressive speech.

Every architectural decision in this codebase is made with that end state in
mind.

## 3. Current Capabilities (Phase 1)

- Live microphone capture with ambient-noise calibration.
- Voice → text via **Google Speech Recognition** (default) or **local Whisper**.
- Text → voice via **Microsoft Edge TTS** (default) or **offline pyttsx3**.
- Command processing in English, Hindi (Devanagari), and Hinglish.
- Wake-word architecture (configurable, mock-capable).
- Simulated automation — NOVA clearly labels actions as *[SIMULATED]* rather
  than pretending they happened.
- Non-blocking UI: orb/waveform animate through IDLE → LISTENING → PROCESSING
  → SPEAKING → EXECUTING → ERROR.

### Supported commands

| Example command | Response |
|---|---|
| "Hello NOVA" | Greeting based on time of day |
| "What can you do?" / "Kya kar sakti ho?" | Capability summary |
| "Open Chrome" / "Chrome kholo" / "क्रोम खोलो" | *[SIMULATED]* Open Chrome |
| "Open Notepad" / "Notepad kholo" / "नोटपैड खोलो" | *[SIMULATED]* Open Notepad |
| "Open YouTube" / "YouTube open karo" / "यूट्यूब खोलो" | *[SIMULATED]* Open YouTube |
| "Open Calculator" / "Calculator kholo" / "कैलकुलेटर खोलो" | *[SIMULATED]* Open Calculator |
| "Tell me the time" / "वक्त बताओ" / "Kitne baje" | Current time |
| "What's the date" / "आज की तारीख" | Current date |
| "Who are you?" / "तुम कौन हो?" | NOVA identity |
| "Thank you" / "शुक्रिया" | Courtesy response |
| "Bye" / "बंद करो" | Goodbye + close |

Unknown commands receive a graceful "I'm not sure how to help with that yet"
response, including an echo of exactly what was heard.

## 4. Current Limitations

- **Automation is simulated**, not real (Phase 2).
- No push-to-talk or echo cancellation; while NOVA speaks, an active mic may
  re-capture her voice. Default config is click-to-listen.
- **Wake word detection is a configurable mock** — in `WAKE_WORD_ENABLED=false`
  mode every utterance is treated as a command; the "NOVA" phrase still gets the
  "Yes?" greeting. A real wake-word engine (e.g. Porcupine) is planned.
- Google STT/TTS and Edge TTS require an internet connection.
- Single-shot commands only; no multi-step task chaining yet.
- Hindi recognition quality depends on the active STT provider.

## 5. Tech Stack

| Layer | Technology | Why |
|---|---|---|
| UI | PyQt6 + custom `QPainter` drawing | Rich custom animations, native Windows feel |
| Animation | Custom widget timers (60fps orb, 30fps waveform) | No extra animation framework needed |
| Mic capture | `SpeechRecognition` + `PyAudio` | Well-tested, provider-based |
| Speech → text | Google Web Speech (default) / local Whisper | Swappable via `STT_PROVIDER` |
| Text → speech | Edge TTS (default) / pyttsx3 fallback | High-quality neural voice; offline fallback |
| Audio playback | `pygame.mixer` | Simple, reliable streaming of TTS buffers |
| Config | `python-dotenv` | Keys/config live outside source code |
| Logging | stdlib `logging` | Structured console + UTF-8 file logs |

## 6. Project Structure

```
NOVA/
├── main.py                    # Entry point — launches the Qt event loop
├── config.py                  # Dataclass-based configuration from .env
├── requirements.txt
├── .env.example               # Copy to .env and adjust
│
├── ui/
│   ├── __init__.py
│   ├── main_window.py         # The command center + state wiring
│   ├── nova_orb.py            # Animated central orb (state-reactive)
│   ├── waveform.py            # Audio-reactive waveform bars
│   └── styles/
│       └── theme.py           # Fallback QSS stylesheet
│
├── voice/
│   ├── __init__.py
│   ├── listener.py            # Microphone loop in a background thread
│   ├── speech_to_text.py      # STT providers (Google / Whisper)
│   └── text_to_speech.py      # TTS providers (Edge TTS / pyttsx3)
│
├── brain/
│   ├── __init__.py
│   └── agent.py               # Command interpretation + response generation
│
├── automation/
│   └── __init__.py            # Phase 2: real Windows automation lives here
│
└── utils/
    ├── __init__.py
    └── logger.py              # Unicode-safe logging (console + file)
```

## 7. Installation

Requirements: **Windows 10/11**, **Python 3.10+**.

```bash
cd NOVA

# (Recommended) create a virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
python -m pip install -r requirements.txt
```

`pyaudio` ships prebuilt wheels for Windows on Python 3.10+, so no extra
compiler setup is required.

## 8. Environment-Variable Setup

```bash
copy .env.example .env
```

Then edit `.env`:

| Variable | Options | Default | Notes |
|---|---|---|---|
| `STT_PROVIDER` | `google` / `whisper` | `google` | `whisper` requires the `whisper` package + `openai` |
| `WHISPER_MODEL` | `tiny`/`base`/`small`/`medium`/`large` | `base` | Only used when STT is `whisper` |
| `TTS_PROVIDER` | `edge-tts` / `pyttsx3` | `edge-tts` | Edge TTS needs internet |
| `TTS_VOICE` | e.g. `en-US-AvaNeural`, `en-US-JennyNeural`, `hi-IN-SwaraNeural` | `en-US-AvaNeural` | Female neural voices recommended |
| `RECOGNITION_LANGUAGE` | `en-US` / `hi-IN` / `auto` | `auto` | `auto` → English first |
| `WAKE_WORD_ENABLED` | `true` / `false` | `false` | False = instant command mode ("press & speak") |
| `WAKE_WORD` | any word | `nova` | Wake phrase |
| `DEBUG` | `true` / `false` | `false` | Verbose logging |

Never commit `.env`.

## 9. How to Run NOVA

```bash
.venv\Scripts\activate
python main.py
```

When the window opens:

1. Click the **🎤 MICROPHONE** button to start the voice listener
   (the orb turns green = listening).
2. Speak a command — e.g. *"Open Chrome"* or *"Notepad kholo"*.
3. Watch NOVA move through **LISTENING → PROCESSING → SPEAKING ∈ EXECUTING**
   as it answers.
4. No microphone? Use **⌨ TYPE COMMAND** to type commands and hear them
   spoken back.

Alternatively `--help`: NOVA currently starts with the GUI by default.

## 10. Voice Configuration

NOVA decouples providers through two thin factories:

- `voice/speech_to_text.py::create_stt_provider()` → returns an `STTProvider`.
- `voice/text_to_speech.py::create_tts_provider()` → returns a `TTSProvider`.

To add a provider, implement the abstract base class and register it in the
factory. The UI, brain, and listener never import a specific provider.

### Choosing a TTS voice
List available Edge TTS voices:

```bash
python -c "import edge_tts, asyncio; \
print(asyncio.run(edge_tts.list_voices()))"
```

Recommended female voices: `en-US-AvaNeural`, `en-US-JennyNeural`,
`hi-IN-SwaraNeural`.

## 11. Supported Languages

- **English** — "Open Chrome"
- **Hindi (Devanagari)** — "क्रोम खोलो"
- **Hinglish** — "Chrome kholo"
- **Mixed** — "NOVA, Chrome kholo aur YouTube open karo" (NOVA preserves the
  original phrasing; per-phrase translation is a future-phase refinement)

The brain matches on language-agnostic *intent* patterns rather than
translating user speech, so the original command is always preserved verbatim
in history and in NOVA's "I heard you say…" feedback.

## 12. UI States

The orb and waveform re-style for each state:

| State | Orb behavior | Waveform | Color |
|---|---|---|---|
| **IDLE** | Gentle breathing pulse | Slow drifting bars | Cyan |
| **LISTENING** | Stronger pulse, audio-reactive | Spike with mic level | Green |
| **PROCESSING** | Fast rotation + particle swarm | Pulsing waves | Purple |
| **SPEAKING** | Rhythmic pulse | Simulated voice bars | Pink |
| **EXECUTING** | Constant energized glow | Sustained waves | Amber |
| **ERROR** | Sputtering, low pulse | Jitter | Red |

Layout highlights: brand titlebar with minimize/close, system status panel
(CORE / LANG / STT / TTS / WAKE / MIC), command feed, live command + response
labels, connection indicator, and settings button.

## 13. Architecture Overview

```
Mic ──► listener.py ──► speech_to_text.py ──► brain/agent.py ──► TTS ──► Speaker
         (thread)          (provider)            (commands)       (thread)
            │                  │                     │               │
            └────────► VoiceBridge ◄─────────────────┘               │
                         (Qt signals)                                 │
                              │                                      │
                         main_window.py (UI thread) ◄────────────────┘
```

Key decisions:

- **Workers never touch the UI.** All cross-thread updates flow through
  `VoiceBridge` (a `QObject` emitting signals), which Qt safely queues to the
  main thread. This is what guarantees the UI never freezes.
- **Providers are replaceable.** STT and TTS are abstract-base + factory
  patterns; the brain and UI depend only on the interface.
- **State is explicit.** A single `set_state()` drives the orb, waveform,
  status bar, and system panel — one source of truth.
- **No secrets in code.** Everything configurable lives in `.env`.

## 14. Roadmap

| Phase | Scope |
|---|---|
| **Phase 1 — UI + Voice Foundation** ✅ | This release: premium UI, voice pipeline, multilingual intents, simulated actions, wake-word architecture |
| **Phase 2 — Windows Automation** | Real app launching, window control, settings, file ops, clipboard (in `automation/`) |
| **Phase 3 — Browser Automation** | Open/search/navigate pages; drive Chrome/Edge programmatically |
| **Phase 4 — Screen Vision** | Screenshot + OCR/vision models for "what's on my screen?" |
| **Phase 5 — Multi-step Agent** | Chaining commands, tool orchestration, confirmation flows |
| **Phase 6 — Memory** | Persistent user profile, conversation recall, learned preferences |
| **Phase 7 — Advanced NOVA** | Real wake word (Porcupine), streaming responses, offline models, custom skills/plugins |

## 15. Future Automation Capabilities

`automation/` is intentionally empty for Phase 1. Phase 2 will add
capability modules such as:

- Launching & focusing applications
- Window management (move, resize, minimize)
- File management (open folders, move/copy files, list directories)
- Setting system state (volume, brightness, wifi toggle)
- Clipboard & text insertion
- A capability registry the brain can query before deciding to act

## 16. Safety Considerations

- Automation actions are **explicitly simulated** in Phase 1 and clearly
  labelled — NOVA never pretends an action happened.
- Future destructive/privileged actions (deleting files, system changes) will
  require spoken/user confirmation before execution.
- All API keys live in `.env` (never committed). Google STT requires no key;
  adding an LLM later requires an `OPENAI_API_KEY` or equivalent in `.env`.
- Voice recording is local-only in this phase; device audio is never uploaded
  except for the selected STT provider's online transcript request.
- Logs exclude secrets; review `logs/` for anything sensitive before sharing.

## 17. Development Instructions

```bash
# Compile-check all modules
python -m py_compile main.py config.py utils\logger.py voice\*.py brain\*.py ui\*.py ui\styles\*.py

# Headless smoke test (no audio)
$env:QT_QPA_PLATFORM = "offscreen"
python -X utf8 -c "from PyQt6.QtWidgets import QApplication; import ui.main_window as m; import sys; app=QApplication(sys.argv); w=m.MainWindow(); w.show(); app.processEvents(); w.close(); print('OK')"
```

Guidelines:

- Keep worker threads off the UI thread; communicate only via `VoiceBridge`.
- Add intent patterns to `brain/agent.py` — patterns are regex + handler maps,
  so new languages/phrases are just new patterns.
- New providers implement the abstract bases in `voice/`.
- All logs go to `logs/nova_YYYYMMDD.log` (UTF-8, debug-level) and the console
  (info-level, Unicode-safe).
- Run `py_compile` after any change before committing.

---

**NOVA** — Phase 1 complete. The foundation is ready for automation, agentic
tasks, vision, and memory.