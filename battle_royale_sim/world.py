# battle_royale_sim/world.py

from .utils import random_position

class World:
    def __init__(self, cfg):
        self.width   = cfg['width']
        self.height  = cfg['height']
        self.center  = (self.width/2, self.height/2)

        # load buildings if provided
        self.buildings = cfg.get('buildings', [])

    def in_building(self, pos):
        x, y = pos
        for b in self.buildings:
            if b['x'] <= x <= b['x'] + b['width'] \
            and b['y'] <= y <= b['y'] + b['height']:
                return True
        return False

    def random_pos(self):
        # pick positions outside buildings
        while True:
            x, y = random_position(self.width, self.height)
            if not self.in_building((x, y)):
                return (x, y)
