from .constants import TICK_RATE
from .utils import distance

class Storm:
    def __init__(self, phases, world):
        self.phases        = phases
        self.world         = world
        self.current_phase = 0
        self.ticks_in_phase = 0

        self.initial_radius = min(world.width, world.height) / 2
        self.center         = world.center
        self.radius         = self.initial_radius

    def update(self):
        phase = self.phases[self.current_phase]
        self.ticks_in_phase += 1

        # Advance phase if duration exceeded
        if self.ticks_in_phase >= phase['duration'] * TICK_RATE:
            if self.current_phase + 1 < len(self.phases):
                self.current_phase += 1
                self.ticks_in_phase = 0
            phase = self.phases[self.current_phase]

        # Linear shrink: fraction of total phases
        total = len(self.phases)
        fraction = (self.current_phase + self.ticks_in_phase / (phase['duration'] * TICK_RATE)) / total
        self.radius = self.initial_radius * (1 - fraction)

    def in_safe_zone(self, pos):
        return distance(pos, self.center) <= self.radius

    def damage(self):
        return self.phases[self.current_phase]['damage']
