import random
from ..utils import distance
from .behavior import Behavior
from ..inventory import Inventory
from ..telemetry import log_event
from ..constants import TICK_RATE

class Agent:
    def __init__(self, idx, skill, luck, world, storm):
        self.id            = idx
        self.health        = 100
        self.shield        = 0
        self.skill         = skill
        self.luck          = luck
        self.pos           = world.random_pos()
        self.world         = world
        self.storm         = storm
        self.inventory     = Inventory()
        self.behavior      = Behavior(self, world, storm)
        # combat cooldown in ticks
        self.cooldown_ticks = 0

    def tick(self, loot_items):
        # movement + loot (unchanged)
        if not self.storm.in_safe_zone(self.pos):
            target = self.storm.center
        else:
            target = self.behavior.choose_target(loot_items)

        self._move_towards(target)

        for item in loot_items[:]:
            if distance(self.pos, item['pos']) < 10:
                self.inventory.add(item)
                loot_items.remove(item)
                log_event('pickup', {'agent': self.id, 'item': item['type']})

        if not self.storm.in_safe_zone(self.pos):
            dmg = self.storm.damage()
            self.health -= dmg
            log_event('storm_damage', {'agent': self.id, 'damage': dmg})

    def attack(self, agents):
        # cooldown handling
        if self.cooldown_ticks > 0:
            self.cooldown_ticks -= 1
            return None

        # need at least one weapon
        if not self.inventory.weapons:
            return None

        # choose weapon (first slot)
        weapon = self.inventory.weapons[0]

        # find nearest alive enemy
        enemies = [a for a in agents if a.id != self.id and a.health > 0]
        if not enemies:
            return None

        target = min(enemies, key=lambda a: distance(self.pos, a.pos))
        dist = distance(self.pos, target.pos)
        if dist > weapon.range:
            return None

        # accuracy check
        hit_chance = weapon.accuracy * self.skill
        did_hit = (random.random() <= hit_chance)

        if did_hit:
            target.health -= weapon.damage
            log_event('hit', {
                'shooter':   self.id,
                'target':    target.id,
                'damage':    weapon.damage
            })
        else:
            log_event('miss', {
                'shooter': self.id,
                'target':  target.id
            })

        # start cooldown
        self.cooldown_ticks = max(1, int(TICK_RATE / weapon.fire_rate))

        # always return a shot to render, even if miss
        return (self.pos, target.pos)

    def _move_towards(self, target):
        dx, dy = target[0] - self.pos[0], target[1] - self.pos[1]
        dist   = distance(self.pos, target)
        if dist > 0:
            step = 2
            self.pos = (
                self.pos[0] + dx/dist*step,
                self.pos[1] + dy/dist*step
            )
