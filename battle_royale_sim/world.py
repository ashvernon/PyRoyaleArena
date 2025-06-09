from .utils import random_position, distance

class World:
    def __init__(self, cfg):
        self.width      = cfg['width']
        self.height     = cfg['height']
        self.center     = (self.width/2, self.height/2)
        self.buildings  = cfg.get('buildings', [])

    def in_wall(self, pos):
        x, y = pos
        for b in self.buildings:
            # walls + interiors
            for seg in b.get('walls', []) + b.get('interiors', []):
                if seg['x'] <= x <= seg['x']+seg['width'] \
                and seg['y'] <= y <= seg['y']+seg['height']:
                    # if it's a door, it's NOT a wall
                    for d in b.get('doors', []):
                        if d['x'] <= x <= d['x']+d['width'] \
                        and d['y'] <= y <= d['y']+d['height']:
                            return False
                    return True
        return False

    def in_building(self, pos):
        # bounding‐box test to keep spawns out
        x, y = pos
        for b in self.buildings:
            xs = [w['x'] for w in b.get('walls',[])]
            ws = [w['width'] for w in b.get('walls',[])]
            ys = [w['y'] for w in b.get('walls',[])]
            hs = [w['height'] for w in b.get('walls',[])]
            minx = min(xs)
            maxx = max(x0 + w0 for x0,w0 in zip(xs, ws))
            miny = min(ys)
            maxy = max(y0 + h0 for y0,h0 in zip(ys, hs))
            if minx <= x <= maxx and miny <= y <= maxy:
                return True
        return False

    def has_line_of_sight(self, p1, p2):
        # sample points along the line; if any in_wall, block shot
        steps = int(distance(p1, p2) // 5)
        for i in range(1, steps + 1):
            t = i / steps
            x = p1[0] + (p2[0] - p1[0]) * t
            y = p1[1] + (p2[1] - p1[1]) * t
            if self.in_wall((x, y)):
                return False
        return True

    def random_pos(self):
        # avoid walls *and* full building interiors
        while True:
            pos = random_position(self.width, self.height)
            if not self.in_wall(pos) and not self.in_building(pos):
                return pos
