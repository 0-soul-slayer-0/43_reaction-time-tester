import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
from game.game_engine import GameEngine, GREEN, RED
from game.round import Round


class TimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.clock = patch("pygame.time.get_ticks")
        self.ticks = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.ticks.return_value = 1000

    def make_engine(self, rounds_total=5):
        return GameEngine(600, 400, rounds_total, 1500, 1500)

    def show_green(self, engine):
        self.ticks.return_value = 2500
        engine.update()
        screen = pygame.Surface((600, 400))
        engine.render(screen)
        self.assertEqual(screen.get_at((0, 0))[:3], GREEN)
        # Simulate the first green frame being presented after rendering.
        self.ticks.return_value = 2520
        engine.on_frame_presented()

    def test_wait_delay_is_excluded_from_reaction(self):
        engine = self.make_engine()
        self.show_green(engine)
        self.ticks.return_value = 2770
        engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        self.assertEqual(engine.reaction_times, [250])
        self.assertEqual(engine.average_reaction_ms(), 250)

    def test_go_clock_waits_for_presented_frame(self):
        round_ = Round(1500, 1500)
        self.ticks.return_value = 2500
        round_.update()
        self.assertEqual(round_.state, "go")
        self.assertIsNone(round_.go_time)
        self.assertIsNone(round_.register_input())
        self.assertEqual(round_.state, "go")
        self.ticks.return_value = 2520
        round_.mark_go_presented()
        self.assertEqual(round_.go_time, 2520)

    def test_later_frames_do_not_reset_go_clock(self):
        engine = self.make_engine()
        self.show_green(engine)
        self.ticks.return_value = 2600
        engine.on_frame_presented()
        self.assertEqual(engine.round.go_time, 2520)

    def test_both_controls_reject_early_input(self):
        events = [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1),
                  pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)]
        for event in events:
            with self.subTest(event_type=event.type):
                self.ticks.return_value = 1000
                engine = self.make_engine()
                self.ticks.return_value = 1100
                engine.handle_event(event)
                self.assertEqual(engine.round.state, "false_start")
                self.assertIsNone(engine.round.reaction_ms)
                self.assertEqual(engine.reaction_times, [])

    def test_both_controls_accept_valid_reactions(self):
        events = [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1),
                  pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)]
        for event in events:
            with self.subTest(event_type=event.type):
                self.ticks.return_value = 1000
                engine = self.make_engine()
                self.show_green(engine)
                self.ticks.return_value = 2670
                engine.handle_event(event)
                self.assertEqual(engine.reaction_times, [150])

    def test_false_start_renders_feedback(self):
        engine = self.make_engine()
        engine.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1))
        screen = pygame.Surface((600, 400))
        engine.render(screen)
        self.assertEqual(screen.get_at((0, 0))[:3], RED)

    def test_false_start_retries_without_completing_round(self):
        engine = self.make_engine(rounds_total=1)
        self.ticks.return_value = 1100
        engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        self.ticks.return_value = 1899
        engine.update()
        self.assertEqual(engine.round.state, "false_start")
        self.ticks.return_value = 1900
        engine.update()
        self.assertEqual(engine.round.state, "waiting")
        self.assertEqual(engine.reaction_times, [])
        self.assertFalse(engine.game_over)

    def test_false_start_preserves_existing_average(self):
        engine = self.make_engine()
        engine.reaction_times = [200, 300]
        engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        self.assertEqual(engine.reaction_times, [200, 300])
        self.assertEqual(engine.average_reaction_ms(), 250)

    def test_result_label_stays_on_completed_round(self):
        engine = self.make_engine()
        self.show_green(engine)
        self.ticks.return_value = 2770
        engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        with patch.object(engine, "font", wraps=engine.font) as font:
            engine.render(pygame.Surface((600, 400)))
            self.assertEqual(font.render.call_args_list[0].args[0], "Round 1/5")
        self.ticks.return_value = 3570
        engine.update()
        with patch.object(engine, "font", wraps=engine.font) as font:
            engine.render(pygame.Surface((600, 400)))
            self.assertEqual(font.render.call_args_list[0].args[0], "Round 2/5")

    def test_repeated_input_cannot_overwrite_result(self):
        engine = self.make_engine()
        self.show_green(engine)
        self.ticks.return_value = 2770
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
        engine.handle_event(event)
        self.ticks.return_value = 2870
        engine.handle_event(event)
        self.assertEqual(engine.reaction_times, [250])
        self.assertEqual(engine.round.reaction_ms, 250)
        self.assertIsNone(engine.round.register_input())

    def test_repeated_false_start_does_not_extend_pause(self):
        engine = self.make_engine()
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
        self.ticks.return_value = 1100
        engine.handle_event(event)
        self.ticks.return_value = 1200
        engine.handle_event(event)
        self.assertEqual(engine.result_shown_at, 1100)

    def test_zero_ms_reaction_is_valid(self):
        engine = self.make_engine()
        self.show_green(engine)
        engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        self.assertEqual(engine.reaction_times, [0])

    def test_session_completes_after_valid_round(self):
        engine = self.make_engine(rounds_total=1)
        self.show_green(engine)
        self.ticks.return_value = 2770
        engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        self.ticks.return_value = 3570
        engine.update()
        self.assertTrue(engine.game_over)
        self.assertEqual(engine.reaction_times, [250])

    def test_unrelated_keys_and_game_over_input_are_ignored(self):
        engine = self.make_engine()
        engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
        self.assertEqual(engine.round.state, "waiting")
        engine.game_over = True
        engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        self.assertEqual(engine.round.state, "waiting")
        self.assertEqual(engine.reaction_times, [])


if __name__ == "__main__":
    unittest.main()
