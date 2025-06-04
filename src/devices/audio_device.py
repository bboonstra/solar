"""
Audio Device Module for SOLAR Robot

This module provides an interface to audio output for playing notification sounds
and text-to-speech output using sounddevice.
"""

import logging
import threading
from typing import Dict, Optional

import numpy as np
import sounddevice as sd


class AudioDevice:
    """
    Interface to audio for notifications and TTS.

    Features:
    - Simple beep/notification sounds
    - Text-to-speech output (when enabled)
    - Thread-safe audio output
    - Configurable audio parameters
    """

    def __init__(self, config: Dict, production: bool = False):
        """
        Initialize the audio device.

        Args:
            config: Configuration dictionary
            production: Whether running in production mode
        """
        self.logger = logging.getLogger(__name__)
        self.production = production
        self.config = config.get("audio", {})

        # Audio device configuration
        self.sample_rate = self.config.get("sample_rate", 44100)
        self.channels = self.config.get("channels", 1)  # Mono output
        self.blocksize = self.config.get("blocksize", 1024)

        # Thread safety
        self._audio_lock = threading.Lock()
        self._stream: Optional[sd.OutputStream] = None

        # Initialize audio
        self._initialize_audio()

    def _generate_boot_jingle(self) -> np.ndarray:
        """Generate a cheerful boot-up jingle using an ascending arpeggio."""
        notes = [523.25, 659.25, 783.99, 1046.50]  # C5, E5, G5, C6
        note_duration = 0.15
        silence_duration = 0.05
        total_duration = (note_duration + silence_duration) * len(notes)
        total_samples = int(self.sample_rate * total_duration)
        jingle = np.zeros(total_samples, dtype=np.float64)

        for i, freq in enumerate(notes):
            start_pos = int(i * (note_duration + silence_duration) * self.sample_rate)
            end_pos = int(start_pos + note_duration * self.sample_rate)
            t = np.linspace(
                0, note_duration, end_pos - start_pos, False, dtype=np.float64
            )
            note = np.sin(2 * np.pi * freq * t, dtype=np.float64)

            fade_len = min(int(0.01 * self.sample_rate), len(note) // 4)
            envelope = np.ones_like(note)
            envelope[:fade_len] = np.linspace(0, 1, fade_len, dtype=np.float64)
            envelope[-fade_len:] = np.linspace(1, 0, fade_len, dtype=np.float64)
            note *= envelope

            jingle[start_pos:end_pos] = note

        return jingle.astype(np.float32).reshape(-1, 1)

    def _initialize_audio(self) -> bool:
        """Initialize the audio output stream with explicit OutputStream to prevent ALSA underruns."""
        try:
            self._stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=np.float32,
                blocksize=self.blocksize,
                latency="low",
            )
            self._stream.start()
            self.logger.info("Audio device initialized successfully")

            if self.production:
                try:
                    with self._audio_lock:
                        jingle = self._generate_boot_jingle()
                        self._stream.write(jingle)
                except Exception as e:
                    self.logger.warning(f"Could not play boot jingle: {e}")

            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize audio device: {e}")
            return False

    def _generate_beep(self, frequency: float, duration: float) -> np.ndarray:
        """Generate a simple sine wave beep."""
        t = np.linspace(
            0, duration, int(self.sample_rate * duration), False, dtype=np.float64
        )
        samples = np.sin(2 * np.pi * frequency * t, dtype=np.float64)

        fade_len = min(int(0.005 * self.sample_rate), len(samples) // 4)
        fade_in = np.linspace(0, 1, fade_len, dtype=np.float64)
        fade_out = np.linspace(1, 0, fade_len, dtype=np.float64)
        samples[:fade_len] *= fade_in
        samples[-fade_len:] *= fade_out

        return samples.astype(np.float32).reshape(-1, 1)

    def play_beep(self, frequency: float = 440.0, duration: float = 0.2) -> bool:
        """Play a beep sound using the persistent OutputStream to avoid underrun and truncation."""
        if not self._stream:
            self.logger.error("Audio device not initialized")
            return False

        try:
            with self._audio_lock:
                audio_data = self._generate_beep(frequency, duration)
                self._stream.write(audio_data)
                silence = np.zeros((int(0.05 * self.sample_rate), 1), dtype=np.float32)
                self._stream.write(silence)
            return True
        except Exception as e:
            self.logger.error(f"Error playing beep: {e}")
            return False

    def play_notification(self, notification_type: str = "info") -> bool:
        notifications = {
            "info": (440, 0.1),
            "success": (880, 0.2),
            "warning": (220, 0.3),
            "error": (110, 0.5),
        }
        freq, dur = notifications.get(notification_type, (440, 0.1))
        return self.play_beep(freq, dur)

    def speak_text(self, text: str) -> bool:
        self.logger.warning("TTS not yet implemented")
        return self.play_notification("info")

    def cleanup(self) -> None:
        if self._stream:
            try:
                with self._audio_lock:
                    self._stream.stop()
                    self._stream.close()
                    self._stream = None
                self.logger.debug("Audio device cleaned up")
            except Exception as e:
                self.logger.error(f"Error cleaning up audio device: {e}")

    def is_healthy(self) -> bool:
        if not self._stream:
            return False
        try:
            return self.play_beep(440, 0.01)
        except Exception:
            return False

    def play_boot_jingle(self) -> bool:
        if not self._stream:
            self.logger.error("Audio device not initialized")
            return False
        try:
            with self._audio_lock:
                jingle = self._generate_boot_jingle()
                self._stream.write(jingle)
            return True
        except Exception as e:
            self.logger.error(f"Error playing boot jingle: {e}")
            return False
