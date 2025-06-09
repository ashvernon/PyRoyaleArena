from ..utils import distance

class Behavior:
    def __init__(self, agent, world, storm):
        self.agent = agent
        self.world = world
        self.storm = storm

    def choose_target(self, loot_items):
        # If loot within 200px, go for nearest; else roam
        nearby = [it for it in loot_items if distance(self.agent.pos, it['pos']) < 200]
        if nearby:
            return min(nearby, key=lambda it: distance(self.agent.pos, it['pos']))['pos']
        return self.world.random_pos()
