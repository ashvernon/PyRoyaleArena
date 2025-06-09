class Inventory:
    def __init__(self):
        self.weapons     = []
        self.consumables = []
        self.materials   = {}

    def add(self, item):
        typ = item['type']
        if typ == 'weapon' and len(self.weapons) < 5:
            self.weapons.append(item['object'])

        elif typ == 'consumable':
            self.consumables.append(item)

        elif typ == 'material':
            name = item['name']
            self.materials[name] = self.materials.get(name, 0) + 1
