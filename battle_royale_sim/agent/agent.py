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
    def __init__(self, idx, skill, luck, world, storm, color):
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
        self.color = color
        self.current_action = None
        self.last_decision  = None

    def tick(self, agents, loot_items):
        # 0) Decide next action
        decision, target = self.behavior.select_action(agents, loot_items)
        self.last_decision = decision

        # 1) Execute: either attack or move, record what actually happened
        if decision == 'attack':
            shot = self.attack(agents)
            self.current_action = 'attack' if shot else 'idle'
        else:
            self._move_towards(target)
            self.current_action = 'move'

        # 2) Loot pickup
        for item in loot_items[:]:
            if distance(self.pos, item['pos']) < 10:
                self.inventory.add(item)
                loot_items.remove(item)
                log_event('pickup', {'agent': self.id, 'item': item['type']})

        # 2.5) Auto‐use consumables if needed
        MAX_HEALTH = 100
        MAX_SHIELD = 50

        # — Medkit restores health —
        for cons in self.inventory.consumables[:]:
            if cons['name'] == 'medkit' and self.health < MAX_HEALTH:
                amt = cons['amount']
                self.health = min(MAX_HEALTH, self.health + amt)
                self.inventory.consumables.remove(cons)
                log_event('use_consumable', {
                    'agent':    self.id,
                    'item':     'medkit',
                    'restored': amt
                })
                break

        # — Shield‐kit restores shield —
        for cons in self.inventory.consumables[:]:
            if cons['name'] == 'shield' and self.shield < MAX_SHIELD:
                amt = cons['amount']
                self.shield = min(MAX_SHIELD, self.shield + amt)
                self.inventory.consumables.remove(cons)
                log_event('use_consumable', {
                    'agent':    self.id,
                    'item':     'shield',
                    'restored': amt
                })
                break

        # 3) Storm damage (eat shield first, then health)
        if not self.storm.in_safe_zone(self.pos):
            dmg = self.storm.damage()
            # shields absorb first
            if self.shield > 0:
                blocked = min(self.shield, dmg)
                self.shield -= blocked
                dmg -= blocked
            # any remainder hits health
            if dmg > 0:
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
        if not self.world.has_line_of_sight(self.pos, target.pos):
            return None
        if distance(self.pos, target.pos) > weapon.range:
            return None

        hit_chance = weapon.accuracy * self.skill
        if random.random() <= hit_chance:
            dmg = weapon.damage
            # shields absorb first
            if target.shield > 0:
                blocked = min(target.shield, dmg)
                target.shield -= blocked
                dmg -= blocked
            # leftover goes to health
            if dmg > 0:
                target.health -= dmg

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
            base_step = 2
            # slow down in water
            if self.world.is_in_water(self.pos):
                step = base_step * 0.5
            else:
                step = base_step
            new_pos = (
                self.pos[0] + dx / dist * step,
                self.pos[1] + dy / dist * step
            )
            # only move if not colliding a wall
            if not self.world.in_wall(new_pos):
                self.pos = new_pos
