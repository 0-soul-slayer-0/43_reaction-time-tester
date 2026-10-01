import io
import math
import struct
import wave

import pygame


class SoundFeedback:
    """Generate short cues locally and play them without blocking gameplay."""

    def __init__(self):
        self._sounds = {}
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self._sounds = {
                "go": self._make_sound([(880, 0.12)]),
                "false_start": self._make_sound([(220, 0.12), (165, 0.16)]),
                "session_end": self._make_sound([(523, 0.12), (659, 0.12), (784, 0.20)]),
            }
        except pygame.error:
            # A missing audio device must not prevent the game from running.
            self._sounds = {}

    @property
    def enabled(self):
        return bool(self._sounds)

    @staticmethod
    def _make_sound(notes):
        sample_rate = 44100
        frames = bytearray()
        for frequency, duration in notes:
            count = round(sample_rate * duration)
            fade_samples = round(sample_rate * 0.01)
            for index in range(count):
                # Fade each note's edges to avoid clicks between tones.
                envelope = min(1.0, index / fade_samples, (count - 1 - index) / fade_samples)
                amplitude = int(32767 * 0.25 * envelope *
                                math.sin(2 * math.pi * frequency * index / sample_rate))
                frames.extend(struct.pack("<h", amplitude))
        data = io.BytesIO()
        with wave.open(data, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(frames)
        data.seek(0)
        return pygame.mixer.Sound(file=data)

    def play(self, cue):
        sound = self._sounds.get(cue)
        if sound is not None:
            try:
                sound.play()
            except pygame.error:
                # Continue silently if audio stops being available mid-session.
                self._sounds = {}
