"""
NOVA Voice Assistant - Listener
Manages the microphone, captures audio, and feeds it to the STT pipeline.
Runs in a background thread to keep the UI responsive.
"""

import threading
import time
import queue
from typing import Optional, Callable

import speech_recognition as sr

from config import config
from utils.logger import log
from voice.speech_to_text import create_stt_provider


class Listener:
    """
    Microphone listener that captures audio and converts to text.
    
    The listener uses SpeechRecognition's background listening to continuously
    capture audio. When audio is detected (and optionally after a wake word),
    it sends the audio to the STT provider for transcription.
    
    Signals state changes via callbacks so the UI can update accordingly.
    """

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone: Optional[sr.Microphone] = None
        self.stt = create_stt_provider()
        self._listening = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue = queue.Queue()

        # Callbacks
        self.on_state_change: Optional[Callable[[str], None]] = None
        self.on_text_captured: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_audio_level: Optional[Callable[[float], None]] = None

        # Wake word state
        self._awaiting_command = not config.wake_word.enabled
        self._wake_word = config.wake_word.word.lower()

        self._adjust_ambient = True

    @property
    def listening(self) -> bool:
        return self._listening

    @property
    def awaiting_command(self) -> bool:
        return self._awaiting_command

    def initialize(self) -> bool:
        """Initialize the microphone. Returns True if successful."""
        try:
            self.microphone = sr.Microphone()
            # Reduce noise threshold for better sensitivity
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.8
            log.info("Microphone initialized successfully")
            return True
        except OSError as e:
            log.error("No microphone found: %s", e)
            return False

    def calibrate(self, duration: float = 2.0):
        """Calibrate for ambient noise."""
        if not self.microphone:
            return
        try:
            with self.microphone as source:
                log.info("Calibrating for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=duration)
                log.info("Calibration complete. Energy threshold: %.0f",
                         self.recognizer.energy_threshold)
        except Exception as e:
            log.error("Calibration failed: %s", e)

    def start(self):
        """Start listening in background thread."""
        if self._listening:
            return
        if not self.microphone:
            if not self.initialize():
                return

        self._stop_event.clear()
        self._listening = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        self._emit_state("LISTENING")
        log.info("Listener started")

    def stop(self):
        """Stop listening."""
        self._listening = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._emit_state("IDLE")
        log.info("Listener stopped")

    def toggle(self):
        """Toggle listening on/off."""
        if self._listening:
            self.stop()
        else:
            self.start()

    def _emit_state(self, state: str):
        if self.on_state_change:
            self.on_state_change(state)

    def _emit_text(self, text: str):
        if self.on_text_captured:
            self.on_text_captured(text)

    def _emit_error(self, error: str):
        if self.on_error:
            self.on_error(error)

    def _emit_audio_level(self, level: float):
        if self.on_audio_level:
            self.on_audio_level(level)

    def _listen_loop(self):
        """Background loop: listen for audio, transcribe, repeat."""
        while self._listening and not self._stop_event.is_set():
            try:
                with self.microphone as source:
                    log.debug("Listening for audio...")
                    audio = self.recognizer.listen(
                        source, timeout=5, phrase_time_limit=10
                    )

                # Calculate audio level for waveform visualization
                raw_data = audio.get_raw_data()
                level = self._calculate_audio_level(raw_data)
                self._emit_audio_level(level)

                self._emit_state("PROCESSING")
                log.debug("Audio captured, transcribing...")

                # Transcribe
                text = self.stt.transcribe(raw_data, audio.sample_rate)

                if text:
                    text_lower = text.lower().strip()

                    # Wake word check
                    if config.wake_word.enabled and not self._awaiting_command:
                        if self._wake_word in text_lower:
                            self._awaiting_command = True
                            self._emit_text(config.wake_word.word)
                            self._emit_state("LISTENING")
                            continue
                        else:
                            self._emit_state("LISTENING")
                            continue

                    # Reset wake word state after command
                    if config.wake_word.enabled:
                        self._awaiting_command = False

                    self._emit_text(text)
                    log.info("Captured: %s", text)
                else:
                    self._emit_state("LISTENING")

            except sr.WaitTimeoutError:
                log.debug("No speech detected, continuing...")
                self._emit_state("LISTENING")
            except Exception as e:
                log.error("Listen loop error: %s", e)
                self._emit_error(str(e))
                time.sleep(0.5)
                self._emit_state("LISTENING")

    def _calculate_audio_level(self, raw_data: bytes) -> float:
        """Calculate normalized audio level from raw audio data."""
        try:
            import struct
            samples = struct.unpack(f"<{len(raw_data) // 2}h", raw_data)
            if not samples:
                return 0.0
            rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
            # Normalize to 0.0 - 1.0
            return min(rms / 15000.0, 1.0)
        except Exception:
            return 0.0
