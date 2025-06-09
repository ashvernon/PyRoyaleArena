from .constants import TICK_RATE
from .utils     import distance

class Storm:
    def __init__(self, phases, world):
        # phases: list of dicts with keys hold, shrink, damage
        self.phases         = phases
        self.world          = world
        self.current_phase  = 0
        self.ticks_in_phase = 0
        self.initial_radius = min(world.width, world.height) / 2
        self.center         = world.center
        self.radius         = self.initial_radius

    def update(self):
        phase = self.phases[self.current_phase]
        self.ticks_in_phase += 1

        hold_ticks   = phase['hold']   * TICK_RATE
        shrink_ticks = phase['shrink'] * TICK_RATE

        if self.ticks_in_phase <= hold_ticks:
            # still holding radius
            pass
        elif self.ticks_in_phase <= hold_ticks + shrink_ticks:
            # interpolating shrink
            elapsed_shrink = self.ticks_in_phase - hold_ticks
            frac = elapsed_shrink / shrink_ticks
            # radius = start_radius * (1 - (phase_index + frac)/total_phases)
            total = len(self.phases)
            self.radius = self.initial_radius * (1 - (self.current_phase + frac) / total)
        else:
            # move to next phase
            if self.current_phase + 1 < len(self.phases):
                self.current_phase += 1
                self.ticks_in_phase = 0

    def in_safe_zone(self, pos):
        return distance(pos, self.center) <= self.radius

    def damage(self):
        return self.phases[self.current_phase]['damage']
