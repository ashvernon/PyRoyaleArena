import pygame
import random
import yaml
import os
import math
from .constants          import TICK_RATE
from .world              import World
from .storm              import Storm
from .items.loot_spawner import LootSpawner
from .agent.agent        import Agent
from .telemetry          import flush, log_event

class GameEngine:
    def __init__(self):
        # — Load configs —
        map_cfg       = yaml.safe_load(open('config/map.yaml'))
        buildings_cfg = yaml.safe_load(open('config/buildings.yaml'))
        storm_cfg     = yaml.safe_load(open('config/storm.yaml'))
        loot_cfg      = yaml.safe_load(open('config/loot_table.yaml'))
        agents_cfg    = yaml.safe_load(open('config/agents.yaml'))

        map_cfg['buildings'] = buildings_cfg.get('buildings', [])

        # — Init subsystems —
        self.world   = World(map_cfg)
        self.storm   = Storm(storm_cfg['phases'], self.world)
        self.spawner = LootSpawner(loot_cfg, self.world)

        # — Create agents —
        self.agents = []
        self.selected_agent = None
        for i in range(agents_cfg['count']):
            s = random.uniform(*agents_cfg['skill_range'])
            l = random.uniform(*agents_cfg['luck_range'])
            color = pygame.Color(0)
            color.hsva = (int(360 * i / agents_cfg['count']), 90, 90, 100)
            self.agents.append(Agent(i, s, l, self.world, self.storm, (color.r, color.g, color.b)))

        # — State holders —
        self.loot_items   = self.spawner.spawn_initial_loot()
        self.shots        = []
        self.total_agents = len(self.agents)

        # — Pygame setup —
        pygame.init()
        pygame.font.init()
        self.font    = pygame.font.SysFont(None, 24)
        self.id_font = pygame.font.SysFont(None, 14)

        # screen shows the viewport
        self.screen = pygame.display.set_mode(
            (int(self.world.width), int(self.world.height))
        )

        # world_surf holds the entire 2km×2km world (in world pixels)
        self.world_surf = pygame.Surface(
            (int(self.world.width), int(self.world.height))
        )

        # camera for pan & zoom
        self.cam_offset = [0, 0]
        self.zoom       = 1.0
        self.dragging   = False
        self.last_mouse = (0, 0)

        # load tiles & sprites
        base_dir        = os.path.dirname(__file__)
        self.grass_tex  = pygame.image.load(os.path.join(base_dir, "assets", "pygrass_tile.png")).convert()
        self.floor_tex  = pygame.image.load(os.path.join(base_dir, "assets", "wood_floor_tile_dark_32.png")).convert()
        self.agent_sprite = pygame.image.load(os.path.join(base_dir, "assets", "agent_sprite.png")).convert_alpha()

        # overlay for storm shading (reused each frame)
        self.overlay = pygame.Surface(
            (int(self.world.width), int(self.world.height)),
            pygame.SRCALPHA
        )

        # scatterable assets (trees, rocks, grass)
        def load_all(subdir):
            path = os.path.join(base_dir, "assets", subdir)
            return [pygame.image.load(os.path.join(path, f)).convert_alpha()
                    for f in os.listdir(path) if f.endswith(".png")]

        self.tree_textures  = load_all("trees")
        self.rock_textures  = load_all("rocks")
        self.grass_textures = load_all("grass")

        # counts from config
        tree_count  = map_cfg.get("tree_count", 50)
        rock_count  = map_cfg.get("rock_count", 30)
        grass_count = map_cfg.get("grass_count",100)

        self.tree_positions  = [self.world.random_pos() for _ in range(tree_count)]
        self.rock_positions  = [self.world.random_pos() for _ in range(rock_count)]
        self.grass_positions = [self.world.random_pos() for _ in range(grass_count)]

        self.world.trees = self.tree_positions
        self.world.rocks = self.rock_positions

        pygame.display.set_caption("Battle Royale Simulation")
        self.clock = pygame.time.Clock()

    def run(self):
        running = True
        while running and len(self.agents) > 1:
            for e in pygame.event.get():
                # Quit
                if e.type == pygame.QUIT:
                    running = False

                # Mouse button pressed
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    # Left click → select agent
                    if e.button == 1:
                        sx, sy = e.pos
                        # Map screen coords → world coords
                        wx = self.cam_offset[0] + sx / self.zoom
                        wy = self.cam_offset[1] + sy / self.zoom

                        # Click radius of 10px on screen ⇒ world radius
                        r_world = 10 / self.zoom
                        rr2 = r_world * r_world

                        self.selected_agent = None
                        for agent in self.agents:
                            dx = agent.pos[0] - wx
                            dy = agent.pos[1] - wy
                            if dx*dx + dy*dy <= rr2:
                                self.selected_agent = agent
                                break

                    # Middle click → start panning
                    elif e.button == 2:
                        self.dragging   = True
                        self.last_mouse = e.pos

                    # Wheel up → zoom in
                    elif e.button == 4:
                        self.zoom = min(self.zoom * 1.1, 5.0)
                    # Wheel down → zoom out
                    elif e.button == 5:
                        self.zoom = max(self.zoom / 1.1, 0.2)

                # Mouse button released
                elif e.type == pygame.MOUSEBUTTONUP and e.button == 2:
                    self.dragging = False

                # Mouse moved while panning
                elif e.type == pygame.MOUSEMOTION and self.dragging:
                    dx, dy = e.pos[0] - self.last_mouse[0], e.pos[1] - self.last_mouse[1]
                    self.cam_offset[0] -= dx / self.zoom
                    self.cam_offset[1] -= dy / self.zoom
                    self.last_mouse = e.pos

            # Update & render loop
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
        # 0) Draw entire world into world_surf
        ws = self.world_surf
        ws.fill((0, 0, 0))

        # 1) Grass background
        tw, th = self.grass_tex.get_width(), self.grass_tex.get_height()
        for x in range(0, int(self.world.width), tw):
            for y in range(0, int(self.world.height), th):
                ws.blit(self.grass_tex, (x, y))

        # 2) Ponds
        for poly in self.world.ponds:
            pygame.draw.polygon(ws, (65, 105, 225), poly)

        # 3) Scatter grass, rocks, trees
        for gx, gy in self.grass_positions:
            g = random.choice(self.grass_textures)
            ws.blit(g, (gx - g.get_width()//2, gy - g.get_height()//2))
        for rx, ry in self.rock_positions:
            r = random.choice(self.rock_textures)
            ws.blit(r, (rx - r.get_width()//2, ry - r.get_height()//2))
        for tx, ty in self.tree_positions:
            t = random.choice(self.tree_textures)
            ws.blit(t, (tx - t.get_width()//2, ty - t.get_height()//2))

        # 4) Buildings (floors + walls + doors + interiors)
        for b in self.world.buildings:
            # floor tiling
            xs     = [seg['x']      for seg in b.get('walls', [])]
            wsizes = [seg['width']  for seg in b.get('walls', [])]
            ys     = [seg['y']      for seg in b.get('walls', [])]
            hsizes = [seg['height'] for seg in b.get('walls', [])]
            minx, maxx = min(xs), max(x0 + w0 for x0, w0 in zip(xs, wsizes))
            miny, maxy = min(ys), max(y0 + h0 for y0, h0 in zip(ys, hsizes))

            fw, fh = self.floor_tex.get_width(), self.floor_tex.get_height()
            for fx in range(minx, maxx, fw):
                for fy in range(miny, maxy, fh):
                    dw, dh = min(fw, maxx-fx), min(fh, maxy-fy)
                    if dw<fw or dh<fh:
                        sub = self.floor_tex.subsurface((0, 0, dw, dh))
                        ws.blit(sub, (fx, fy))
                    else:
                        ws.blit(self.floor_tex, (fx, fy))

            # outer walls
            for seg in b.get('walls', []):
                x, y, wdt, hgt = seg['x'], seg['y'], seg['width'], seg['height']
                shadow = pygame.Surface((wdt+6, hgt+6), pygame.SRCALPHA)
                pygame.draw.rect(shadow, (0,0,0,60), (0,0,wdt+6,hgt+6), border_radius=4)
                ws.blit(shadow, (x-3, y-3))
                pygame.draw.rect(ws, (70,70,70), (x, y, wdt, hgt))
                pad = 2
                pygame.draw.rect(ws, (180,180,180), (x+pad, y+pad, wdt-2*pad, hgt-2*pad))

            # doors
            for d in b.get('doors', []):
                x, y, wdt, hgt = d['x'], d['y'], d['width'], d['height']
                for i in range(hgt):
                    col = (
                        120 + int(40*i/hgt),
                        80  + int(30*i/hgt),
                        40
                    )
                    pygame.draw.line(ws, col, (x, y+i), (x+wdt, y+i))

            # interiors
            for interior in b.get('interiors', []):
                pygame.draw.rect(ws, (160,160,160),
                                 (interior['x'], interior['y'],
                                  interior['width'], interior['height']))

        # 5) Loot items
        for item in self.loot_items:
            col = (255,215,0) if item['type']=='weapon' else (0,255,255)
            x, y = item['pos']
            pygame.draw.rect(ws, col, (int(x-3), int(y-3), 6, 6))

        # 6) Agents + health bars
        for a in self.agents:
            x, y = a.pos
            # tinted sprite
            sprite = self.agent_sprite.copy()
            tint   = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
            tint.fill((*a.color, 255))
            sprite.blit(tint, (0,0), special_flags=pygame.BLEND_RGBA_MULT)
            ws.blit(sprite, (int(x - sprite.get_width()/2),
                             int(y - sprite.get_height()/2)))          


            # health bar
            hb = int((a.health/100)*10)
            pygame.draw.rect(ws, (255,0,0), (int(x-5), int(y-20), 10, 2))
            pygame.draw.rect(ws, (0,255,0), (int(x-5), int(y-20), hb, 2))

        # 7) Shot visuals
        for start, end in self.shots:
            pygame.draw.line(ws, (255,0,0),
                             (int(start[0]), int(start[1])),
                             (int(end[0]),   int(end[1])),
                             1)       


        # — VIEWPORT CROPPING & ZOOM BLIT —
        sw, sh = self.screen.get_size()
        view_w = min(sw/self.zoom,  self.world.width)
        view_h = min(sh/self.zoom,  self.world.height)
        max_x  = self.world.width  - view_w
        max_y  = self.world.height - view_h
        vx     = max(0, min(self.cam_offset[0], max_x))
        vy     = max(0, min(self.cam_offset[1], max_y))
        vp     = pygame.Rect(int(vx), int(vy), int(view_w), int(view_h))
        sub    = ws.subsurface(vp)
        scaled = pygame.transform.smoothscale(sub, (sw, sh))
        self.screen.blit(scaled, (0, 0))

        fps = int(self.clock.get_fps())
        self.screen.blit(self.font.render(f"FPS: {fps}", True, (255,255,0)), (sw-60, 10))

        # Zoom Level
        self.screen.blit(self.font.render(f"Zoom: {self.zoom:.2f}×", True, (255,255,255)), (sw-100, 30))


        # 8) Players remaining counter
        remaining = len(self.agents)
        cnt_surf = self.font.render(f"{remaining} / {self.total_agents}", True, (255,255,255))
        self.screen.blit(cnt_surf, (10,10))

        # 9) Storm-cycle timer
        phase      = self.storm.phases[self.storm.current_phase]
        ticks      = self.storm.ticks_in_phase
        hold_t, shr = phase['hold']*TICK_RATE, phase['shrink']*TICK_RATE
        if ticks<=hold_t:
            lbl = f"Holding: {(hold_t-ticks)//TICK_RATE}s"
        else:
            secs = max(0, (shr-(ticks-hold_t))//TICK_RATE)
            lbl  = f"Shrinking: {secs}s"
        timer_surf = self.font.render(lbl, True, (255,255,255))
        self.screen.blit(timer_surf, (10,30))

        # 10) Storm overlay
        cxw, cyw = self.world.center
        sx = int((cxw - vx)*self.zoom)
        sy = int((cyw - vy)*self.zoom)
        sr = int(self.storm.radius * self.zoom)
        self.overlay.fill((50,50,50,150))
        pygame.draw.circle(self.overlay, (0,0,0,0), (sx,sy), sr)
        self.screen.blit(self.overlay, (0,0))
        pygame.draw.circle(self.screen, (255,255,255), (sx,sy), sr, 2)


        # — Agent inspector —
        if self.selected_agent:
            agent = self.selected_agent
            # background panel
            pygame.draw.rect(self.screen, (30, 30, 30), (20, 120, 270, 260))
            pygame.draw.rect(self.screen, (200, 200, 50), (20, 120, 270, 260), 2)

            font = self.font
            lines = [
                f"Agent #{agent.id}",                                            # identifier
                f"Position: ({int(agent.pos[0])}, {int(agent.pos[1])})",         # where they are
                f"Health: {int(agent.health)}   Shield: {int(agent.shield)}",    # survivability
                f"Skill: {agent.skill:.2f}   Luck: {agent.luck:.2f}",             # their stats
                f"Kills: {agent.kills}",                                         # fight performance
                f"Accuracy: {agent.shots_hit}/{agent.shots_fired} "              # shot stats
                f"({(agent.shots_hit/agent.shots_fired*100) if agent.shots_fired else 0.0:.1f}%)",
                f"Last Strategy: {agent.last_decision}",                          # AI decisions
                f"Current Strategy: {agent.current_action}",
                "Inventory:"                                                     # inventory header
            ]

            # Weapons
            if agent.inventory.weapons:
                weapon_names = ", ".join(w.name for w in agent.inventory.weapons)
            else:
                weapon_names = "(none)"
            lines.append(f"  Weapons: {weapon_names}")

            # Consumables (show each name(+amount))
            if agent.inventory.consumables:
                consumable_list = ", ".join(
                    f"{c['name']}(+{c['amount']})"
                    for c in agent.inventory.consumables
                )
            else:
                consumable_list = "(none)"
            lines.append(f"  Consumables: {consumable_list}")

            # render each line
            for i, text in enumerate(lines):
                surf = font.render(text, True, (255, 255, 255))
                self.screen.blit(surf, (28, 128 + i*18))

            # highlight the selected agent on map
            screen_x = int((agent.pos[0] - vx) * self.zoom)
            screen_y = int((agent.pos[1] - vy) * self.zoom)
            pygame.draw.circle(
                self.screen,
                (255, 255, 0),
                (screen_x, screen_y),
                max(2, int(9 * self.zoom)),
                2
            )



        # 10) Flip display
        pygame.display.flip()
