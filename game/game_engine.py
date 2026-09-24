import pygame
from .round import Round

# Game Engine

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (90, 90, 90)
GREEN = (40, 180, 90)
BLUE = (50, 90, 170)

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
        self.game_over = False

    def handle_event(self, event):
        if self.game_over:
            return
        is_click = event.type == pygame.MOUSEBUTTONDOWN
        is_space = event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE
        if (is_click or is_space) and self.round.state != "result":
            reaction_ms = self.round.register_input()
            self.reaction_times.append(reaction_ms)
            self.result_shown_at = pygame.time.get_ticks()

    def handle_input(self):
        # Reserved for continuously-held-key input; every action here
        # is a discrete click/keypress, handled in handle_event.
        pass

    def update(self):
        if self.game_over:
            return

        self.round.update()

        if self.round.state == "result":
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
        if self.round.state == "waiting":
            bg = GRAY
            message = "Wait for green..."
        elif self.round.state == "go":
            bg = GREEN
            message = "Click now!"
        else:
            bg = BLUE
            message = f"{self.round.reaction_ms} ms"

        screen.fill(bg)

        text_surf = self.big_font.render(message, True, WHITE)
        text_rect = text_surf.get_rect(center=(self.width // 2, self.height // 2))
        screen.blit(text_surf, text_rect)

        round_num = min(len(self.reaction_times) + 1, self.rounds_total)
        round_text = self.font.render(f"Round {round_num}/{self.rounds_total}", True, WHITE)
        screen.blit(round_text, (10, 10))

        avg_text = self.font.render(f"Avg: {self.average_reaction_ms()} ms", True, WHITE)
        screen.blit(avg_text, (self.width - 190, 10))

        if self.game_over and not getattr(self, "_game_over_logged", False):
            # NOTE: no proper results screen yet - see Task 2 in the README.
            print("Session complete! Reaction times (ms):", self.reaction_times)
            print("Average:", self.average_reaction_ms(), "ms")
            self._game_over_logged = True
