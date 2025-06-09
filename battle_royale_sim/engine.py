import pygame
import random
import yaml
from .constants            import TICK_RATE
from .world                import World
from .storm                import Storm
from .items.loot_spawner   import LootSpawner
from .agent.agent          import Agent
from .telemetry            import flush, log_event

class GameEngine:
    def __init__(self):
        # — Load configs —
        map_cfg     = yaml.safe_load(open('config/map.yaml'))
        buildings_cfg = yaml.safe_load(open('config/buildings.yaml'))
        storm_cfg   = yaml.safe_load(open('config/storm.yaml'))
        loot_cfg    = yaml.safe_load(open('config/loot_table.yaml'))
        agents_cfg  = yaml.safe_load(open('config/agents.yaml'))

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
        self.shots        = []  # [(start_pos, end_pos), ...]
        self.total_agents = len(self.agents)

        # — Pygame setup —
        pygame.init()
        pygame.font.init()
        self.font   = pygame.font.SysFont(None, 24)
        self.screen = pygame.display.set_mode(
            (int(self.world.width), int(self.world.height))
        )
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

        # 3) Move, loot pickup, storm damage & preliminary elimination
        for a in self.agents[:]:
            a.tick(self.loot_items)
            if a.health <= 0:
                log_event('eliminate', {'agent': a.id})
                self.agents.remove(a)

        # 4) Combat: each agent attempts to fire
        self.shots = []
        for a in self.agents[:]:
            shot = a.attack(self.agents)
            if shot:
                self.shots.append(shot)

        # 5) Post-combat elimination
        for a in self.agents[:]:
            if a.health <= 0:
                log_event('eliminate', {'agent': a.id})
                self.agents.remove(a)

    def render(self):
        # 1) Background
        self.screen.fill((34, 139, 34))

        # 2) Draw buildings (cover)
        for b in self.world.buildings:
            rect = pygame.Rect(b['x'], b['y'], b['width'], b['height'])
            pygame.draw.rect(self.screen, (100, 100, 100), rect)

        # 3) Players remaining counter
        remaining = len(self.agents)
        counter_surf = self.font.render(
            f"{remaining} / {self.total_agents}",
            True,
            (255, 255, 255)
        )
        self.screen.blit(counter_surf, (10, 10))

        # 4) Storm-cycle timer
        phase = self.storm.phases[self.storm.current_phase]
        ticks_elapsed  = self.storm.ticks_in_phase
        ticks_total    = phase['duration'] * TICK_RATE
        ticks_left     = max(0, ticks_total - ticks_elapsed)
        secs_left      = ticks_left // TICK_RATE
        timer_surf = self.font.render(
            f"Next shrink in: {secs_left}s",
            True,
            (255, 255, 255)
        )
        self.screen.blit(timer_surf, (10, 30))

        # 5) Loot items
        for item in self.loot_items:
            col = (255, 215, 0) if item['type'] == 'weapon' else (0, 255, 255)
            x, y = item['pos']
            pygame.draw.rect(self.screen, col, (int(x-3), int(y-3), 6, 6))

        # 6) Agents + health bars
        for a in self.agents:
            x, y = a.pos
            # Agent circle
            pygame.draw.circle(
                self.screen,
                (0, 0, 255),
                (int(x), int(y)),
                5
            )
            # Health bar (red bg + green fg)
            hb_width = int((a.health / 100) * 10)
            pygame.draw.rect(
                self.screen,
                (255, 0, 0),
                (int(x-5), int(y-12), 10, 2)
            )
            pygame.draw.rect(
                self.screen,
                (0, 255, 0),
                (int(x-5), int(y-12), hb_width, 2)
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
                (int(end[0]),   int(end[1])),
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

