# Battle Royale Simulator

A Python simulation engine that spawns 100 AI agents on a 2D grid map with a shrinking safe zone. Agents have randomized stats and behavior trees. Run thousands of simulations and analyze which trait combinations survive longest.

## Setup

```bash
pip install -r requirements.txt
```

Requires Python 3.11+.

## Usage

```bash
# Run 1000 simulations (default)
python src/main.py

# Custom run
python src/main.py --sims 500 --output results/ --map-size 100 --workers 4
```

### CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--sims` | 1000 | Number of simulations to run |
| `--output` | `results/` | Output directory for charts and report |
| `--map-size` | 100 | Map width and height |
| `--workers` | auto | Number of parallel workers |

## Output

After running, the output directory contains:

- `charts/` - PNG charts with analysis visualizations
  - `win_rate_by_behavior.png` - Win rate per behavior type
  - `win_rate_by_dominant_stat.png` - Win rate by highest stat
  - `avg_survival_by_behavior.png` - Average turns survived
  - `kd_by_behavior.png` - Kill/death stats
  - `death_heatmap.png` - Where agents die on the map
  - `winner_stats_vs_avg.png` - Radar chart of winner stats vs average
  - `placement_by_stat_level.png` - How stat levels affect placement
- `meta_report.md` - Full markdown analysis with tables and charts

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
