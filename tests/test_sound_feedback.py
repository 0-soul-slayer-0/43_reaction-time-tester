import os
import unittest
from unittest.mock import Mock, call, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
from game.game_engine import GameEngine
from game.sound_feedback import SoundFeedback


class SoundTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.addCleanup(pygame.quit)

    def test_three_distinct_playable_cues_are_generated(self):
        sounds = SoundFeedback()
        self.assertTrue(sounds.enabled)
        expected = {"go": 0.12, "false_start": 0.28, "session_end": 0.44}
        self.assertEqual(set(sounds._sounds), set(expected))
        raw_cues = []
        for name, duration in expected.items():
            sound = sounds._sounds[name]
            self.assertAlmostEqual(sound.get_length(), duration, delta=0.005)
            self.assertTrue(any(sound.get_raw()))
            self.assertIsNotNone(sound.play())
            raw_cues.append(sound.get_raw())
        self.assertEqual(len(set(raw_cues)), 3)

    def test_go_cue_only_after_first_green_frame_is_presented(self):
        with patch("pygame.time.get_ticks", return_value=1000):
            engine = GameEngine(600, 400, min_wait_ms=0, max_wait_ms=0)
        with patch.object(engine.sounds, "play") as play, \
                patch("pygame.time.get_ticks", return_value=1000):
            engine.update()
            self.assertEqual(engine.round.state, "go")
            play.assert_not_called()
            for _ in range(3):
                engine.render(pygame.Surface((600, 400)))
                engine.on_frame_presented()
                engine.update()
            play.assert_called_once_with("go")
            self.assertEqual(engine.round.go_time, 1000)

    def test_false_start_cue_once_for_each_control_and_not_on_repeated_input(self):
        events = [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),
                  pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1)]
        for event in events:
            with self.subTest(control=event.type):
                engine = GameEngine(600, 400)
                with patch.object(engine.sounds, "play") as play:
                    engine.handle_event(event)
                    engine.handle_event(event)
                    engine.render(pygame.Surface((600, 400)))
                    engine.on_frame_presented()
                    play.assert_called_once_with("false_start")
                self.assertEqual(engine.reaction_times, [])

    def test_session_end_cue_once_even_when_results_are_rendered_repeatedly(self):
        engine = GameEngine(600, 400, rounds_total=1)
        engine.reaction_times = [250]
        with patch.object(engine.sounds, "play") as play:
            engine._start_next_round()
            for _ in range(3):
                engine.update()
                engine.render(pygame.Surface((600, 400)))
                engine.on_frame_presented()
                engine._start_next_round()
            play.assert_called_once_with("session_end")

    def test_replay_rearms_go_and_completion_cues(self):
        engine = GameEngine(600, 400)
        with patch.object(engine.sounds, "play") as play:
            for _ in range(2):
                engine.start_session("Easy")
                with patch("pygame.time.get_ticks", return_value=engine.round.start_time + 2000):
                    engine.update()
                    engine.on_frame_presented()
                engine.reaction_times = [200] * 3
                engine._start_next_round()
            self.assertEqual(play.call_args_list,
                             [call("go"), call("session_end"), call("go"), call("session_end")])

    def test_full_round_sequence_has_no_false_start_sound_on_valid_input(self):
        with patch("pygame.time.get_ticks", return_value=1000):
            engine = GameEngine(600, 400, rounds_total=1, min_wait_ms=0, max_wait_ms=0)
        with patch.object(engine.sounds, "play") as play:
            with patch("pygame.time.get_ticks", return_value=1000):
                engine.update()
                engine.on_frame_presented()
            with patch("pygame.time.get_ticks", return_value=1250):
                engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
            with patch("pygame.time.get_ticks", return_value=2050):
                engine.update()
            self.assertEqual(play.call_args_list, [call("go"), call("session_end")])
            self.assertEqual(engine.reaction_times, [250])

    def test_no_cues_for_waiting_frames_or_replay_menu(self):
        engine = GameEngine(600, 400)
        with patch.object(engine.sounds, "play") as play:
            engine.on_frame_presented()
            engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
            engine.game_over = True
            engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
            engine.render(pygame.Surface((600, 400)))
            engine.on_frame_presented()
            play.assert_not_called()

    def test_unavailable_mixer_does_not_break_gameplay(self):
        with patch("pygame.mixer.get_init", return_value=None), \
                patch("pygame.mixer.init", side_effect=pygame.error("No audio device")):
            engine = GameEngine(600, 400)
        self.assertFalse(engine.sounds.enabled)
        engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        self.assertEqual(engine.round.state, "false_start")
        self.assertEqual(engine.reaction_times, [])
        engine.render(pygame.Surface((600, 400)))

    def test_playback_failure_disables_audio_without_crashing(self):
        sounds = SoundFeedback()
        broken = Mock()
        broken.play.side_effect = pygame.error("Device disconnected")
        sounds._sounds = {"go": broken}
        sounds.play("go")
        self.assertFalse(sounds.enabled)
        sounds.play("go")
        broken.play.assert_called_once()


if __name__ == "__main__":
    unittest.main()
