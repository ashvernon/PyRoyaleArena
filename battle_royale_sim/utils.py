import random, math

def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def random_position(width, height):
    return (random.uniform(0, width), random.uniform(0, height))

def generate_pond(center, avg_radius, variation=0.3, points=8, smooth_iters=2):
    """
    Returns a list of (x,y) vertices approximating a natural pond polygon.
    """
    cx, cy = center
    pts = []
    for i in range(points):
        angle  = 2*math.pi * i/points
        radius = avg_radius * random.uniform(1-variation, 1+variation)
        pts.append((cx + math.cos(angle)*radius,
                    cy + math.sin(angle)*radius))
    # Chaikin smoothing
    for _ in range(smooth_iters):
        new_pts = []
        for j in range(len(pts)):
            p0 = pts[j]
            p1 = pts[(j+1)%len(pts)]
            q  = (0.75*p0[0] + 0.25*p1[0], 0.75*p0[1] + 0.25*p1[1])
            r  = (0.25*p0[0] + 0.75*p1[0], 0.25*p0[1] + 0.75*p1[1])
            new_pts.extend([q,r])
        pts = new_pts
    return pts

def point_in_poly(pt, poly):
    """
    Ray‐casting algorithm to test if pt=(x,y) is inside polygon poly.
    """
    x, y = pt
    inside = False
    for i in range(len(poly)):
        x0,y0 = poly[i]
        x1,y1 = poly[(i+1)%len(poly)]
        if ((y0>y) != (y1>y)) and (x < (x1-x0)*(y-y0)/(y1-y0) + x0):
            inside = not inside
    return inside