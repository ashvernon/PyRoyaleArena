from ..utils import distance
from .behavior import Behavior
from ..inventory import Inventory
from ..telemetry import log_event

class Agent:
    def __init__(self, idx, skill, luck, world, storm):
        self.id      = idx
        self.health  = 100
        self.shield  = 0
        self.skill   = skill
        self.luck    = luck
        self.pos     = world.random_pos()
        self.world   = world
        self.storm   = storm
        self.inventory = Inventory()
        self.behavior  = Behavior(self, world, storm)

    def tick(self, loot_items):
        # 1) Determine target
        if not self.storm.in_safe_zone(self.pos):
            target = self.storm.center
        else:
            target = self.behavior.choose_target(loot_items)

        # 2) Move toward target
        self._move_towards(target)

        # 3) Pickup loot
        for item in loot_items[:]:
            if distance(self.pos, item['pos']) < 10:
                self.inventory.add(item)
                loot_items.remove(item)
                log_event('pickup', {'agent': self.id,'item':item['type']})

        # 4) Storm damage
        if not self.storm.in_safe_zone(self.pos):
            dmg = self.storm.damage()
            self.health -= dmg
            log_event('storm_damage', {'agent': self.id,'damage':dmg})

    def _move_towards(self, target):
        dx, dy = target[0] - self.pos[0], target[1] - self.pos[1]
        dist   = distance(self.pos, target)
        if dist > 0:
            step = 2  # px per tick
            self.pos = (
                self.pos[0] + dx/dist*step,
                self.pos[1] + dy/dist*step
            )
