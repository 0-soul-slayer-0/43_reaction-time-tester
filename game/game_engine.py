import pygame
from .round import Round
from .sound_feedback import SoundFeedback

# Game Engine

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (90, 90, 90)
GREEN = (40, 180, 90)
BLUE = (50, 90, 170)
RED = (180, 50, 50)

# Each preset defines (valid rounds, minimum wait ms, maximum wait ms).
DIFFICULTIES = {
    "Easy": (3, 1000, 2000),
    "Medium": (5, 1000, 3000),
    "Hard": (10, 500, 5000),
}

class GameEngine:
    def __init__(self, width, height, rounds_total=5, min_wait_ms=1000, max_wait_ms=3000):
        self.width = width
        self.height = height

        self.rounds_total = rounds_total
        self.min_wait_ms = min_wait_ms
        self.max_wait_ms = max_wait_ms

        self.sounds = SoundFeedback()
        self.round = Round(self.min_wait_ms, self.max_wait_ms)
        self.reaction_times = []

        self.result_shown_at = None
        self.result_pause_ms = 800  # brief pause on the result screen between rounds

        self.font = pygame.font.SysFont("Arial", 30)
        self.big_font = pygame.font.SysFont("Arial", 46)
        self.small_font = pygame.font.SysFont("Arial", 24)
        self.game_over = False
        self.exit_requested = False
        self.results_scroll = 0
        self.replay_menu = False
        self.difficulty = None

    def handle_event(self, event):
        if self.game_over:
            if self.replay_menu:
                self._handle_replay_menu(event)
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.exit_requested = True
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                self.replay_menu = True
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_DOWN:
                self._scroll_results(1)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_UP:
                self._scroll_results(-1)
            elif event.type == pygame.MOUSEWHEEL:
                self._scroll_results(-event.y)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                replay, exit_button = self._results_buttons()
                if replay.collidepoint(event.pos):
                    self.replay_menu = True
                elif exit_button.collidepoint(event.pos):
                    self.exit_requested = True
            return
        is_click = event.type == pygame.MOUSEBUTTONDOWN
        is_space = event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE
        if (is_click or is_space) and self.round.state in ("waiting", "go"):
            reaction_ms = self.round.register_input()
            if reaction_ms is not None:
                self.reaction_times.append(reaction_ms)
            if self.round.state in ("result", "false_start"):
                self.result_shown_at = pygame.time.get_ticks()
                if self.round.state == "false_start":
                    self.sounds.play("false_start")

    def on_frame_presented(self):
        if not self.game_over:
            first_go_frame = self.round.state == "go" and self.round.go_time is None
            self.round.mark_go_presented()
            if first_go_frame:
                self.sounds.play("go")

    def start_session(self, difficulty):
        if difficulty not in DIFFICULTIES:
            raise ValueError(f"Unknown difficulty: {difficulty}")
        self.rounds_total, self.min_wait_ms, self.max_wait_ms = DIFFICULTIES[difficulty]
        self.difficulty = difficulty
        self.reaction_times = []
        self.result_shown_at = None
        self.results_scroll = 0
        self.exit_requested = False
        self.game_over = False
        self.replay_menu = False
        self.round = Round(self.min_wait_ms, self.max_wait_ms)

    def _handle_replay_menu(self, event):
        if event.type == pygame.KEYDOWN:
            choices = {pygame.K_1: "Easy", pygame.K_2: "Medium", pygame.K_3: "Hard"}
            if event.key in choices:
                self.start_session(choices[event.key])
            elif event.key == pygame.K_ESCAPE:
                self.exit_requested = True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for label, rect in self._replay_buttons():
                if rect.collidepoint(event.pos):
                    if label == "Exit":
                        self.exit_requested = True
                    else:
                        self.start_session(label)
                    return

    def handle_input(self):
        # Reserved for continuously-held-key input; every action here
        # is a discrete click/keypress, handled in handle_event.
        pass

    def update(self):
        if self.game_over:
            return

        self.round.update()

        if self.round.state in ("result", "false_start"):
            now = pygame.time.get_ticks()
            if now - self.result_shown_at >= self.result_pause_ms:
                self._start_next_round()

    def _start_next_round(self):
        if len(self.reaction_times) >= self.rounds_total:
            if not self.game_over:
                self.game_over = True
                self.sounds.play("session_end")
            return
        self.round = Round(self.min_wait_ms, self.max_wait_ms)

    def average_reaction_ms(self):
        if not self.reaction_times:
            return 0
        return round(sum(self.reaction_times) / len(self.reaction_times))

    def render(self, screen):
        if self.game_over:
            if self.replay_menu:
                self._render_replay_menu(screen)
            else:
                self._render_results(screen)
            return

        if self.round.state == "waiting":
            bg = GRAY
            message = "Wait for green..."
        elif self.round.state == "go":
            bg = GREEN
            message = "Click now!"
        elif self.round.state == "false_start":
            bg = RED
            message = "False start! Try again."
        else:
            bg = BLUE
            message = f"{self.round.reaction_ms} ms"

        screen.fill(bg)

        text_surf = self.big_font.render(message, True, WHITE)
        text_rect = text_surf.get_rect(center=(self.width // 2, self.height // 2))
        screen.blit(text_surf, text_rect)

        # A valid result belongs to the round just completed; retries stay
        # on the next uncompleted round without increasing the count.
        round_num = len(self.reaction_times)
        if self.round.state != "result":
            round_num += 1
        round_num = min(round_num, self.rounds_total)
        round_text = self.font.render(f"Round {round_num}/{self.rounds_total}", True, WHITE)
        screen.blit(round_text, (10, 10))

        avg_text = self.font.render(f"Avg: {self.average_reaction_ms()} ms", True, WHITE)
        screen.blit(avg_text, (self.width - 190, 10))

    def _visible_results_rows(self):
        return max(1, (self.height - 215) // 32)

    def _scroll_results(self, delta):
        max_scroll = max(0, len(self.reaction_times) - self._visible_results_rows())
        self.results_scroll = max(0, min(self.results_scroll + delta, max_scroll))

    def _render_results(self, screen):
        screen.fill(BLUE)
        title = self.big_font.render("Session complete", True, WHITE)
        screen.blit(title, title.get_rect(midtop=(self.width // 2, 18)))

        visible_rows = self._visible_results_rows()
        first = self.results_scroll
        for row, reaction_ms in enumerate(self.reaction_times[first:first + visible_rows]):
            result = self.small_font.render(
                f"Round {first + row + 1}: {reaction_ms} ms", True, WHITE
            )
            screen.blit(result, result.get_rect(midtop=(self.width // 2, 90 + row * 32)))

        average = self.font.render(
            f"Average: {self.average_reaction_ms()} ms", True, WHITE
        )
        screen.blit(average, average.get_rect(midtop=(self.width // 2, self.height - 120)))

        if len(self.reaction_times) > visible_rows:
            instructions = self.small_font.render("Up/Down or scroll to view all rounds", True, WHITE)
            screen.blit(instructions, instructions.get_rect(midtop=(self.width // 2, self.height - 80)))
        replay, exit_button = self._results_buttons()
        self._draw_button(screen, replay, "Play again (R)")
        self._draw_button(screen, exit_button, "Exit (Esc)")

    def _results_buttons(self):
        width = (self.width - 100) // 2
        return (pygame.Rect(40, self.height - 48, width, 38),
                pygame.Rect(60 + width, self.height - 48, width, 38))

    def _replay_buttons(self):
        buttons = [(name, pygame.Rect(50, 92 + index * 70, self.width - 100, 52))
                   for index, name in enumerate(DIFFICULTIES)]
        buttons.append(("Exit", pygame.Rect(50, 302, self.width - 100, 44)))
        return buttons

    def _draw_button(self, screen, rect, label):
        pygame.draw.rect(screen, GRAY, rect, border_radius=8)
        text = self.small_font.render(label, True, WHITE)
        screen.blit(text, text.get_rect(center=rect.center))

    def _render_replay_menu(self, screen):
        screen.fill(BLUE)
        title = self.big_font.render("Play again", True, WHITE)
        screen.blit(title, title.get_rect(midtop=(self.width // 2, 18)))
        for index, (name, rect) in enumerate(self._replay_buttons(), 1):
            label = "Exit (Esc)"
            if name in DIFFICULTIES:
                rounds, minimum, maximum = DIFFICULTIES[name]
                label = f"{index}. {name} ({rounds} rounds, wait {minimum / 1000:g}-{maximum / 1000:g} s)"
            self._draw_button(screen, rect, label)
        hint = self.small_font.render("Click a choice or press 1, 2, or 3", True, WHITE)
        screen.blit(hint, hint.get_rect(midtop=(self.width // 2, self.height - 42)))
