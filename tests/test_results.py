import contextlib
import io
import os
import runpy
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
from game.game_engine import GameEngine


class ResultsTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.addCleanup(pygame.quit)

    def completed_engine(self, times=None):
        times = [210, 250, 180, 320, 240] if times is None else times
        engine = GameEngine(600, 400, rounds_total=len(times))
        engine.reaction_times = times.copy()
        engine._start_next_round()
        return engine

    def capture_results_text(self, engine):
        with patch.object(engine, "small_font", wraps=engine.small_font) as small_font, \
                patch.object(engine, "font", wraps=engine.font) as font, \
                patch.object(engine, "big_font", wraps=engine.big_font) as big_font:
            engine.render(pygame.Surface((600, 400)))
            return [call.args[0] for renderer in (big_font, small_font, font)
                    for call in renderer.render.call_args_list]

    def test_final_screen_shows_every_round_and_average(self):
        engine = self.completed_engine()
        text = self.capture_results_text(engine)
        self.assertIn("Session complete", text)
        for index, time in enumerate(engine.reaction_times, 1):
            self.assertIn(f"Round {index}: {time} ms", text)
        self.assertIn("Average: 240 ms", text)
        self.assertIn("Press Esc to exit", text)
        self.assertNotIn("Wait for green...", text)

    def test_final_screen_stays_until_exit_input(self):
        engine = self.completed_engine()
        round_ = engine.round
        for event in [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),
                      pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1)]:
            engine.handle_event(event)
        with patch("pygame.time.get_ticks", return_value=100000):
            engine.update()
        self.assertTrue(engine.game_over)
        self.assertFalse(engine.exit_requested)
        self.assertIs(engine.round, round_)
        self.assertEqual(engine.reaction_times, [210, 250, 180, 320, 240])
        self.assertIn("Session complete", self.capture_results_text(engine))

    def test_results_render_without_console_output(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.capture_results_text(self.completed_engine())
        self.assertEqual(output.getvalue(), "")

    def test_escape_requests_exit_from_results(self):
        engine = self.completed_engine()
        engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertTrue(engine.exit_requested)

    def test_long_session_all_results_accessible_and_average_fixed(self):
        times = list(range(100, 110))
        engine = self.completed_engine(times)
        text = self.capture_results_text(engine)
        self.assertIn("Round 1: 100 ms", text)
        for _ in range(20):
            engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
            text += self.capture_results_text(engine)
        for index, time in enumerate(times, 1):
            self.assertIn(f"Round {index}: {time} ms", text)
        self.assertEqual(engine.results_scroll, 10 - engine._visible_results_rows())
        self.assertIn("Average: 104 ms", self.capture_results_text(engine))
        self.assertFalse(engine.exit_requested)
        engine.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=100))
        self.assertEqual(engine.results_scroll, 0)
        engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
        self.assertEqual(engine.results_scroll, 0)

    def test_final_results_appear_after_last_valid_result_pause(self):
        engine = GameEngine(600, 400, rounds_total=1, min_wait_ms=0, max_wait_ms=0)
        with patch("pygame.time.get_ticks", return_value=1000):
            engine.update()
            engine.on_frame_presented()
        with patch("pygame.time.get_ticks", return_value=1250):
            engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        self.assertFalse(engine.game_over)
        with patch("pygame.time.get_ticks", return_value=2049):
            engine.update()
        self.assertFalse(engine.game_over)
        with patch("pygame.time.get_ticks", return_value=2050):
            engine.update()
        text = self.capture_results_text(engine)
        self.assertTrue(engine.game_over)
        self.assertIn("Round 1: 250 ms", text)
        self.assertIn("Average: 250 ms", text)

    def test_results_wait_in_real_game_loop_then_escape_shuts_down(self):
        app = runpy.run_path("main.py", run_name="startup_check")
        app["engine"].reaction_times = [210, 250, 180, 320, 240]
        app["engine"]._start_next_round()
        frames = iter([[], [], [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)]])
        with patch("pygame.event.get", side_effect=lambda: next(frames)), \
                patch("pygame.display.flip", wraps=pygame.display.flip) as flip:
            app["main"]()
        self.assertEqual(flip.call_count, 2)
        self.assertFalse(pygame.get_init())

    def test_window_close_shuts_down(self):
        app = runpy.run_path("main.py", run_name="startup_check")
        with patch("pygame.event.get", return_value=[pygame.event.Event(pygame.QUIT)]):
            app["main"]()
        self.assertFalse(pygame.get_init())


if __name__ == "__main__":
    unittest.main()
