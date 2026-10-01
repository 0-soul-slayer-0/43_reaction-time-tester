import pygame
from .round import Round

# Game Engine

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (90, 90, 90)
GREEN = (40, 180, 90)
BLUE = (50, 90, 170)
RED = (180, 50, 50)

class GameEngine:
    def __init__(self, width, height, rounds_total=5, min_wait_ms=1000, max_wait_ms=3000):
        self.width = width
        self.height = height

        self.rounds_total = rounds_total
        self.min_wait_ms = min_wait_ms
        self.max_wait_ms = max_wait_ms

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

    def handle_event(self, event):
        if self.game_over:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.exit_requested = True
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_DOWN:
                self._scroll_results(1)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_UP:
                self._scroll_results(-1)
            elif event.type == pygame.MOUSEWHEEL:
                self._scroll_results(-event.y)
            return
        is_click = event.type == pygame.MOUSEBUTTONDOWN
        is_space = event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE
        if (is_click or is_space) and self.round.state in ("waiting", "go"):
            reaction_ms = self.round.register_input()
            if reaction_ms is not None:
                self.reaction_times.append(reaction_ms)
            if self.round.state in ("result", "false_start"):
                self.result_shown_at = pygame.time.get_ticks()

    def on_frame_presented(self):
        self.round.mark_go_presented()

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
            self.game_over = True
            return
        self.round = Round(self.min_wait_ms, self.max_wait_ms)

    def average_reaction_ms(self):
        if not self.reaction_times:
            return 0
        return round(sum(self.reaction_times) / len(self.reaction_times))

    def render(self, screen):
        if self.game_over:
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
        return max(1, (self.height - 190) // 32)

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
        screen.blit(average, average.get_rect(midtop=(self.width // 2, self.height - 90)))

        hint = "Press Esc to exit"
        if len(self.reaction_times) > visible_rows:
            hint = "Up/Down or scroll to view results | Esc to exit"
        instructions = self.small_font.render(hint, True, WHITE)
        screen.blit(instructions, instructions.get_rect(midtop=(self.width // 2, self.height - 42)))
