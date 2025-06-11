from .utils import random_position, distance, generate_pond, point_in_poly
import random

# collision radii (tweak to match your asset sizes)
TREE_COLLISION_RADIUS = 20
ROCK_COLLISION_RADIUS = 15

class World:
    def __init__(self, cfg):
        self.width      = cfg['width']
        self.height     = cfg['height']
        self.center     = (self.width/2, self.height/2)
        self.buildings  = cfg.get('buildings', [])

        # procedurally generate 4 organic ponds
        self.ponds = []
        for _ in range(4):
            center = random_position(self.width, self.height)
            radius = random.uniform(20, 100)
            self.ponds.append(generate_pond(center, radius))

        # will be populated by the engine for collision/LOS
        self.trees = []  # list of (x,y) positions
        self.rocks = []  # list of (x,y) positions

    def in_wall(self, pos):
        x, y = pos
        # check building walls/doors
        for b in self.buildings:
            for seg in b.get('walls', []) + b.get('interiors', []):
                if seg['x'] <= x <= seg['x'] + seg['width'] and seg['y'] <= y <= seg['y'] + seg['height']:
                    # door exception
                    for d in b.get('doors', []):
                        if d['x'] <= x <= d['x'] + d['width'] and d['y'] <= y <= d['y'] + d['height']:
                            return False
                    return True

        # block movement into any tree
        for tx, ty in self.trees:
            if distance(pos, (tx, ty)) < TREE_COLLISION_RADIUS:
                return True

        # block movement into any rock
        for rx, ry in self.rocks:
            if distance(pos, (rx, ry)) < ROCK_COLLISION_RADIUS:
                return True

        return False

    def in_building(self, pos):
        # bounding-box test to keep spawns out of building interiors
        x, y = pos
        for b in self.buildings:
            xs = [w['x'] for w in b.get('walls', [])]
            ws = [w['width'] for w in b.get('walls', [])]
            ys = [w['y'] for w in b.get('walls', [])]
            hs = [w['height'] for w in b.get('walls', [])]
            minx = min(xs)
            maxx = max(x0 + w0 for x0, w0 in zip(xs, ws))
            miny = min(ys)
            maxy = max(y0 + h0 for y0, h0 in zip(ys, hs))
            if minx <= x <= maxx and miny <= y <= maxy:
                return True
        return False

    def is_in_water(self, pos):
        # check procedural ponds
        for poly in self.ponds:
            if point_in_poly(pos, poly):
                return True
        return False

    def has_line_of_sight(self, p1, p2):
        # sample points along the line for wall collisions, trees, and rocks
        steps = max(1, int(distance(p1, p2) // 5))
        for i in range(1, steps + 1):
            t = i / steps
            x = p1[0] + (p2[0] - p1[0]) * t
            y = p1[1] + (p2[1] - p1[1]) * t

            # blocked by walls
            if self.in_wall((x, y)):
                return False

            # blocked by trees
            for tx, ty in self.trees:
                if distance((x, y), (tx, ty)) < TREE_COLLISION_RADIUS:
                    return False

            # blocked by rocks
            for rx, ry in self.rocks:
                if distance((x, y), (rx, ry)) < ROCK_COLLISION_RADIUS:
                    return False

        return True

    def random_pos(self):
        # avoid walls, building interiors, and water
        while True:
            pos = random_position(self.width, self.height)
            if (
                not self.in_wall(pos)
                and not self.in_building(pos)
                and not self.is_in_water(pos)
            ):
                return pos
