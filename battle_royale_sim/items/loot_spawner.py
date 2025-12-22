import random
from .weapon import Weapon

# Note: This file intentionally only depends on World’s existing public API:
# - random_pos(), in_wall(), in_building(), width/height, buildings
# - optionally is_in_water() (guarded with hasattr)


class LootSpawner:
    def __init__(self, cfg, world):
        self.world = world
        self.weapons_cfg = cfg.get('weapons', {})
        self.consumables_cfg = cfg.get('consumables', {})
        self.materials_cfg = cfg.get('materials', {})

        # Tunables (kept internal so no other files change)
        self._spawn_loot_min_items = 0          # per spawn_loot() call
        self._spawn_loot_max_items = 2          # keep small; engine may call often
        self._category_weights = {
            'weapon': 0.55,
            'consumable': 0.30,
            'material': 0.15,
        }

        # Placement
        self._max_place_tries = 25
        self._building_padding = 8

    # ----------------------------
    # Public API
    # ----------------------------
    def spawn_loot(self):
        """
        Dynamic trickle: returns a small list of loot items.
        Count-based (not "roll once per type"), so it scales sensibly regardless of how many types exist.
        """
        items = []
        n = random.randint(self._spawn_loot_min_items, self._spawn_loot_max_items)
        for _ in range(n):
            cat = self._weighted_category_choice()
            item = self._spawn_one_anywhere(category=cat, avoid_buildings=True)
            if item:
                items.append(item)
        return items

    def spawn_initial_loot(self):
        """
        Initial map population:
          1) In-building loot: 2–3 per building (favor consumables)
          2) Outdoor loot: scaled by building count (kept as existing behavior), weapons-heavy
        """
        items = []

        # 1) In-building loot: 2–3 per building (favor consumables/health)
        for b in self.world.buildings:
            bbox = self._building_bbox(b)
            if bbox is None:
                continue
            minx, miny, maxx, maxy = bbox

            drops = random.randint(2, 3)
            for _ in range(drops):
                pos = self._random_point_in_bbox(
                    minx, miny, maxx, maxy,
                    padding=self._building_padding,
                    require_valid=True,
                    avoid_buildings=False,  # we WANT inside the building bbox
                )
                if not pos:
                    continue

                # 70% consumable, 30% weapon
                loot_type = random.choices(['consumable', 'weapon'], weights=[0.7, 0.3], k=1)[0]
                if loot_type == 'weapon':
                    item = self._make_weapon_item_at(pos)
                else:
                    item = self._make_consumable_item_at(pos)

                if item:
                    items.append(item)

        # 2) Outdoor loot: more weapons, scattered anywhere NOT in a building
        # Keep your existing scaling, but harden placement and avoid water.
        num_outdoor_loot = int(len(self.world.buildings) * 5)
        for _ in range(num_outdoor_loot):
            pos = self._random_outdoor_pos()
            if not pos:
                continue

            # 80% weapons, 20% consumable
            loot_type = random.choices(['weapon', 'consumable'], weights=[0.8, 0.2], k=1)[0]
            if loot_type == 'weapon':
                item = self._make_weapon_item_at(pos)
            else:
                item = self._make_consumable_item_at(pos)

            if item:
                items.append(item)

        return items

    # ----------------------------
    # Internal: item creation
    # ----------------------------
    def _make_weapon_item_at(self, pos):
        name, p = self._weighted_choice(self.weapons_cfg)
        if not name:
            return None
        w = Weapon(
            name,
            damage=p['damage'],
            fire_rate=p['fire_rate'],
            accuracy=p['accuracy'],
            range=p['range'],
            magazine_size=p.get('magazine_size', 0),
            reload_time=p.get('reload_time', 0.0),
        )
        return {'type': 'weapon', 'object': w, 'pos': pos}

    def _make_consumable_item_at(self, pos):
        name, p = self._weighted_choice(self.consumables_cfg)
        if not name:
            return None
        amount = p.get('heal_amount', p.get('shield_amount', 0))
        return {'type': 'consumable', 'name': name, 'amount': amount, 'pos': pos}

    def _make_material_item_at(self, pos):
        name, _p = self._weighted_choice(self.materials_cfg)
        if not name:
            return None
        return {'type': 'material', 'name': name, 'pos': pos}

    # ----------------------------
    # Internal: spawning helpers
    # ----------------------------
    def _spawn_one_anywhere(self, category, avoid_buildings=True):
        # pick a position first
        pos = self._random_pos_general(avoid_buildings=avoid_buildings)
        if not pos:
            return None

        if category == 'weapon':
            return self._make_weapon_item_at(pos)
        if category == 'consumable':
            return self._make_consumable_item_at(pos)
        if category == 'material':
            return self._make_material_item_at(pos)

        # fallback
        return self._make_material_item_at(pos)

    def _weighted_category_choice(self):
        cats = list(self._category_weights.keys())
        weights = [self._category_weights[c] for c in cats]
        return random.choices(cats, weights=weights, k=1)[0]

    def _weighted_choice(self, cfg_dict):
        """
        Choose a key from a config dict using spawn_chance as weights.
        Returns (name, cfg) or (None, None) if empty.
        """
        if not cfg_dict:
            return None, None
        names = list(cfg_dict.keys())
        weights = []
        for n in names:
            w = cfg_dict[n].get('spawn_chance', 0.0)
            weights.append(max(0.0, float(w)))
        if sum(weights) <= 0:
            # all zero weights -> uniform fallback
            name = random.choice(names)
            return name, cfg_dict[name]
        name = random.choices(names, weights=weights, k=1)[0]
        return name, cfg_dict[name]

    # ----------------------------
    # Internal: placement helpers
    # ----------------------------
    def _random_pos_general(self, avoid_buildings=True):
        """
        Uses world.random_pos() when possible (it already avoids walls/buildings/water in your World),
        but we still apply extra checks for consistency and safety.
        """
        for _ in range(self._max_place_tries):
            pos = self.world.random_pos()
            if self.world.in_wall(pos):
                continue
            if avoid_buildings and self.world.in_building(pos):
                continue
            if self._is_in_water(pos):
                continue
            return pos
        return None

    def _random_outdoor_pos(self):
        """
        Outdoor placement that avoids buildings, walls, and water.
        Uses raw coords to keep distribution uniform outdoors.
        """
        for _ in range(self._max_place_tries):
            x = random.uniform(0, self.world.width)
            y = random.uniform(0, self.world.height)
            pos = (x, y)
            if self.world.in_building(pos):
                continue
            if self.world.in_wall(pos):
                continue
            if self._is_in_water(pos):
                continue
            return pos
        return None

    def _random_point_in_bbox(self, minx, miny, maxx, maxy, padding=0, require_valid=True, avoid_buildings=False):
        """
        Try to pick a point in a bbox, optionally enforcing validity (not in wall, not in water).
        """
        # Clamp padding so we don’t invert bounds
        pad = max(0, float(padding))
        if (maxx - minx) <= pad * 2 or (maxy - miny) <= pad * 2:
            pad = 0

        for _ in range(self._max_place_tries):
            x = random.uniform(minx + pad, maxx - pad)
            y = random.uniform(miny + pad, maxy - pad)
            pos = (x, y)

            if not require_valid:
                return pos

            if self.world.in_wall(pos):
                continue
            if avoid_buildings and self.world.in_building(pos):
                continue
            if self._is_in_water(pos):
                continue
            return pos

        return None

    def _building_bbox(self, building):
        """
        Robust bbox from walls.
        Returns (minx, miny, maxx, maxy) or None if not computable.
        """
        walls = building.get('walls', [])
        if not walls:
            return None

        xs = [w.get('x', 0) for w in walls]
        ys = [w.get('y', 0) for w in walls]
        ws = [w.get('width', 0) for w in walls]
        hs = [w.get('height', 0) for w in walls]

        # guard against weird data
        if not xs or not ys:
            return None

        minx = min(xs)
        miny = min(ys)
        maxx = max(x0 + w0 for x0, w0 in zip(xs, ws))
        maxy = max(y0 + h0 for y0, h0 in zip(ys, hs))

        # sanity: ensure bbox has area
        if maxx <= minx or maxy <= miny:
            return None

        return (minx, miny, maxx, maxy)

    def _is_in_water(self, pos):
        # only call if the world supports water checks
        if hasattr(self.world, 'is_in_water'):
            try:
                return bool(self.world.is_in_water(pos))
            except Exception:
                return False
        return False
