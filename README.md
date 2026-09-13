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
| `VOICE_PROVIDER` | `edge-tts` / `windows-sapi` / `none` | `edge-tts` | Uses `TTS_PROVIDER` when unset |
| `VOICE_NAME` | e.g. `en-IN-NeerjaNeural` | `en-IN-NeerjaNeural` | Default voice (uses `TTS_VOICE` when unset). Indian settings see §21 |
| `VOICE_LANGUAGE` | `AUTO` / `ENGLISH` / `HINDI` / `HINGLISH` | `AUTO` | Reply + TTS language bias |
| `VOICE_AUTO_LANGUAGE` | `true` / `false` | `true` | Follow the user's language in AUTO mode |
| `VOICE_ENABLED` | `true` / `false` | `true` | Master voice switch |
| `VOICE_VOLUME` | `0`–`100` | `100` | Speech volume |
| `VOICE_SPEED` | `-50`…`+50` | `0` | Speaking-rate shift |
| `VOICE_SAPI_NAME` | (SAPI name) | empty | Preferred Windows SAPI voice |
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
   (NOVA's eyes light up green = listening).
2. Speak a command — e.g. *"Open Chrome"* or *"Notepad kholo"*.
3. Watch NOVA move through **LISTENING → PROCESSING → SPEAKING ∈ EXECUTING**
   as it answers.
4. No microphone? Use **⌨ TYPE COMMAND** to type commands and hear them
   spoken back.

Alternatively `--help`: NOVA currently starts with the GUI by default.

## 10. Voice Configuration

NOVA decouples providers through two thin factories:

- `voice/speech_to_text.py::create_stt_provider()` → returns an `STTProvider`.
- `voice/text_to_speech.py::create_tts_provider()` → returns a `TTSProvider` (legacy).

For spoken output NOVA now uses the **VoiceController**
(`voice/controller.py`): a runtime singleton that applies volume/speed/language
mode, auto-detects the user's language, and dispatches to a swappable
`VoiceProvider` (`voice/providers/`). The default provider is **edge-tts**
with Indian female neural voices — `en-IN-NeerjaNeural` (Indian English) and
`hi-IN-SwaraNeural` (Hindi / Hinglish) — see §21.2. The original factory and
`TTSProvider` class remain available and fully functional.

To add a provider, implement the abstract base class and register it in the
factory. The UI, brain, and listener never import a specific provider.
Voice settings are editable live in **SETTINGS ⚙** and persist to `.env`.

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

The character, stage FX, and waveform re-style for each state (see §21 for the
character & avatar system):

| State | Character | Stage FX | Color |
|---|---|---|---|
| **IDLE** | Soft blink, gentle head sway | Breathing halo rings | Cyan |
| **LISTENING** | Alert eyes, gaze track, mic-LED pulse | Audio-reactive rings | Green |
| **PROCESSING** | Eyes up-right, one brow raised, "o" mouth | Halo arcs + "…" dots | Purple |
| **SPEAKING** | Mouth lip-syncs to the voice | Glow pulses with speech | Rose |
| **EXECUTING** | Determined eyes, focus glints | Progress arc around head | Amber |
| **SUCCESS** | Grin, sparkle burst | Radiant particle burst | Emerald |
| **ERROR** | Worried brows, frown | Glitch bars | Red |

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
| **Phase 1 — UI + Voice Foundation** ✅ | This release: **Aurora Core** premium UI (Visual v2), voice pipeline, multilingual intents, simulated actions, wake-word architecture |
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

## 18. Aurora Core UI — Visual v2 (Phase 1 Upgrade)

The Phase-1 UI was rebuilt into a premium, futuristic deep-space command center.
The voice architecture (bridge, threads, providers, brain) is untouched; the
upgrade is a visual layer that reads the same states through a shared clock.

### Design identity

- **Name:** *Aurora Core* — a glass control deck around a living energy core.
- **Scene:** deep navy-to-black vertical gradient with drifting aurora glows and
  a twinkling star field (the `AmbientBackground` behind everything).
- **Core:** the NOVA orb — a conical-gradient energy sphere with a rotating halo
  ring, orbiting particles, task-progress arc, and text-in-orb label.
- **Surround:** three concentric energy rings (`EnergyRings`) with a dashed
  outer ring, segmented breathing arcs, glow tips, and orbit dots.
- **Live input:** a mirrored spectrum waveform that reacts to mic energy, speech
  envelope, and idle drift.
- **Surfaces:** frosted-glass side panels (`GlassPanel`), success/fail flash
  chips, and progress-driven flashes for simulated actions.

### Visual components

| File | Widget | Role |
|---|---|---|
| `ui/ambient.py` | `AmbientBackground` | Full-window atmosphere: cached gradient + 3 aurora glows + 90 twinkling stars (single 35 ms coarse timer) |
| `ui/ring_field.py` | `EnergyRings` | Concentric rings, breathing segmented arcs, orbit dots |
| `ui/nova_orb.py` | `NovaOrb` | Core orb: conical glow, halo, particles, progress arc, text label |
| `ui/waveform.py` | `WaveformWidget` | Mirrored spectrum, audio / speech / idle modes |
| `ui/glass.py` | `GlassPanel` | Frosted panel + section titles + status rows + flash chips |
| `ui/settings_dialog.py` | `SettingsDialog` | Glass config dialog (STT/TTS/wake/language/docs) |
| `ui/theming.py` | palettes | `PALETTE`, `STATE_DEFS`, `STATE_COLORS`, lerp helpers |
| `ui/state_engine.py` | `NovaStateAnimator` | Single 30 ms clock driving every visual |

### State visuals (Visual v2 palette)

| State | Core color | Accent | Visual |
|---|---|---|---|
| **IDLE** | Teal | Sky | Gentle pulse, drifting rings, slow waveform drift |
| **LISTENING** | Emerald | Mint | Stronger pulse, waveform reacts to real mic energy |
| **PROCESSING** | Violet | Lavender | Fast core rotation, particle swarm, pulsing rings |
| **SPEAKING** | Rose | Pink | Rhythmic speech envelope on core + waveform |
| **EXECUTING** | Amber | Gold | Sustained energized glow + task progress arc |
| **ERROR** | Red | Crimson | Sputtering core, jitter, red flash chip |

### Animation architecture

- **One clock, many readers.** `NovaStateAnimator` owns a single 30 ms
  `PreciseTimer`. Each frame it advances shared floats (rotation, ring angle,
  pulse, audio, speech) and emits `updated`; orb / rings / waveform / status
  update only when that fires.
- **Frame-rate independent.** Transitions use exponential damping
  (`1 - e^(-dt·k)`), so motion smoothness depends on the clock, not the
  repaint rate.
- **Simulated voice.** When SPEAKING, a deterministic sine-based envelope drives
  the orb and waveform in place of real audio.
- **Task progress.** EXECUTING exposes a `.progress` value (0→1); the orb draws
  a progress arc and the shape sustains an energized glow.

### Performance notes

- Base background gradient and the orb's inner artwork are cached to `QPixmap`
  on resize, never rebuilt per frame.
- The scene runs two timers (animator 30 ms, ambient 35 ms); widgets repaint
  only on `updated`, and glow-heavy paint paths are kept cheap.
- Cross-thread rules are unchanged: workers only emit `VoiceBridge` signals;
  no worker ever touches a widget. New signals added: `task_progress` and
  `latency_updated`.

### Platform note (Windows + offscreen)

The raster path on the `offscreen` QPA platform crashed for
`drawEllipse(x, y, w, h)` float-rect calls with gradient brushes. All ellipse
drawing therefore uses the `QPointF(center), rx, ry` overload, which is
reliable on both `offscreen` and `windows`. Keep new drawing code on this form.

## 19. Voice ✕ UI Data Flow (v2)

```
listener (thread) ──► bridge.text_captured ──► main_window ──► brain (worker)
                                                      │              │
   mic level ──► bridge.audio_level ──► animator.set_audio_level()      │
                                                      │              │
speech_processing ──► animator.set_state(PROCESSING)  │◄── response_ready
   task dispatch  ──► bridge.task_progress ──► animator.set_progress()
   TTS speak      ──► bridge.state_changed(SPEAKING) ◄── animator text
                                                      │
                          bridge.latency_updated ──► sys_latency label
```

Wake-word architecture, provider factories, and the multilingual brain are
described in §11–§13 and are unchanged by the visual upgrade.

---

## 20. Windows Automation (Phase 2)

NOVA can now act on the system through a **secure, white-listed tool layer**.
The voice/UI brain you already know now understands natural-language commands
(English, Hindi, Hinglish, and Devanagari) and turns them into **typed, verified
tool calls** — NOVA never builds or runs an arbitrary shell command.

### 20.1 Architecture: brain → intent → plan → tool → verify → reply

```
     user speaks ──► speech_to_text ──► brain/NovaAgent
                                          │  classify (risk: SAFE / CONFIRMATION_REQUIRED / HIGH_RISK)
                                          │  map intent → ActionPlan[ActionStep...]   (params extracted, typed)
                                          ▼
                              AutomationEngine.execute_plan(plan, approved=?)
                                          │  risk gate (blockHIGH_RISK unless explicit allow; block
                                          │  CONFIRMATION_REQUIRED unless the user says yes first)
                                          ▼
                             controlled tool fn (audited, fixed subprocess/py API calls)
                                          │  verification (tasklist, path checks, volume readback)
                                          ▼
                  ToolResult(ok, verified, message) ──► honest reply ("Done" only when verified)
                                          │
                                          └─► UI flash ✓/⚠ via brain.last_action_ok
```

The flow is the one you asked for: **brain → intent → action planner → tool
selection → tool execution → verification → response**.

### 20.2 Tool catalogue and their risk

All tools live in `automation/tools/`. Each is a plain function taking typed
parameters; none of them invokes `shell=True`.

| Tool | Risk | What it does |
|---|---|---|
| `open_application` | SAFE | Opens an app by name/alias; verifies a process appeared |
| `close_application` | SAFE | Closes an app (graceful `taskkill`, no `/F` unless verified needed); verifies it exited |
| `open_url` | SAFE | Opens a URL in the default browser (`ShellExecuteW`) |
| `open_folder` | SAFE | Opens Explorer at a location (supports Windows CLSIDs, e.g. "This PC") |
| `create_folder` / `create_file` | SAFE | Creates a folder / text file |
| `move_file` / `copy_file` / `rename_file` | SAFE | File operations into a resolved destination |
| `search_files` | SAFE | Shallow-scanned filename search under a root |
| `take_screenshot` | SAFE | Saves a PNG to `Pictures\NOVA Screenshots` (or `SCREENSHOT_DIR`) |
| `type_text` | SAFE | Types text (Unicode-safe; falls back to clipboard+Ctrl+V) |
| `press_key` | SAFE | Sends a key chord, e.g. Ctrl+N |
| `mouse_click` | SAFE | Clicks (optionally at x,y; double-click supported) |
| `volume_control` | SAFE | Set/up/down/mute volume; reads level back to confirm |
| `install_software` | CONFIRMATION_REQUIRED | Installs via `winget` — always asks first |
| `delete_file` | CONFIRMATION_REQUIRED | Deletes a file/folder — always asks first |

Tools NOT in this list cannot be called by the brain — an unknown tool is never
dispatched.

### 20.3 Permission model

- **SAFE** tools run immediately after intent mapping.
- **CONFIRMATION_REQUIRED** tools (delete, install) are *staged*: NOVA replies
  "This will delete X — say yes to confirm, or say cancel." Nothing runs until
  the user confirms with "yes / haan / हाँ / confirm / theek hai…".
- **HIGH_RISK** actions never run silently. They are refused up-front with an
  explanation. A HIGH_RISK step also blocks the whole plan (no partial runs).
- `AUTOMATION_AUTO_CONFIRM=true` skips the spoken confirmation prompt for
  CONFIRMATION_REQUIRED tools only (never silent high-risk).
- `AUTOMATION_ALLOW_HIGH_RISK=true` permits HIGH_RISK steps *only when they also
  pass the user's explicit confirmation*. This flips a safety switch — keep it
  off unless you know what you are doing.

### 20.4 Safety model

- **Protected roots** (`C:\Windows`, `Program Files`, `Program Files (x86)`,
  `ProgramData`, `$Recycle.Bin`, `System Volume Information`) automatically
  escalate any file operation to HIGH_RISK — the plan is refused.
- High-risk **phrases** ("format the disk", "disable firewall", "wipe the
  drive", "change partition", "delete system files", registry/policy edits) are
  refused before any tool selection happens — `automation/safety.py`.
- Every action is **verified after the fact**: the process is running/stopped,
  the path exists/gone, the volume level matches — only then does NOVA say
  "Done". Otherwise NOVA says *"I couldn't complete that because …"*.
- No unrestricted shell: parameters are never interpolated into a shell
  command string.

### 20.5 Supported commands (examples)

```
Open Chrome                      Chrome kholo              क्रोम खोलो
Open YouTube                     Open VS Code and create a new file
Open Downloads / Open This PC    Close Notepad              नोटपैड बंद करो
Desktop pe ek folder banao naam Projects
Downloads mein Python folder banao
Volume 50 percent karo           Volume thoda kam karo
Take a screenshot                Type hello               Press Ctrl+N
find my resume in Downloads      Copy notes.txt to backup
create file expenses.txt in Desktop
delete file hello.txt            (asks confirmation)
install software Notepad++       (asks confirmation)
What time is it? / Kitne baje? / समय क्या हुआ?
Who are you? / Tumhara naam kya hai?
what can you do
bye / quit                       (closes NOVA; "close" alone no longer quits)
```

### 20.6 New dependencies

Added to `requirements.txt` (UI and voice deps are unchanged):

- `Pillow` — screenshot capture (`automation/tools/screen.py`)
- `pyautogui` — keyboard/mouse synthesis (`automation/tools/input_tools.py`)
- `pycaw>=2024` (+ `comtypes`) — volume control and readback
  (`automation/tools/systools.py`)

`winget` (built into Windows 10/11) powers `install_software`.

### 20.7 Configuration (`.env` / `.env.example`)

| Variable | Default | Meaning |
|---|---|---|
| `AUTOMATION_AUTO_CONFIRM` | `false` | Auto-approve CONFIRMATION_REQUIRED tools |
| `AUTOMATION_ALLOW_HIGH_RISK` | `false` | Allow HIGH_RISK steps after explicit confirm |
| `SCREENSHOT_DIR` | *(empty)* → `Pictures\NOVA Screenshots` | Where screenshots are saved |
| `APPS_CONFIG_FILE` | `apps_config.json` | Extra app aliases (JSON keyed by spoken name) |
| `SEARCH_ROOT` | *(empty)* → user home | Default root for `search_files` |

### 20.8 Troubleshooting

- A command is answered with "I couldn't complete that because …" → read the
  reason (missing file, app not found, verification failed). NOVA never claims
  success it didn't verify.
- "That action is too risky" → the intent or a protected path tripped a
  HIGH_RISK gate; NOVA will not override it by default.
- Delete/install paused on "say yes to confirm" → answer yes / haan / cancel.
- Tools silently not working (screenshot, keys, volume) → confirm `Pillow`,
  `pyautogui`, `pycaw` are installed (`pip install -r requirements.txt`).

### 20.9 Roadmap update

- **Phase 1** — Core assistant + voice controls: ✅ done (see §1–§19).
- **Phase 2** — Secure Windows automation with risk-gated, verified tools:
  ✅ shipped (§20).
- **Next** — agentic multi-step planning with memory, vision, and the
  permission surface extended to schedules and system health.

---

## 21. NOVA Character & Voice Identity (Phase 3)

NOVA now has a face and a voice of her own: an **original anime/cartoon AI
girl** rendered live with QPainter, and a **natural Indian female voice** that
follows the user's language.

### 21.1 The character (no copyrights — 100% original)

NOVA is drawn procedurally every frame from the shared animation engine — she
is not a static image and no external character assets are used:

- **Design.** Young-adult AI girl, big anime eyes with iris + highlights,
  futuristic violet hair (fringe + long side locks), a teal sci-fi jacket with
  a glowing collar "core" badge, a headset with a boom mic whose LED pulses,
  and subtle teal stud earrings. Personality: warm, confident, a little
  playful; professionally focused while executing tasks.
- **Animation.** One 30 ms clock (the existing `NovaStateAnimator`) drives
  everything — no per-widget timers:
  - eyelids close/open on a natural blink window;
  - gaze shifts with state (gazing up-right while thinking, tracking the
    user while listening);
  - head tilts and sways, hair locks sway with inertia, shoulders "breathe";
  - eyebrows raise/lower/furrow by state;
  - the mouth lip-syncs to the **speech envelope** while speaking (and blooms
    into a grin on success, a worried frown on error, a small "o" while
    thinking).
- **Stage FX** behind the character: halo arcs, orbiting particles, a
  progress ring while executing, radiating burst on success, glitch bars on
  error — all tinted per state.
- **Files.** `ui/avatar/` — `face.py` (`AnimeFace`), `stage.py`
  (`AvatarStage`), `interface.py` (an `AvatarHost` contract so a future
  **Live2D / sprite-rig / 3D** model can be swapped in without touching the UI).
- **Facial states:** `IDLE · LISTENING · THINKING · SPEAKING · EXECUTING ·
  SUCCESS · ERROR` (the new `SUCCESS` state is also reflected in `STATE_DEFS`,
  the status label, and the mic readout).

### 21.2 The Indian female voice

NOVA's default provider is **edge-tts** with Microsoft's neural Indian female
voices (free, high quality, needs internet):

| Language used by the user | Voice picked |
|---|---|
| English | `en-IN-NeerjaNeural` (Indian English, F) |
| Hindi (Devanagari) | `hi-IN-SwaraNeural` (Hindi, F — bilingual) |
| Hinglish (Romanised) | `hi-IN-SwaraNeural` — she naturally blends Hindi + English |

- `voice/language.py` auto-detects the user's language: Devanagari script →
  Hindi; a Romanised-Hindi lexicon → Hinglish; otherwise English.
- `VoiceController` (`voice/controller.py`) applies the chosen
  `VOICE_LANGUAGE` mode, volume and speed live, and routes
  responses/speech accordingly.
- **Offline fallback:** `VOICE_PROVIDER = windows-sapi` uses the installed
  Windows SAPI voices (`VOICE_SAPI_NAME` to pick one).
- **Language-aware replies:** after a *verified successful* action NOVA
  answers with a natural prefix in the user's language
  (“Sure, …” / “ज़रूर, …”). Refusals, confirmations and errors keep their
  neutral, safe phrasing.
- Editable live in **SETTINGS ⚙ → VOICE**: master switch, volume, speed,
  provider, language mode, and auto-detect — with a **TEST VOICE** button.
  Changes persist to `.env` through `write_env`.

### 21.3 Voice provider architecture

```
voice/language.py           detect_lang(), effective_language() (AUTO/EN/HI/HINGLISH)
voice/controller.py         VoiceController: settings + async speak + persistence
voice/providers/
    __init__.py             VoiceProvider (abstract contract)
    edge.py                 EdgeVoiceProvider  (+ NullVoiceProvider)
    sapi.py                 WindowsSAPIVoiceProvider (offline)
```

Every provider implements the same contract (`speak(text, lang)`,
`apply(volume, speed)`, `stop()`, `voices()`, `describe()`), so the UI, brain
and listener stay provider-agnostic. Speech always runs on a worker thread —
the UI never blocks.

### 21.4 New Phase-3 dependencies

- `edge-tts` — neural TTS synthesis (speaker voices above)
- `pygame` — MP3 playback of synthesized audio
- (optional) `pyttsx3` + `pywin32` — offline SAPI provider

### 21.5 Testing

- `python -X utf8 -m unittest discover -s tests` → **48 tests** (safety,
  automation files, brain intents incl. language-aware replies, language
  detection, voice-provider mapping — no audio/network calls).
- `python -u -X utf8 <smoke_main_window.py>` → end-to-end offscreen smoke:
  real `MainWindow` → `NovaAgent` → mocked tools, all seven character states,
  the success flash pipeline, and an avatar frame rendered to a PNG.

### 21.6 Roadmap update

- **Phase 1** — Core assistant + voice controls: ✅ (§1–§19)
- **Phase 2** — Secure risk-gated Windows automation: ✅ (§20)
- **Phase 3** — Procedural anime character + Indian female voice identity: ✅ (§21)
- **Next** — Live2D/3D model rigging, deeper facial emotion from voice/context,
  on-device voice emotion, longer agentic multi-step memory, vision, and
  browser automation.

---

**NOVA** — Phase 1 core voice + Aurora Core UI shipped; Phase 2 adds a secure, risk-gated Windows automation layer with verified execution; Phase 3 puts an original anime girl at the heart of the UI with a natural Indian female voice that follows your language.