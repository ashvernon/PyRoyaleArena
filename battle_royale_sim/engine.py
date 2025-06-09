import pygame
import random
import yaml
import os
import math
from .constants            import TICK_RATE
from .world                import World
from .storm                import Storm
from .items.loot_spawner   import LootSpawner
from .agent.agent          import Agent
from .telemetry            import flush, log_event

class GameEngine:
    def __init__(self):
        # — Load configs —
        map_cfg        = yaml.safe_load(open('config/map.yaml'))
        buildings_cfg  = yaml.safe_load(open('config/buildings.yaml'))
        storm_cfg      = yaml.safe_load(open('config/storm.yaml'))
        loot_cfg       = yaml.safe_load(open('config/loot_table.yaml'))
        agents_cfg     = yaml.safe_load(open('config/agents.yaml'))

        # merge buildings into world config
        map_cfg['buildings'] = buildings_cfg.get('buildings', [])

        # — Init subsystems —
        self.world    = World(map_cfg)
        self.storm    = Storm(storm_cfg['phases'], self.world)
        self.spawner  = LootSpawner(loot_cfg, self.world)

        # — Create agents —
        self.agents = []
        for i in range(agents_cfg['count']):
            s = random.uniform(*agents_cfg['skill_range'])
            l = random.uniform(*agents_cfg['luck_range'])
            self.agents.append(Agent(i, s, l, self.world, self.storm))

        # — State holders —
        self.loot_items   = []
        self.shots        = []   # [(start_pos, end_pos), ...]
        self.total_agents = len(self.agents)
        self.loot_items   = self.spawner.spawn_initial_loot()

        # — Pygame setup —
        pygame.init()
        pygame.font.init()
        self.font   = pygame.font.SysFont(None, 24)
        self.id_font = pygame.font.SysFont(None, 14)   # smaller size for IDs
        self.screen = pygame.display.set_mode(
            (int(self.world.width), int(self.world.height))
        )
        # load grass tile
        base_dir = os.path.dirname(__file__)
        asset_p = os.path.join(base_dir, "assets", "pygrass_tile.png")
        self.grass_tex = pygame.image.load(asset_p).convert()

        # load floor tile 
        floor_asset_p = os.path.join(base_dir, "assets", "wood_floor_tile_dark_32.png")
        self.floor_tex = pygame.image.load(floor_asset_p).convert()

        pygame.display.set_caption("Battle Royale Simulation")
        self.clock = pygame.time.Clock()

    def run(self):
        running = True
        while running and len(self.agents) > 1:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False

            self.update()
            self.render()
            self.clock.tick(TICK_RATE)

        flush()
        pygame.quit()

    def update(self):
        # 1) Storm
        self.storm.update()

        # 2) Spawn loot occasionally, but only inside the safe zone
        if random.random() < 0.05:
            new_loot = self.spawner.spawn_loot()
            inside = [
                it for it in new_loot
                if self.storm.in_safe_zone(it['pos'])
            ]
            self.loot_items.extend(inside)

        # 3) Agent actions: decide, move/attack, pickup, storm damage & elimination
        for a in self.agents[:]:
            # tick now accepts both agents list and loot_items
            a.tick(self.agents, self.loot_items)
            if a.health <= 0:
                log_event('eliminate', {'agent': a.id})
                self.agents.remove(a)

        # 4) Combat: collect shot visuals
        self.shots = []
        for a in self.agents:
            shot = a.attack(self.agents)
            if shot:
                self.shots.append(shot)

        # 5) Post-combat elimination (in case attack killed someone)
        for a in self.agents[:]:
            if a.health <= 0:
                log_event('eliminate', {'agent': a.id})
                self.agents.remove(a)

    def render(self):
        # 1) Textured grass background (tile the grass texture)

        tex = self.grass_tex
        tw, th = tex.get_width(), tex.get_height()
        # optional: make a bit transparent
        tex.set_alpha(200)

        for x in range(0, int(self.world.width), tw):
            for y in range(0, int(self.world.height), th):
                self.screen.blit(tex, (x, y))

        # 2) Draw organic ponds
        for poly in self.world.ponds:
            pygame.draw.polygon(self.screen, (65,105,225), poly)



        # 2) Draw detailed buildings: shadows, two-tone walls, doors, textured floor in building interiors
        for b in self.world.buildings:
            # Compute bounds of the exterior rectangle from outer wall segments only
            xs = [w['x'] for w in b.get('walls',[])]
            ws = [w['width'] for w in b.get('walls',[])]
            ys = [w['y'] for w in b.get('walls',[])]
            hs = [w['height'] for w in b.get('walls',[])]
            minx = min(xs)
            maxx = max(x0 + w0 for x0, w0 in zip(xs, ws))
            miny = min(ys)
            maxy = max(y0 + h0 for y0, h0 in zip(ys, hs))


            fw, fh = self.floor_tex.get_width(), self.floor_tex.get_height()
            for fx in range(minx, maxx, fw):
                for fy in range(miny, maxy, fh):
                    # Calculate width and height to draw (crop if at the edge)
                    draw_w = min(fw, maxx - fx)
                    draw_h = min(fh, maxy - fy)
                    if draw_w < fw or draw_h < fh:
                        # Crop the texture for the edge
                        sub = self.floor_tex.subsurface((0, 0, draw_w, draw_h))
                        self.screen.blit(sub, (fx, fy))
                    else:
                        self.screen.blit(self.floor_tex, (fx, fy))




            
            # outer walls
            for w in b.get('walls', []):
                x, y, wdt, hgt = w['x'], w['y'], w['width'], w['height']

                # Draw drop shadow (soft, slightly offset, semi-transparent)
                shadow = pygame.Surface((wdt+6, hgt+6), pygame.SRCALPHA)
                pygame.draw.rect(shadow, (0,0,0,60), (0,0,wdt+6,hgt+6), border_radius=4)
                self.screen.blit(shadow, (x-3, y-3))

                # Outer dark edge
                pygame.draw.rect(self.screen, (70, 70, 70), (x, y, wdt, hgt))
                # Slightly inset, lighter inner face
                pad = 2
                pygame.draw.rect(self.screen, (180, 180, 180), (x+pad, y+pad, wdt-2*pad, hgt-2*pad))

            # doors (brown vertical gradient)
            for d in b.get('doors', []):
                x, y, wdt, hgt = d['x'], d['y'], d['width'], d['height']
                for i in range(hgt):
                    color = (
                        120 + int(40 * i/hgt),  # redder at bottom
                        80 + int(30 * i/hgt),   # greener at bottom
                        40                      # low blue, brown
                    )
                    pygame.draw.line(self.screen, color, (x, y+i), (x+wdt, y+i))

            # interior walls (simple medium gray)
            for i in b.get('interiors', []):
                pygame.draw.rect(self.screen, (160, 160, 160),
                                 (i['x'], i['y'], i['width'], i['height']))


        # 3) Players remaining counter
        remaining = len(self.agents)
        counter_surf = self.font.render(
            f"{remaining} / {self.total_agents}",
            True,
            (255, 255, 255)
        )
        self.screen.blit(counter_surf, (10, 10))

        # 4) Storm-cycle timer
        phase        = self.storm.phases[self.storm.current_phase]
        ticks        = self.storm.ticks_in_phase
        hold_ticks   = phase['hold']   * TICK_RATE
        shrink_ticks = phase['shrink'] * TICK_RATE

        if ticks <= hold_ticks:
            # still holding radius
            secs_left = (hold_ticks - ticks) // TICK_RATE
            label     = f"Holding: {secs_left}s"
        else:
            # currently shrinking
            elapsed_shrink = ticks - hold_ticks
            if elapsed_shrink <= shrink_ticks:
                secs_left = (shrink_ticks - elapsed_shrink) // TICK_RATE
            else:
                secs_left = 0
            label = f"Shrinking: {secs_left}s"

        timer_surf = self.font.render(label, True, (255, 255, 255))
        self.screen.blit(timer_surf, (10, 30))


        # 5) Loot items
        for item in self.loot_items:
            col = (255, 215, 0) if item['type'] == 'weapon' else (0, 255, 255)
            x, y = item['pos']
            pygame.draw.rect(self.screen, col, (int(x-3), int(y-3), 6, 6))

        # 6) Agents + health bars + ID
        for a in self.agents:
            x, y = a.pos
            # Agent circle

            pygame.draw.circle(
                self.screen,
                (0, 0, 255),
                (int(x), int(y)),
                5
            )

            # ID above agent (using smaller font)
            id_surf = self.id_font.render(str(a.id), True, (255, 255, 0))
            self.screen.blit(id_surf, (int(x - 5), int(y - 20)))

            # Health bar (red bg + green fg)
            hb_width = int((a.health / 100) * 10)
            pygame.draw.rect(
                self.screen,
                (255, 0, 0),
                (int(x - 5), int(y - 12), 10, 2)
            )
            pygame.draw.rect(
                self.screen,
                (0, 255, 0),
                (int(x - 5), int(y - 12), hb_width, 2)
            )
            # 7) Storm circle
            cx, cy = self.world.center
            pygame.draw.circle(
                self.screen,
                (0, 0, 0),
                (int(cx), int(cy)),
                int(self.storm.radius),
                2
            )

        # 8) Shot visuals
        for start, end in self.shots:
            pygame.draw.line(
                self.screen,
                (255, 0, 0),
                (int(start[0]), int(start[1])),
                (int(end[0]), int(end[1])),
                1
            )

        # 9) UI Legend
        legend_items = [
            ("Weapon",     (255, 215,   0), "rect"),
            ("Consumable", (  0, 255, 255), "rect"),
            ("Building",   (100, 100, 100), "rect"),
            ("Agent",      (  0,   0, 255), "circle"),
        ]
        lx, ly = 10, 50
        for label, color, shape in legend_items:
            if shape == "rect":
                pygame.draw.rect(self.screen, color, (lx, ly, 12, 12))
            else:
                pygame.draw.circle(self.screen, color, (lx + 6, ly + 6), 6)
            text_surf = self.font.render(label, True, (255, 255, 255))
            self.screen.blit(text_surf, (lx + 18, ly))
            ly += 18

        # 10) Flip display
        pygame.display.flip()
