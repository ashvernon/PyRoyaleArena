from .utils import random_position

class World:
    def __init__(self, cfg):
        self.width  = cfg['width']
        self.height = cfg['height']
        self.center = (self.width/2, self.height/2)

    def random_pos(self):
        return random_position(self.width, self.height)
