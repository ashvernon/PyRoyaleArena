import random
from ..utils import distance
from .behavior import Behavior
from ..inventory import Inventory
from ..telemetry import log_event
from ..constants import TICK_RATE

import random
from ..utils import distance
from .behavior import Behavior
from ..inventory import Inventory
from ..telemetry import log_event
from ..constants import TICK_RATE

class Agent:
    def __init__(self, idx, skill, luck, world, storm):
        self.id             = idx
        self.health         = 100
        self.shield         = 0
        self.skill          = skill
        self.luck           = luck
        self.pos            = world.random_pos()
        self.world          = world
        self.storm          = storm
        self.inventory      = Inventory()
        self.behavior       = Behavior(self, world, storm)
        self.cooldown_ticks = 0

    def tick(self, agents, loot_items):
        # 0) Decide next action
        action, target = self.behavior.select_action(agents, loot_items)

        # 1) Execute: either attack or move
        if action == 'attack':
            _ = self.attack(agents)
        else:
            self._move_towards(target)

        # 2) Loot pickup
        for item in loot_items[:]:
            if distance(self.pos, item['pos']) < 10:
                self.inventory.add(item)
                loot_items.remove(item)
                log_event('pickup', {'agent': self.id, 'item': item['type']})

        # 3) Storm damage
        if not self.storm.in_safe_zone(self.pos):
            dmg = self.storm.damage()
            self.health -= dmg
            log_event('storm_damage', {'agent': self.id, 'damage': dmg})

    def attack(self, agents):
        if self.cooldown_ticks > 0:
            self.cooldown_ticks -= 1
            return None

        if not self.inventory.weapons:
            return None

        weapon  = self.inventory.weapons[0]
        enemies = [a for a in agents if a.id != self.id and a.health > 0]
        if not enemies:
            return None

        target = min(enemies, key=lambda a: distance(self.pos, a.pos))
        dist   = distance(self.pos, target.pos)
        if dist > weapon.range:
            return None

        hit_chance = weapon.accuracy * self.skill
        if random.random() <= hit_chance:
            target.health -= weapon.damage
            log_event('hit', {
                'shooter': self.id,
                'target':  target.id,
                'damage':  weapon.damage
            })
        else:
            log_event('miss', {
                'shooter': self.id,
                'target':  target.id
            })

        self.cooldown_ticks = max(1, int(TICK_RATE / weapon.fire_rate))
        return (self.pos, target.pos)

    def _move_towards(self, target):
        dx, dy = target[0] - self.pos[0], target[1] - self.pos[1]
        dist   = distance(self.pos, target)
        if dist > 0:
            step = 2
            self.pos = (
                self.pos[0] + dx / dist * step,
                self.pos[1] + dy / dist * step
            )
