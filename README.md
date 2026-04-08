# Battle Royale Simulator

A Python simulation engine that spawns 100 AI agents on a 2D grid map with a shrinking safe zone. Agents have randomized stats and behavior trees. Run thousands of simulations and analyze which trait combinations survive longest.

## Setup

```bash
pip install -r requirements.txt
```

Requires Python 3.11+.

## Usage

### Batch Simulation Mode

```bash
# Run 1000 simulations with random agents
python src/main.py simulate --sims 1000 --output results/

# Custom run
python src/main.py simulate --sims 500 --output results/ --map-size 100 --workers 4
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--sims` | 1000 | Number of simulations to run |
| `--output` | `results/` | Output directory for charts and report |
| `--map-size` | 100 | Map width and height |
| `--workers` | auto | Number of parallel workers |

### Evolution Mode (Genetic Algorithm)

```bash
# Evolve optimal agent builds over 200 generations
python src/main.py evolve --generations 200 --output evolution_results/

# Longer evolution with more games per evaluation
python src/main.py evolve --generations 500 --games-per-eval 5 --output evolution_results/
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--generations` | 200 | Number of evolution generations |
| `--population` | 100 | Population size per generation |
| `--games-per-eval` | 3 | Games per fitness evaluation |
| `--mutation-rate` | 0.15 | Mutation rate per gene |
| `--output` | `evolution_results/` | Output directory |
| `--map-size` | 100 | Map width and height |
| `--seed` | 42 | Random seed for reproducibility |

## Output

### Simulation Mode

- `charts/` - 7 PNG analysis charts (win rates, heatmap, radar, etc.)
- `meta_report.md` - Full analysis with tables and optimal build

### Evolution Mode

- `charts/` - 5 PNG evolution charts
  - `fitness_curve.png` - Best/average fitness over generations
  - `stat_evolution.png` - How stat priorities shift during evolution
  - `behavior_evolution.png` - Behavior type frequency over time
  - `best_genome_radar.png` - Radar chart of the best evolved build
  - `final_population_stats.png` - Stat distribution of final population
- `evolution_report.md` - Full evolution analysis with optimal build

## Agent Design

Each agent receives 30 stat points distributed across 6 stats (0-10 each):

- **Aggression** - Damage output and fight likelihood
- **Speed** - Movement tiles per turn, dodge chance
- **Stealth** - Avoid detection, escape combat
- **Accuracy** - Hit chance in combat
- **Health** - Starting HP pool (50 + health * 10)
- **Luck** - Critical hit chance, tiebreakers

### Behavior Types

- **Hunter** - Actively seeks nearest agent to fight
- **Camper** - Stays still, avoids combat, fights only in self-defense
- **Scavenger** - Prioritizes loot tiles, fights only if cornered
- **Nomad** - Moves randomly, fights whatever it encounters

## Simulation Mechanics

- **Map**: Grid with clustered obstacles and scattered loot tiles
- **Zone**: Shrinks every 20 turns, dealing escalating damage to agents outside
- **Combat**: Triggered when agents are adjacent. Uses accuracy vs speed for hit chance, aggression for damage, stealth for escape, luck for crits
- **Loot**: Temporary stat buffs collected by walking over loot tiles
- **Win condition**: Last agent standing (hard cap at 500 turns)
