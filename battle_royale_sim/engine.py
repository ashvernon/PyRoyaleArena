import pygame, random, yaml
from .constants      import TICK_RATE
from .world          import World
from .storm          import Storm
from .items.loot_spawner import LootSpawner
from .agent.agent    import Agent
from .telemetry      import flush

class GameEngine:
    def __init__(self):
        # — Load configs —
        map_cfg    = yaml.safe_load(open('config/map.yaml'))
        storm_cfg  = yaml.safe_load(open('config/storm.yaml'))
        loot_cfg   = yaml.safe_load(open('config/loot_table.yaml'))
        agents_cfg = yaml.safe_load(open('config/agents.yaml'))

        # — Init subsystems —
        self.world = World(map_cfg)
        self.storm = Storm(storm_cfg['phases'], self.world)
        self.spawner = LootSpawner(loot_cfg, self.world)

        # — Create agents —
        self.agents = []
        for i in range(agents_cfg['count']):
            s = random.uniform(*agents_cfg['skill_range'])
            l = random.uniform(*agents_cfg['luck_range'])
            self.agents.append(Agent(i, s, l, self.world, self.storm))

        self.loot_items = []

        # — Pygame setup —
        pygame.init()
        self.screen = pygame.display.set_mode((self.world.width, self.world.height))
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
        self.storm.update()

        # Occasionally spawn loot
        if random.random() < 0.05:
            self.loot_items.extend(self.spawner.spawn_loot())

        # Tick each agent
        for a in self.agents[:]:
            a.tick(self.loot_items)
            if a.health <= 0:
                self.agents.remove(a)

    def render(self):
        # 1) Background
        self.screen.fill((34,139,34))

        # 2) Loot
        for item in self.loot_items:
            col = (255,215,0) if item['type']=='weapon' else (0,255,255)
            x,y = item['pos']
            pygame.draw.rect(self.screen, col, (x-3,y-3,6,6))

        # 3) Agents + health bars
        for a in self.agents:
            x,y = a.pos
            pygame.draw.circle(self.screen, (0,0,255), (int(x),int(y)), 5)
            # Health bar
            hb = int(a.health/100*10)
            pygame.draw.rect(self.screen, (255,0,0), (x-5,y-12,10,2))
            pygame.draw.rect(self.screen, (0,255,0), (x-5,y-12,hb,2))

        # 4) Storm circle
        cx,cy = self.world.center
        pygame.draw.circle(self.screen, (0,0,0), (int(cx),int(cy)), int(self.storm.radius), 2)

        pygame.display.flip()
