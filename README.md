# Battle Royale Simulator

A Python simulation engine where 100 agents compete on a 2D grid with a shrinking safe zone. Each agent has randomized stats and a behavior tree. Run thousands of simulations to analyze which trait combinations survive longest, or use a **genetic algorithm** to evolve the optimal build from scratch.

## Setup

```bash
pip install -r requirements.txt
```

Requires Python 3.11+.

## Project Structure

```
src/
  main.py                   # CLI entry point
  core/
    agent.py                # Agent dataclass, stat generation, behavior trees
    map.py                  # Grid, zone shrinking, obstacles, loot
    combat.py               # Combat resolution (hit/damage/crit/stealth)
    simulation.py           # Single game loop and event logging
  analysis/
    batch.py                # Parallel batch runner (multiprocessing)
    analytics.py            # Charts and markdown report generation
  evolution/
    genetic.py              # Genetic algorithm engine
    ga_analytics.py         # Evolution-specific visualizations
  gui/
    viewer.py               # Pygame real-time simulation viewer
    colors.py               # Color constants and palettes
```

## Usage

### Batch Simulation

Run N simulations with random agents, then analyze the results:

```bash
python src/main.py simulate --sims 1000 --output results/
python src/main.py simulate --sims 500 --map-size 100 --workers 4
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--sims` | 1000 | Number of simulations to run |
| `--output` | `results/` | Output directory |
| `--map-size` | 100 | Map width and height |
| `--workers` | auto | Number of parallel workers |

**Output:** 7 analysis charts (win rates, death heatmap, stat radar, etc.) + `meta_report.md`

### Genetic Algorithm Evolution

Evolve the optimal agent build over generations using natural selection:

```bash
python src/main.py evolve --generations 200 --output evolution_results/
python src/main.py evolve --generations 500 --games-per-eval 5
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--generations` | 200 | Number of evolution generations |
| `--population` | 100 | Population size per generation |
| `--games-per-eval` | 3 | Games per fitness evaluation |
| `--mutation-rate` | 0.15 | Mutation rate per gene |
| `--output` | `evolution_results/` | Output directory |
| `--seed` | 42 | Random seed for reproducibility |

**Output:** 5 evolution charts (fitness curve, stat evolution, behavior frequency, best genome radar, population box plots) + `evolution_report.md`

### Watch Mode (Live Viewer)

Watch a single simulation play out in real-time with a Pygame GUI:

```bash
python src/main.py watch --seed 42
python src/main.py watch --seed 123 --agents 50 --map-size 80
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--seed` | 42 | Random seed |
| `--map-size` | 100 | Map size |
| `--agents` | 100 | Number of agents |
| `--fps` | 60 | Render framerate |

**Controls:** SPACE play/pause, S step one turn, UP/DOWN adjust speed, R restart with new seed, ESC quit.

## How It Works

### Agent Design

Each agent receives **30 stat points** distributed across 6 stats (0-10 each):

| Stat | Effect |
|------|--------|
| Aggression | Damage output, scales combat damage |
| Speed | Movement tiles per turn, dodge chance |
| Stealth | Avoid detection, escape combat |
| Accuracy | Hit chance in combat |
| Health | Starting HP pool (50 + health x 10) |
| Luck | Critical hit chance, tiebreakers |

### Behavior Types

| Type | Strategy |
|------|----------|
| Hunter | Actively seeks nearest agent to fight (12-tile detection range) |
| Camper | Stays still, avoids combat, flees when possible |
| Scavenger | Prioritizes loot tiles, fights only if cornered |
| Nomad | Moves randomly, fights whatever it encounters |

All agents switch to hunter behavior in the endgame (< 20 agents remaining).

### Simulation Mechanics

- **Map**: 100x100 grid with clustered obstacles and scattered loot tiles
- **Zone**: Shrinks every 15 turns with escalating damage (8 + 5 per phase)
- **Combat**: Triggered within 2 tiles. Hit chance = accuracy vs speed, damage scales with aggression, stealth enables escape, luck drives crits
- **Kill rewards**: 25% max HP heal + 10% damage bonus per kill (up to +50%)
- **Loot**: Temporary stat buffs (+1 to +3) for 10-20 turns
- **Win condition**: Last agent standing (hard cap at 500 turns)

### Genetic Algorithm

The GA evolves optimal stat allocations and behavior types through natural selection:

1. **Genome**: 6 stat weights (normalized to distribute 30 points) + behavior type
2. **Fitness**: Placement score (winner = 100, last = 1) + kill bonus, averaged over multiple games
3. **Selection**: Tournament selection (best of 3 random candidates)
4. **Crossover**: Per-stat random interpolation between two parents
5. **Mutation**: Gaussian perturbation on stat weights (15% rate), occasional behavior flip
6. **Elitism**: Top 10 genomes survive unchanged each generation

Over hundreds of generations, the population converges on the optimal build.
