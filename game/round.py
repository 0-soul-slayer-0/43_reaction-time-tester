import random
import pygame

class Round:
    def __init__(self, min_wait_ms=1000, max_wait_ms=3000):
        self.wait_delay_ms = random.randint(min_wait_ms, max_wait_ms)
        self.state = "waiting"  # "waiting" -> "go" -> "result"
        self.start_time = pygame.time.get_ticks()
        self.go_time = None
        self.reaction_ms = None

    def update(self):
        if self.state == "waiting":
            now = pygame.time.get_ticks()
            if now - self.start_time >= self.wait_delay_ms:
                self.state = "go"
                self.go_time = now

    def register_input(self):
        # NOTE: this always measures elapsed time since the round
        # STARTED (self.start_time), not since the screen actually
        # turned green (self.go_time) - and it never checks self.state
        # first. Two consequences: (1) a click during the grey
        # "waiting" phase is timed and recorded exactly like a real
        # reaction instead of being flagged as a false start, and (2)
        # even a genuine reaction after "go" is inflated by however
        # long the wait phase lasted, since the clock never resets
        # when the screen turns green. See Task 1 in the README.
        now = pygame.time.get_ticks()
        self.reaction_ms = now - self.start_time
        self.state = "result"
        return self.reaction_ms
