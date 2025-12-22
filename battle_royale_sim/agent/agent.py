import math
import random
from ..utils import distance
from .behavior import Behavior
from ..inventory import Inventory
from ..telemetry import log_event
from ..constants import TICK_RATE

class Agent:
    def __init__(self, idx, skill, luck, world, storm, color, behavior_config=None):
        self.id             = idx
        self.health         = 100
        self.shield         = 50
        self.skill          = skill
        self.luck           = luck
        self.pos            = world.random_pos()
        self.world          = world
        self.storm          = storm
        self.inventory      = Inventory()
        self.cooldown_ticks = 0
        self.color = color
        self.current_action = None
        self.last_decision  = None
        self.kills          = 0
        self.vel            = (0.0, 0.0)
        self.heading        = 0.0
        self.desired_heading = 0.0
        self.last_heading_update_tick = -math.inf
        self.move_mode      = 'walk'
        self.tick_counter   = 0
        self.locomotion_cfg = {
            'walk_speed': 1.0,
            'jog_speed': 1.6,
            'sprint_speed': 2.4,
            'max_accel': 0.25,
            'max_decel': 0.4,
            'max_turn_deg_per_tick': 12,
            'turn_at_sprint_factor': 0.35,
            'reaction_ticks': 3,
            'arrival_radius': 2.5,
            'stop_radius': 0.6,
            'personal_space_radius': 12.0,
            'separation_strength': 0.6,
            'wall_avoidance_strength': 0.8,
            'avoidance_probe_distance': 8.0,
        }
        self.behavior       = Behavior(self, world, storm, behavior_config)

    def tick(self, agents, loot_items):
        """Update agent state for a single tick.

        Returns the visual representation of a shot if one was fired.
        """
        self.tick_counter += 1

        # 0) Decide next action
        decision, target = self.behavior.select_action(agents, loot_items)
        self.last_decision = decision

        shot = None

        # 1) Execute: either attack or move, and record what actually happened
        if decision == 'attack':
            shot = self.attack(agents)
            # if shot is None, we couldn’t fire (cooldown, no weapon, blocked…), so idle
            self.current_action = 'attack' if shot else 'idle'
        else:
            self._move_towards(target, agents, decision)
            self.current_action = 'move'

        # 2) Loot pickup
        for item in loot_items[:]:
            if distance(self.pos, item['pos']) < 10:
                self.inventory.add(item)
                loot_items.remove(item)
                log_event('pickup', {'agent': self.id, 'item': item['type']})

        # 3) Storm damage
        if not self.storm.in_safe_zone(self.pos):
            dmg = self.storm.damage()
            self.health -= dmg
            log_event('storm_damage', {'agent': self.id, 'damage': dmg})

        return shot


    def attack(self, agents):
        if self.cooldown_ticks > 0:
            self.cooldown_ticks -= 1
            return None

        if not self.inventory.weapons:
            return None

        weapon  = self.inventory.weapons[0]
        enemies = [a for a in agents if a.id != self.id and a.health > 0]
        if not enemies:
            return None

        target = min(enemies, key=lambda a: distance(self.pos, a.pos))

        # block shots through walls
        if not self.world.has_line_of_sight(self.pos, target.pos):
            return None

        # out of range?
        if distance(self.pos, target.pos) > weapon.range:
            return None

        hit_chance = weapon.accuracy * self.skill
        if random.random() <= hit_chance:
            dmg = weapon.damage

            # shields absorb first
            if target.shield > 0:
                blocked = min(target.shield, dmg)
                target.shield -= blocked
                dmg -= blocked

            # leftover goes to health
            if dmg > 0:
                target.health -= dmg

                # —— NEW: count a kill if they dropped to 0 or below —— 
                if target.health <= 0:
                    self.kills += 1
                    log_event('kill', {
                        'killer': self.id,
                        'victim': target.id
                    })

            log_event('hit', {
                'shooter': self.id,
                'target':  target.id,
                'damage':  weapon.damage
            })
        else:
            log_event('miss', {
                'shooter': self.id,
                'target':  target.id
            })

        # reset cooldown
        self.cooldown_ticks = max(1, int(TICK_RATE / weapon.fire_rate))
        return (self.pos, target.pos)



    def _move_towards(self, target, agents, action):
        cfg = self.locomotion_cfg
        dt = 1.0  # implicit tick duration; keep explicit for tuning

        to_target = (target[0] - self.pos[0], target[1] - self.pos[1])
        dist = distance(self.pos, target)

        if dist <= cfg['stop_radius']:
            self.vel = (0.0, 0.0)
            return

        nearest_enemy_dist = self._nearest_enemy_distance(agents)
        self.move_mode = self._choose_move_mode(action, nearest_enemy_dist)

        desired_dir = self._normalize(to_target)
        separation = self._separation_vector(agents)
        wall_avoid = self._wall_avoidance_vector(cfg['avoidance_probe_distance'])
        avoid = self._vec_add(
            self._vec_mul(separation, cfg['separation_strength']),
            self._vec_mul(wall_avoid, cfg['wall_avoidance_strength'])
        )
        if self._vec_length(avoid) > 0:
            desired_dir = self._normalize(self._vec_add(desired_dir, avoid))
        if self._vec_length(desired_dir) == 0:
            desired_dir = (math.cos(self.heading), math.sin(self.heading))

        target_heading = math.atan2(desired_dir[1], desired_dir[0])
        if (self.tick_counter - self.last_heading_update_tick) >= cfg['reaction_ticks']:
            self.desired_heading = target_heading
            self.last_heading_update_tick = self.tick_counter

        base_turn = math.radians(cfg['max_turn_deg_per_tick']) * dt
        current_speed = self._vec_length(self.vel)
        speed_norm = self._clamp(current_speed / cfg['sprint_speed'], 0.0, 1.0)
        turn_limit = base_turn * self._lerp(1.0, cfg['turn_at_sprint_factor'], speed_norm)
        self.heading = self._rotate_towards(self.heading, self.desired_heading, turn_limit)

        base_speed = self._speed_for_mode(self.move_mode)
        if self.world.is_in_water(self.pos):
            base_speed *= 0.75

        if dist < cfg['arrival_radius']:
            slowdown = self._clamp(dist / cfg['arrival_radius'], 0.15, 1.0)
            speed_cap = base_speed * slowdown
        else:
            speed_cap = base_speed

        desired_vel = (
            math.cos(self.heading) * speed_cap,
            math.sin(self.heading) * speed_cap
        )
        desired_speed = self._vec_length(desired_vel)

        accel_limit = cfg['max_accel'] * dt if desired_speed > current_speed else cfg['max_decel'] * dt
        delta_v = self._vec_sub(desired_vel, self.vel)
        delta_v = self._clamp_vec_length(delta_v, accel_limit)
        self.vel = self._vec_add(self.vel, delta_v)

        if self._vec_length(self.vel) > speed_cap:
            self.vel = self._vec_mul(self._normalize(self.vel), speed_cap)

        proposed_pos = self._vec_add(self.pos, self._vec_mul(self.vel, dt))
        if self.world.in_wall(proposed_pos):
            self.vel = (0.0, 0.0)
            return

        self.pos = proposed_pos

        if distance(self.pos, target) <= cfg['stop_radius']:
            self.vel = (0.0, 0.0)

    def _speed_for_mode(self, mode):
        if mode == 'sprint':
            return self.locomotion_cfg['sprint_speed']
        if mode == 'jog':
            return self.locomotion_cfg['jog_speed']
        return self.locomotion_cfg['walk_speed']

    def _choose_move_mode(self, action, nearest_enemy_dist):
        if action == 'flee' or self.health < 30:
            return 'sprint'
        if action == 'boundary':
            return 'jog'
        if action == 'loot':
            return 'jog' if nearest_enemy_dist < 35 else 'walk'
        if action in ('hide', 'ambush', 'roam'):
            return 'walk'
        if nearest_enemy_dist < 25:
            return 'jog'
        return 'walk'

    def _nearest_enemy_distance(self, agents):
        return min(
            (distance(self.pos, other.pos) for other in agents if other.id != self.id and other.health > 0),
            default=math.inf
        )

    def _separation_vector(self, agents):
        radius = self.locomotion_cfg['personal_space_radius']
        if radius <= 0:
            return (0.0, 0.0)

        steer = (0.0, 0.0)
        for other in agents:
            if other.id == self.id or other.health <= 0:
                continue
            offset = (self.pos[0] - other.pos[0], self.pos[1] - other.pos[1])
            dist = self._vec_length(offset)
            if dist <= 1e-5 or dist >= radius:
                continue
            weight = (radius - dist) / radius
            steer = self._vec_add(steer, self._vec_mul(self._normalize(offset), weight))
        return steer

    def _wall_avoidance_vector(self, probe_distance):
        angles = [0.0, math.pi / 6, -math.pi / 6]
        steer = (0.0, 0.0)
        for offset in angles:
            ang = self.heading + offset
            probe = (
                self.pos[0] + math.cos(ang) * probe_distance,
                self.pos[1] + math.sin(ang) * probe_distance
            )
            if self.world.in_wall(probe):
                steer = self._vec_add(steer, (-math.cos(ang), -math.sin(ang)))
        return steer

    def _vec_add(self, a, b):
        return (a[0] + b[0], a[1] + b[1])

    def _vec_sub(self, a, b):
        return (a[0] - b[0], a[1] - b[1])

    def _vec_mul(self, v, s):
        return (v[0] * s, v[1] * s)

    def _vec_length(self, v):
        return math.hypot(v[0], v[1])

    def _normalize(self, v):
        l = self._vec_length(v)
        if l <= 1e-6:
            return (0.0, 0.0)
        return (v[0] / l, v[1] / l)

    def _clamp_vec_length(self, v, max_len):
        l = self._vec_length(v)
        if l <= max_len or l == 0:
            return v
        scale = max_len / l
        return (v[0] * scale, v[1] * scale)

    def _rotate_towards(self, current, target, max_delta):
        delta = self._wrap_angle(target - current)
        delta = self._clamp(delta, -max_delta, max_delta)
        return self._wrap_angle(current + delta)

    def _wrap_angle(self, angle):
        return (angle + math.pi) % (2 * math.pi) - math.pi

    def _clamp(self, value, min_value, max_value):
        return max(min_value, min(max_value, value))

    def _lerp(self, a, b, t):
        return a + (b - a) * t
