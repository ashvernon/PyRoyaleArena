import random
import math
from ..utils import distance

class Behavior:
    def __init__(self, agent, world, storm):
        self.agent = agent
        self.world = world
        self.storm = storm

    def select_action(self, agents, loot_items):
        a = self.agent

        # 1) Attack utility
        enemies = [e for e in agents if e.id != a.id and e.health > 0]
        d_enemy = min((distance(a.pos, e.pos) for e in enemies), default=math.inf)
        attack_score = 0.0
        if a.inventory.weapons:
            attack_score = (a.health / 100.0) * max(0.0, 1 - d_enemy / a.inventory.weapons[0].range)

        # 2) Loot utility
        loot_dists = [distance(a.pos, it['pos']) for it in loot_items]
        d_loot = min(loot_dists, default=math.inf)
        inv_load = len(a.inventory.weapons) + len(a.inventory.consumables)
        loot_score = (1 - inv_load / 10.0) * max(0.0, 1 - d_loot / (self.world.width / 2))

        # 3) Flee utility
        flee_score = (1 - a.health / 100.0)
        if not self.storm.in_safe_zone(a.pos):
            flee_score += 1.0

        # 4) Boundary-hug utility
        dist_center = distance(a.pos, self.world.center)
        radius      = self.storm.radius
        boundary_score = 0.0
        if radius > 0:
            boundary_score = 1 - abs(dist_center - radius) / radius

        # Collect and pick highest
        scores = {
            'attack':   attack_score,
            'loot':     loot_score,
            'flee':     flee_score,
            'boundary': boundary_score,
            'roam':     0.1
        }
        action, _ = max(scores.items(), key=lambda kv: kv[1])

        # Determine movement target if not attacking
        if action == 'attack' and enemies:
            target = min(enemies, key=lambda e: distance(a.pos, e.pos)).pos
        elif action == 'loot' and loot_items:
            target = min(loot_items, key=lambda it: distance(a.pos, it['pos']))['pos']
        elif action == 'flee':
            target = self.world.center
        elif action == 'boundary':
            angle = random.random() * 2 * math.pi
            target = (
                self.world.center[0] + math.cos(angle) * radius,
                self.world.center[1] + math.sin(angle) * radius
            )
        else:
            target = self.world.random_pos()

        return action, target
