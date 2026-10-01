import random
import pygame

class Round:
    def __init__(self, min_wait_ms=1000, max_wait_ms=3000):
        self.wait_delay_ms = random.randint(min_wait_ms, max_wait_ms)
        self.state = "waiting"  # "waiting" -> "go" -> "result", or "false_start"
        self.start_time = pygame.time.get_ticks()
        self.go_time = None
        self.reaction_ms = None

    def update(self):
        if self.state == "waiting":
            now = pygame.time.get_ticks()
            if now - self.start_time >= self.wait_delay_ms:
                self.state = "go"

    def mark_go_presented(self):
        # Start timing only after the first green frame reaches the display.
        if self.state == "go" and self.go_time is None:
            self.go_time = pygame.time.get_ticks()

    def register_input(self):
        if self.state == "waiting":
            self.state = "false_start"
            return None
        if self.state != "go" or self.go_time is None:
            return None
        self.reaction_ms = pygame.time.get_ticks() - self.go_time
        self.state = "result"
        return self.reaction_ms
