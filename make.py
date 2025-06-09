import os
from pathlib import Path

def create_structure(base_path="."):
    # Define directories
    dirs = [
        "config",
        "battle_royale_sim",
        "battle_royale_sim/items",
        "battle_royale_sim/agent"
    ]
    
    # Define files
    files = [
        "config/map.yaml",
        "config/storm.yaml",
        "config/loot_table.yaml",
        "config/agents.yaml",
        "battle_royale_sim/__init__.py",
        "battle_royale_sim/constants.py",
        "battle_royale_sim/utils.py",
        "battle_royale_sim/world.py",
        "battle_royale_sim/storm.py",
        "battle_royale_sim/telemetry.py",
        "battle_royale_sim/inventory.py",
        "battle_royale_sim/engine.py",
        "battle_royale_sim/items/__init__.py",
        "battle_royale_sim/items/weapon.py",
        "battle_royale_sim/items/loot_spawner.py",
        "battle_royale_sim/agent/__init__.py",
        "battle_royale_sim/agent/agent.py",
        "battle_royale_sim/agent/behavior.py",
        "run_simulation.py",
        "requirements.txt"
    ]
    
    # Create directories
    for d in dirs:
        dir_path = Path(base_path) / d
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {dir_path}")

    # Create files
    for f in files:
        file_path = Path(base_path) / f
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch(exist_ok=True)
        print(f"Created file: {file_path}")

if __name__ == "__main__":
    create_structure()
