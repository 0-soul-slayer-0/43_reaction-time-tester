import os
import runpy
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
from game.game_engine import DIFFICULTIES, GameEngine


class ReplayTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.addCleanup(pygame.quit)

    def completed_engine(self):
        engine = GameEngine(600, 400)
        engine.reaction_times = [100, 200, 300, 400, 500]
        engine.result_shown_at = 900
        engine.results_scroll = 2
        engine._start_next_round()
        return engine

    def open_menu(self, engine):
        engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
        self.assertTrue(engine.replay_menu)
        self.assertTrue(engine.game_over)

    def test_keyboard_presets_start_fresh_sessions(self):
        expected = [(pygame.K_1, "Easy", (3, 1000, 2000)),
                    (pygame.K_2, "Medium", (5, 1000, 3000)),
                    (pygame.K_3, "Hard", (10, 500, 5000))]
        for key, name, settings in expected:
            with self.subTest(difficulty=name):
                engine = self.completed_engine()
                previous_round = engine.round
                self.open_menu(engine)
                with patch("pygame.time.get_ticks", return_value=2000):
                    engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))
                self.assertEqual((engine.rounds_total, engine.min_wait_ms, engine.max_wait_ms), settings)
                self.assertEqual(engine.difficulty, name)
                self.assertEqual(engine.reaction_times, [])
                self.assertEqual(engine.average_reaction_ms(), 0)
                self.assertEqual(engine.results_scroll, 0)
                self.assertIsNone(engine.result_shown_at)
                self.assertFalse(engine.exit_requested)
                self.assertFalse(engine.game_over)
                self.assertFalse(engine.replay_menu)
                self.assertIsNot(engine.round, previous_round)
                self.assertEqual(engine.round.start_time, 2000)
                self.assertEqual(engine.round.state, "waiting")
                self.assertIsNone(engine.round.go_time)
                self.assertIsNone(engine.round.reaction_ms)
                self.assertGreaterEqual(engine.round.wait_delay_ms, settings[1])
                self.assertLessEqual(engine.round.wait_delay_ms, settings[2])

    def test_mouse_can_open_menu_and_choose_each_preset_without_false_start(self):
        for name in DIFFICULTIES:
            with self.subTest(difficulty=name):
                engine = self.completed_engine()
                replay, _ = engine._results_buttons()
                engine.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=replay.center))
                self.assertTrue(engine.replay_menu)
                rect = dict(engine._replay_buttons())[name]
                engine.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
                self.assertEqual(engine.difficulty, name)
                self.assertEqual(engine.round.state, "waiting")
                self.assertEqual(engine.reaction_times, [])

    def test_presets_cannot_start_directly_from_results_or_during_gameplay(self):
        engine = self.completed_engine()
        engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_3))
        self.assertTrue(engine.game_over)
        self.assertEqual(engine.reaction_times, [100, 200, 300, 400, 500])
        engine = GameEngine(600, 400)
        engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
        engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_3))
        self.assertFalse(engine.replay_menu)
        self.assertEqual(engine.rounds_total, 5)
        self.assertEqual(engine.round.state, "waiting")

    def test_menu_waits_for_selection_without_altering_results(self):
        engine = self.completed_engine()
        previous_round = engine.round
        self.open_menu(engine)
        for event in [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),
                      pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r),
                      pygame.event.Event(pygame.MOUSEWHEEL, y=-3),
                      pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0))]:
            engine.handle_event(event)
        engine.update()
        self.assertTrue(engine.replay_menu)
        self.assertEqual(engine.reaction_times, [100, 200, 300, 400, 500])
        self.assertIs(engine.round, previous_round)

    def test_exit_by_escape_or_button_from_results_and_menu(self):
        for menu in (False, True):
            for use_mouse in (False, True):
                with self.subTest(menu=menu, mouse=use_mouse):
                    engine = self.completed_engine()
                    if menu:
                        self.open_menu(engine)
                    if use_mouse:
                        rect = dict(engine._replay_buttons())["Exit"] if menu else engine._results_buttons()[1]
                        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center)
                    else:
                        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
                    engine.handle_event(event)
                    self.assertTrue(engine.exit_requested)

    def test_invalid_difficulty_leaves_session_intact(self):
        engine = self.completed_engine()
        with self.assertRaises(ValueError):
            engine.start_session("Unknown")
        self.assertTrue(engine.game_over)
        self.assertEqual(engine.reaction_times, [100, 200, 300, 400, 500])

    def test_menu_displays_presets_and_exit(self):
        engine = self.completed_engine()
        self.open_menu(engine)
        with patch.object(engine, "small_font", wraps=engine.small_font) as font:
            engine.render(pygame.Surface((600, 400)))
            text = [call.args[0] for call in font.render.call_args_list]
        for label in ["1. Easy (3 rounds, wait 1-2 s)",
                      "2. Medium (5 rounds, wait 1-3 s)",
                      "3. Hard (10 rounds, wait 0.5-5 s)", "Exit (Esc)"]:
            self.assertIn(label, text)

    def test_replayed_session_ends_after_selected_number_of_valid_rounds(self):
        for name, (rounds, _, _) in DIFFICULTIES.items():
            with self.subTest(difficulty=name):
                engine = self.completed_engine()
                engine.start_session(name)
                tick = engine.round.start_time
                for index in range(rounds):
                    tick += engine.round.wait_delay_ms
                    with patch("pygame.time.get_ticks", return_value=tick):
                        engine.update()
                        engine.on_frame_presented()
                    tick += 200
                    with patch("pygame.time.get_ticks", return_value=tick):
                        engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
                    tick += engine.result_pause_ms
                    with patch("pygame.time.get_ticks", return_value=tick):
                        engine.update()
                    self.assertEqual(engine.game_over, index == rounds - 1)
                self.assertEqual(engine.reaction_times, [200] * rounds)
                self.assertEqual(engine.average_reaction_ms(), 200)
                self.open_menu(engine)
                engine.start_session("Easy")
                self.assertEqual(engine.reaction_times, [])

    def test_real_game_loop_replays_and_closes(self):
        app = runpy.run_path("main.py", run_name="startup_check")
        engine = app["engine"]
        engine.reaction_times = [100] * 5
        engine._start_next_round()
        frames = iter([[pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)],
                       [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_3)],
                       [pygame.event.Event(pygame.QUIT)]])
        with patch("pygame.event.get", side_effect=lambda: next(frames)):
            app["main"]()
        self.assertEqual(engine.difficulty, "Hard")
        self.assertEqual(engine.reaction_times, [])
        self.assertFalse(pygame.get_init())


if __name__ == "__main__":
    unittest.main()
