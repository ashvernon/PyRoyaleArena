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
        # — Pygame setup —
        pygame.init()
        pygame.font.init()
        self.font    = pygame.font.SysFont(None, 24)
        self.id_font = pygame.font.SysFont(None, 14)

        # Create a tiny placeholder display so surface.convert/convert_alpha
        # calls succeed before we know the real window size.
        self.screen = pygame.display.set_mode((1, 1))

        self.sidebar_w = 360
        self.sidebar_pad = 10
        self.sidebar_row_h = 40
        self.sidebar_top_n = 25
        self.sidebar_header_h = 36

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

        # scatterable assets (trees, rocks, grass)
        def load_all(subdir):
            path = os.path.join(base_dir, "assets", subdir)
            return [pygame.image.load(os.path.join(path, f)).convert_alpha()
                    for f in os.listdir(path) if f.endswith(".png")]

        self.tree_textures  = load_all("trees")
        self.rock_textures  = load_all("rocks")
        self.grass_textures = load_all("grass")

        self.clock = pygame.time.Clock()
        pygame.display.set_caption("Battle Royale Simulation")

        self._start_match()

    def _load_configs(self):
        map_cfg       = yaml.safe_load(open('config/map.yaml'))
        buildings_cfg = yaml.safe_load(open('config/buildings.yaml'))
        storm_cfg     = yaml.safe_load(open('config/storm.yaml'))
        loot_cfg      = yaml.safe_load(open('config/loot_table.yaml'))
        agents_cfg    = yaml.safe_load(open('config/agents.yaml'))
        map_cfg['buildings'] = buildings_cfg.get('buildings', [])
        return map_cfg, storm_cfg, loot_cfg, agents_cfg

    def _start_match(self):
        map_cfg, storm_cfg, loot_cfg, agents_cfg = self._load_configs()

        # — Init subsystems —
        self.world   = World(map_cfg)
        self.storm   = Storm(storm_cfg['phases'], self.world)
        self.spawner = LootSpawner(loot_cfg, self.world)

        # screen shows the viewport
        self.world_w = int(self.world.width)
        self.world_h = int(self.world.height)
        self.screen = pygame.display.set_mode(
            (self.world_w + self.sidebar_w, self.world_h)
        )

        # world_surf holds the entire 2km×2km world (in world pixels)
        self.world_surf = pygame.Surface(
            (int(self.world.width), int(self.world.height))
        )

        # overlay for storm shading (reused each frame)
        self.overlay = pygame.Surface(
            (int(self.world.width), int(self.world.height)),
            pygame.SRCALPHA
        )

        # — Create agents —
        self.agents = []
        self.selected_agent = None
        behavior_cfg = {
            k: v for k, v in agents_cfg.items()
            if k.startswith("decision_") or k.startswith("waypoint_") or k in (
                "min_progress_per_tick", "stuck_ticks"
            )
        }
        for i in range(agents_cfg['count']):
            s = random.uniform(*agents_cfg['skill_range'])
            l = random.uniform(*agents_cfg['luck_range'])
            color = pygame.Color(0)
            color.hsva = (int(360 * i / agents_cfg['count']), 90, 90, 100)
            self.agents.append(Agent(
                i,
                s,
                l,
                self.world,
                self.storm,
                (color.r, color.g, color.b),
                behavior_cfg
            ))

        # — State holders —
        self.loot_items   = self.spawner.spawn_initial_loot()
        self.shots        = []
        self.total_agents = len(self.agents)

        # match lifecycle & stats
        self.game_state   = "RUNNING"
        self.game_over_tick = None
        self.winner = None
        self.match_stats = {}
        self.eliminated_agents = []
        self.report_printed = False
        self.ticks = 0
        self.initial_agent_count = len(self.agents)
        self.total_shots_fired = 0
        self.total_loot_spawned = len(self.loot_items)

        # camera reset
        self.cam_offset = [0, 0]
        self.zoom       = 1.0
        self.dragging   = False
        self.last_mouse = (0, 0)

        # counts from config
        tree_count  = map_cfg.get("tree_count", 50)
        rock_count  = map_cfg.get("rock_count", 30)
        grass_count = map_cfg.get("grass_count",100)

        self.tree_positions  = [self.world.random_pos() for _ in range(tree_count)]
        self.rock_positions  = [self.world.random_pos() for _ in range(rock_count)]
        self.grass_positions = [self.world.random_pos() for _ in range(grass_count)]

        self.world.trees = self.tree_positions
        self.world.rocks = self.rock_positions

    def run(self):
        running = True
        while running:
            for e in pygame.event.get():
                # Quit
                if e.type == pygame.QUIT:
                    running = False

                elif e.type == pygame.KEYDOWN:
                    if e.key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                    elif self.game_state == "GAME_OVER" and e.key == pygame.K_r:
                        self._start_match()

                if self.game_state != "RUNNING":
                    continue

                # Mouse button pressed
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    # Left click → select agent
                    if e.button == 1:
                        sx, sy = e.pos
                        if self._handle_sidebar_click(sx, sy):
                            continue
                        if sx >= self.world_w:
                            continue
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
                        if e.pos[0] < self.world_w:
                            self.dragging   = True
                            self.last_mouse = e.pos

                    # Wheel up → zoom in
                    elif e.button == 4:
                        if e.pos[0] < self.world_w:
                            self.zoom = min(self.zoom * 1.1, 5.0)
                    # Wheel down → zoom out
                    elif e.button == 5:
                        if e.pos[0] < self.world_w:
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
        if self.game_state != "RUNNING":
            return

        self.ticks += 1

        # 1) Storm
        self.storm.update()

        # 2) Spawn loot occasionally, but only inside the safe zone
        if random.random() < 0.05:
            new_loot = self.spawner.spawn_loot()
            inside = [
                it for it in new_loot
                if self.storm.in_safe_zone(it['pos'])
            ]
            if inside:
                self.loot_items.extend(inside)
                self.total_loot_spawned += len(inside)

        # 3) Agent actions: decide, move/attack, pickup, storm damage & elimination
        self.shots = []
        for a in self.agents[:]:
            shot = a.tick(self.agents, self.loot_items)
            if shot:
                self.shots.append(shot)

        for a in self.agents[:]:
            if a.health <= 0:
                log_event('eliminate', {'agent': a.id})
                self._record_elimination(a)
                self.agents.remove(a)
                if self.selected_agent and self.selected_agent.id == a.id:
                    self.selected_agent = None

        self.total_shots_fired += len(self.shots)
        self._evaluate_game_over()

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
        view_w = min(self.world_w/self.zoom,  self.world.width)
        view_h = min(self.world_h/self.zoom,  self.world.height)
        max_x  = self.world.width  - view_w
        max_y  = self.world.height - view_h
        vx     = max(0, min(self.cam_offset[0], max_x))
        vy     = max(0, min(self.cam_offset[1], max_y))
        vp     = pygame.Rect(int(vx), int(vy), int(view_w), int(view_h))
        sub    = ws.subsurface(vp)
        scaled = pygame.transform.smoothscale(sub, (self.world_w, self.world_h))
        self.screen.blit(scaled, (0, 0))

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


        # Agent inspector
        if self.selected_agent:
            agent = self.selected_agent
            pygame.draw.rect(self.screen, (30, 30, 30), (20, 120, 270, 220))
            pygame.draw.rect(self.screen, (200, 200, 50), (20, 120, 270, 220), 2)
            font = self.font
            lines = [
                f"Agent #{agent.id}",
                f"Health: {int(agent.health)}",
                f"Shield: {int(agent.shield)}",
                f"Position: ({int(agent.pos[0])}, {int(agent.pos[1])})",
                f"Skill: {agent.skill:.2f}  Luck: {agent.luck:.2f}",
                f"Kills: {agent.kills}",
                f"Last Strategy: {agent.last_decision}",
                f"Current Strategy: {agent.current_action}",
                f"Inventory:",
                f"  Weapons: " + ", ".join(getattr(w, 'name', str(w)) for w in agent.inventory.weapons) if agent.inventory.weapons else "  Weapons: (none)",
                f"  Consumables: {len(agent.inventory.consumables)}"
            ]
            for i, text in enumerate(lines):
                surf = font.render(text, True, (255, 255, 255))
                self.screen.blit(surf, (28, 128 + i * 18))
                screen_x = int((agent.pos[0] - vx) * self.zoom)
                screen_y = int((agent.pos[1] - vy) * self.zoom)
                # Draw highlight at the scaled position & size
                pygame.draw.circle(
                    self.screen,
                    (255, 255, 0),
                    (screen_x, screen_y),
                    max(2, int(9 * self.zoom)),  # scale radius too (or keep fixed)
                    2
                )

        self._render_sidebar()

        if self.game_state == "GAME_OVER":
            self._render_game_over_overlay()

        # 10) Flip display
        pygame.display.flip()

    def _leaderboard_agents(self):
        ranked = sorted(
            self.agents,
            key=lambda a: (-a.kills, -(a.health + a.shield), a.id)
        )
        return ranked[:self.sidebar_top_n]

    def _render_game_over_overlay(self):
        panel_w = 420
        panel_h = 200
        panel_x = (self.world_w - panel_w) // 2
        panel_y = (self.world_h - panel_h) // 2
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 190))
        pygame.draw.rect(panel, (200, 200, 200), panel.get_rect(), 2)

        winner_text = "Winner: "
        if self.winner:
            weapon = "(none)"
            if self.winner.inventory.weapons:
                weapon = getattr(self.winner.inventory.weapons[0], 'name', str(self.winner.inventory.weapons[0]))
            winner_text += (
                f"Agent #{self.winner.id} | Kills: {self.winner.kills} | "
                f"HP: {int(self.winner.health)} | Shield: {int(self.winner.shield)} | Weapon: {weapon}"
            )
        else:
            winner_text += "No winner"

        lines = [
            "Match Over",
            winner_text,
            f"Duration: {self.match_stats.get('duration_ticks', self.ticks)} ticks "
            f"({self.match_stats.get('duration_seconds', self.ticks / TICK_RATE):.1f}s)",
            "Press Q or ESC to quit",
            "Press R to restart",
        ]

        for idx, text in enumerate(lines):
            surf = self.font.render(text, True, (240, 240, 240))
            panel.blit(surf, (20, 20 + idx * 32))

        self.screen.blit(panel, (panel_x, panel_y))

    def _handle_sidebar_click(self, sx, sy):
        if sx < self.world_w:
            return False

        rel_x = sx - self.world_w
        if rel_x < 0 or rel_x > self.sidebar_w:
            return False

        header_bottom = self.sidebar_pad + self.sidebar_header_h
        row_area_start = header_bottom
        if sy < row_area_start:
            return True

        idx = (sy - row_area_start) // self.sidebar_row_h
        agents = self._leaderboard_agents()
        if 0 <= idx < len(agents):
            self.selected_agent = agents[int(idx)]
        return True

    def _render_sidebar(self):
        sidebar_x = self.world_w
        bg_rect = pygame.Rect(sidebar_x, 0, self.sidebar_w, self.world_h)
        pygame.draw.rect(self.screen, (24, 24, 24), bg_rect)

        header = self.font.render("Leaderboard (Top 25)", True, (240, 240, 240))
        self.screen.blit(header, (sidebar_x + self.sidebar_pad, self.sidebar_pad))
        count_lbl = self.id_font.render(
            f"Alive: {len(self.agents)} / {self.total_agents}", True, (200, 200, 200)
        )
        self.screen.blit(count_lbl, (sidebar_x + self.sidebar_pad, self.sidebar_pad + 18))

        header_bottom = self.sidebar_pad + self.sidebar_header_h
        row_width = self.sidebar_w - 2 * self.sidebar_pad
        agents = self._leaderboard_agents()

        for idx, agent in enumerate(agents):
            row_y = header_bottom + idx * self.sidebar_row_h
            row_rect = pygame.Rect(sidebar_x + self.sidebar_pad, row_y, row_width, self.sidebar_row_h - 6)
            is_selected = self.selected_agent and agent.id == self.selected_agent.id
            base_color = (40, 40, 40) if idx % 2 == 0 else (34, 34, 34)
            pygame.draw.rect(self.screen, base_color, row_rect)
            if is_selected:
                pygame.draw.rect(self.screen, (200, 180, 60), row_rect, 2)

            rank_surf = self.font.render(f"{idx+1}", True, (210, 210, 210))
            self.screen.blit(rank_surf, (row_rect.x + 6, row_rect.y + 6))

            icon = pygame.transform.smoothscale(self.agent_sprite, (20, 20))
            tint = pygame.Surface(icon.get_size(), pygame.SRCALPHA)
            tint.fill((*agent.color, 255))
            icon.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self.screen.blit(icon, (row_rect.x + 32, row_rect.y + 4))

            name_surf = self.font.render(f"Agent #{agent.id}", True, (230, 230, 230))
            self.screen.blit(name_surf, (row_rect.x + 60, row_rect.y + 4))

            kills_surf = self.id_font.render(f"K: {agent.kills}", True, (200, 200, 200))
            self.screen.blit(kills_surf, (row_rect.x + 60, row_rect.y + 22))

            hp_ratio = max(0, min(1, agent.health / 100))
            sh_ratio = max(0, min(1, agent.shield / 100))
            bar_w = 90
            bar_h = 6
            bar_x = row_rect.x + row_rect.width - bar_w - 10
            hp_y = row_rect.y + 6
            sh_y = hp_y + bar_h + 4
            pygame.draw.rect(self.screen, (70, 70, 70), (bar_x, hp_y, bar_w, bar_h))
            pygame.draw.rect(self.screen, (60, 160, 80), (bar_x, hp_y, int(bar_w * hp_ratio), bar_h))
            pygame.draw.rect(self.screen, (70, 70, 70), (bar_x, sh_y, bar_w, bar_h))
            pygame.draw.rect(self.screen, (90, 160, 200), (bar_x, sh_y, int(bar_w * sh_ratio), bar_h))

            hp_lbl = self.id_font.render(f"HP {int(agent.health)}", True, (190, 190, 190))
            sh_lbl = self.id_font.render(f"SH {int(agent.shield)}", True, (190, 190, 190))
            self.screen.blit(hp_lbl, (bar_x - 48, hp_y - 2))
            self.screen.blit(sh_lbl, (bar_x - 48, sh_y - 2))

            weapon_name = "(none)"
            if agent.inventory.weapons:
                weapon = agent.inventory.weapons[0]
                weapon_name = getattr(weapon, 'name', str(weapon))
            action_lbl = agent.current_action or "idle"
            strategy = agent.last_decision or "?"
            stat_text = f"{weapon_name} | {action_lbl} | {strategy}"
            stat_surf = self.id_font.render(stat_text, True, (200, 200, 200))
            self.screen.blit(stat_surf, (row_rect.x + 60, row_rect.y + self.sidebar_row_h - 18))

    def _record_elimination(self, agent):
        killer = agent.last_damaged_by
        cause = "storm" if killer is None and not self.storm.in_safe_zone(agent.pos) else "combat"
        self.eliminated_agents.append({
            "tick": self.ticks,
            "id": agent.id,
            "killer": killer,
            "kills": agent.kills,
            "survival_time": self.ticks,
            "cause": cause
        })

    def _evaluate_game_over(self):
        if self.game_state != "RUNNING":
            return

        if len(self.agents) <= 1:
            self.game_state = "GAME_OVER"
            self.game_over_tick = self.ticks
            self.winner = self.agents[0] if self.agents else None
            self._collect_match_stats()
            self.print_match_report()
            flush()

    def _collect_match_stats(self):
        duration_ticks = self.game_over_tick if self.game_over_tick is not None else self.ticks
        duration_seconds = duration_ticks / TICK_RATE
        eliminations = self.initial_agent_count - len(self.agents)
        storm_phases_completed = self.storm.current_phase + (1 if self.storm.ticks_in_phase > 0 else 0)
        storm_phases_completed = min(storm_phases_completed, len(self.storm.phases))

        all_agents = []
        for agent in self.agents:
            weapon = None
            if agent.inventory.weapons:
                weapon = getattr(agent.inventory.weapons[0], 'name', str(agent.inventory.weapons[0]))
            all_agents.append({
                "id": agent.id,
                "kills": agent.kills,
                "health": agent.health,
                "shield": agent.shield,
                "weapon": weapon
            })

        for elim in self.eliminated_agents:
            all_agents.append({
                "id": elim["id"],
                "kills": elim["kills"],
                "health": 0,
                "shield": 0,
                "weapon": None
            })

        top_killers = sorted(
            all_agents,
            key=lambda entry: (-entry["kills"], entry["id"])
        )[:10]

        elimination_timeline = sorted(self.eliminated_agents, key=lambda e: e["tick"])
        survival_times = [entry["survival_time"] for entry in elimination_timeline]
        average_survival = (
            sum(survival_times) / len(survival_times)
            if survival_times else duration_ticks
        )

        self.match_stats = {
            "duration_ticks": duration_ticks,
            "duration_seconds": duration_seconds,
            "initial_agents": self.initial_agent_count,
            "remaining_agents": len(self.agents),
            "eliminations": eliminations,
            "storm_phases_completed": storm_phases_completed,
            "storm_phase_total": len(self.storm.phases),
            "final_storm_radius": self.storm.radius,
            "total_shots_fired": self.total_shots_fired,
            "total_loot_spawned": self.total_loot_spawned,
            "remaining_loot": len(self.loot_items),
            "top_killers": top_killers,
            "elimination_timeline": elimination_timeline,
            "average_survival_time": average_survival,
        }

        if self.winner:
            weapon = None
            if self.winner.inventory.weapons:
                weapon = getattr(self.winner.inventory.weapons[0], 'name', str(self.winner.inventory.weapons[0]))
            self.match_stats["winner"] = {
                "id": self.winner.id,
                "kills": self.winner.kills,
                "health": self.winner.health,
                "shield": self.winner.shield,
                "weapon": weapon,
            }
        else:
            self.match_stats["winner"] = None

    def print_match_report(self):
        if self.report_printed:
            return

        if not self.match_stats:
            self._collect_match_stats()

        self.report_printed = True
        stats = self.match_stats
        lines = []
        lines.append("=== Match Report ===")
        if stats["winner"]:
            winner = stats["winner"]
            weapon = winner["weapon"] or "(none)"
            lines.append(
                f"Winner: Agent #{winner['id']} | Kills: {winner['kills']} | "
                f"HP: {winner['health']:.1f} | Shield: {winner['shield']:.1f} | Weapon: {weapon}"
            )
        else:
            lines.append("Winner: No winner (all eliminated)")

        lines.append(
            f"Duration: {stats['duration_ticks']} ticks ({stats['duration_seconds']:.1f} seconds)"
        )
        lines.append(
            f"Agents: start {stats['initial_agents']}, remaining {stats['remaining_agents']}, "
            f"eliminations {stats['eliminations']}"
        )
        lines.append(
            f"Storm: {stats['storm_phases_completed']}/{stats['storm_phase_total']} phases, "
            f"final radius {stats['final_storm_radius']:.1f}"
        )
        lines.append(
            f"Shots fired: {stats['total_shots_fired']} | Loot spawned: {stats['total_loot_spawned']} "
            f"| Loot remaining: {stats['remaining_loot']}"
        )

        lines.append("Top eliminations (up to 10):")
        for entry in stats["top_killers"]:
            weapon = entry.get("weapon") or "(unknown)"
            lines.append(
                f"  Agent #{entry['id']} — Kills: {entry['kills']} | Weapon: {weapon}"
            )

        if stats["elimination_timeline"]:
            lines.append("Elimination timeline:")
            for elim in stats["elimination_timeline"]:
                killer = elim["killer"]
                killer_text = "Storm/unknown" if killer is None else f"Agent #{killer}"
                lines.append(
                    f"  Tick {elim['tick']}: Agent #{elim['id']} eliminated by {killer_text} "
                    f"(kills: {elim['kills']})"
                )

        lines.append(
            f"Average survival time: {stats['average_survival_time']:.1f} ticks"
        )
        print("\n".join(lines))
