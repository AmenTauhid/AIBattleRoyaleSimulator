"""Head-to-head matchup analysis between behavior types."""

from __future__ import annotations

import os
from collections import Counter, defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from src.core.agent import BehaviorType
from src.core.simulation import SimulationResult


BEHAVIOR_NAMES = [b.value for b in BehaviorType]


def analyze_matchups(results: list[SimulationResult], output_dir: str) -> None:
    """Generate head-to-head matchup analysis from simulation results."""
    charts_dir = os.path.join(output_dir, "charts")
    os.makedirs(charts_dir, exist_ok=True)

    # Count kills between behavior types
    kill_matrix = defaultdict(lambda: defaultdict(int))  # killer_type -> victim_type -> count
    encounter_matrix = defaultdict(lambda: defaultdict(int))

    for result in results:
        for ke in result.kill_events:
            if ke.cause != "combat":
                continue
            killer = result.agent_summaries[ke.killer_id]
            victim = result.agent_summaries[ke.victim_id]
            kill_matrix[killer.behavior.value][victim.behavior.value] += 1
            encounter_matrix[killer.behavior.value][victim.behavior.value] += 1
            encounter_matrix[victim.behavior.value][killer.behavior.value] += 1

    # Build numpy matrix
    n = len(BEHAVIOR_NAMES)
    kill_array = np.zeros((n, n), dtype=np.float64)
    for i, attacker in enumerate(BEHAVIOR_NAMES):
        for j, defender in enumerate(BEHAVIOR_NAMES):
            kill_array[i, j] = kill_matrix[attacker][defender]

    # Win rate matrix (kills / total encounters between pair)
    winrate_array = np.zeros((n, n), dtype=np.float64)
    for i, a in enumerate(BEHAVIOR_NAMES):
        for j, b in enumerate(BEHAVIOR_NAMES):
            if i == j:
                winrate_array[i, j] = 0.5
            else:
                total = kill_array[i, j] + kill_array[j, i]
                if total > 0:
                    winrate_array[i, j] = kill_array[i, j] / total
                else:
                    winrate_array[i, j] = 0.5

    # Chart: Kill heatmap
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(kill_array, annot=True, fmt=".0f", cmap="YlOrRd",
                xticklabels=BEHAVIOR_NAMES, yticklabels=BEHAVIOR_NAMES, ax=ax)
    ax.set_xlabel("Victim")
    ax.set_ylabel("Killer")
    ax.set_title("Kill Matrix (Killer vs Victim)")
    fig.tight_layout()
    fig.savefig(os.path.join(charts_dir, "kill_matrix.png"), dpi=150)
    plt.close(fig)

    # Chart: Win rate heatmap
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(winrate_array, annot=True, fmt=".2f", cmap="RdYlGn",
                xticklabels=BEHAVIOR_NAMES, yticklabels=BEHAVIOR_NAMES,
                ax=ax, vmin=0, vmax=1, center=0.5)
    ax.set_xlabel("Opponent")
    ax.set_ylabel("Attacker")
    ax.set_title("Combat Win Rate (row vs column)")
    fig.tight_layout()
    fig.savefig(os.path.join(charts_dir, "combat_winrate_matrix.png"), dpi=150)
    plt.close(fig)

    # Write matchup section to report
    lines = [
        "",
        "---",
        "",
        "### Head-to-Head Matchups",
        "",
        "**Combat Win Rate** (row wins against column):",
        "",
        "| vs | " + " | ".join(BEHAVIOR_NAMES) + " |",
        "|----" + "|------" * n + "|",
    ]

    for i, name in enumerate(BEHAVIOR_NAMES):
        row = f"| **{name}** |"
        for j in range(n):
            if i == j:
                row += " -- |"
            else:
                row += f" {winrate_array[i, j]:.0%} |"
        lines.append(row)

    lines.extend([
        "",
        "![Kill Matrix](charts/kill_matrix.png)",
        "![Win Rate Matrix](charts/combat_winrate_matrix.png)",
    ])

    # Append to meta_report.md if it exists
    report_path = os.path.join(output_dir, "meta_report.md")
    if os.path.exists(report_path):
        with open(report_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    print(f"  Matchup charts saved to {charts_dir}/")
