import random
from .weapon import Weapon

class LootSpawner:
    def __init__(self, cfg, world):
        self.world            = world
        self.weapons_cfg      = cfg.get('weapons', {})
        self.consumables_cfg  = cfg.get('consumables', {})
        self.materials_cfg    = cfg.get('materials', {})

    def spawn_loot(self):
        items = []

        # Weapons
        for name, p in self.weapons_cfg.items():
            if random.random() < p['spawn_chance']:
                pos = self.world.random_pos()
                w = Weapon(
                    name,
                    damage        = p['damage'],
                    fire_rate     = p['fire_rate'],
                    accuracy      = p['accuracy'],
                    range         = p['range'],
                    magazine_size = p['magazine_size'],
                    reload_time   = p['reload_time']
                )
                items.append({'type': 'weapon','object': w,'pos': pos})

        # Consumables
        for name, p in self.consumables_cfg.items():
            if random.random() < p['spawn_chance']:
                pos = self.world.random_pos()
                items.append({
                    'type':   'consumable',
                    'name':   name,
                    'amount': p.get('heal_amount', p.get('shield_amount')),
                    'pos':    pos
                })

        # Materials
        for name, p in self.materials_cfg.items():
            if random.random() < p['spawn_chance']:
                pos = self.world.random_pos()
                items.append({'type':'material','name':name,'pos':pos})

        return items
    
    def spawn_initial_loot(self):
        items = []

        # 1. In-building loot: 2–3 per building (favor consumables/health)
        for b in self.world.buildings:
            xs = [w['x'] for w in b.get('walls',[])]
            ws = [w['width'] for w in b.get('walls',[])]
            ys = [w['y'] for w in b.get('walls',[])]
            hs = [w['height'] for w in b.get('walls',[])]
            minx = min(xs)
            maxx = max(x0 + w0 for x0, w0 in zip(xs, ws))
            miny = min(ys)
            maxy = max(y0 + h0 for y0, h0 in zip(ys, hs))

            for _ in range(random.randint(2, 3)):
                # Avoid placing in walls/interiors: retry if needed
                for _ in range(10):
                    x = random.uniform(minx + 8, maxx - 8)
                    y = random.uniform(miny + 8, maxy - 8)
                    if not self.world.in_wall((x, y)):
                        break
                # 70% consumable, 30% weapon
                loot_type = random.choices(['consumable', 'weapon'], weights=[0.7, 0.3])[0]
                if loot_type == 'weapon':
                    name, p = random.choice(list(self.weapons_cfg.items()))
                    w = Weapon(
                        name,
                        damage        = p['damage'],
                        fire_rate     = p['fire_rate'],
                        accuracy      = p['accuracy'],
                        range         = p['range'],
                        magazine_size = p['magazine_size'],
                        reload_time   = p['reload_time']
                    )
                    items.append({'type': 'weapon', 'object': w, 'pos': (x, y)})
                else:
                    name, p = random.choice(list(self.consumables_cfg.items()))
                    items.append({
                        'type':   'consumable',
                        'name':   name,
                        'amount': p.get('heal_amount', p.get('shield_amount')),
                        'pos':    (x, y)
                    })

        # 2. Outdoor loot: more weapons, scattered anywhere NOT in a building
        num_outdoor_loot = int(len(self.world.buildings) * 5)  # scale as needed
        for _ in range(num_outdoor_loot):
            for _ in range(10):  # try 10 times to find a good spot
                x = random.uniform(0, self.world.width)
                y = random.uniform(0, self.world.height)
                if not self.world.in_building((x, y)) and not self.world.in_wall((x, y)):
                    break
            # 80% weapons, 20% consumable
            loot_type = random.choices(['weapon', 'consumable'], weights=[0.8, 0.2])[0]
            if loot_type == 'weapon':
                name, p = random.choice(list(self.weapons_cfg.items()))
                w = Weapon(
                    name,
                    damage        = p['damage'],
                    fire_rate     = p['fire_rate'],
                    accuracy      = p['accuracy'],
                    range         = p['range'],
                    magazine_size = p['magazine_size'],
                    reload_time   = p['reload_time']
                )
                items.append({'type': 'weapon', 'object': w, 'pos': (x, y)})
            else:
                name, p = random.choice(list(self.consumables_cfg.items()))
                items.append({
                    'type':   'consumable',
                    'name':   name,
                    'amount': p.get('heal_amount', p.get('shield_amount')),
                    'pos':    (x, y)
                })
        return items