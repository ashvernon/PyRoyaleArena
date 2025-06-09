import random, math

def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def random_position(width, height):
    return (random.uniform(0, width), random.uniform(0, height))
