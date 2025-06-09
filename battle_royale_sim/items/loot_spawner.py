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
