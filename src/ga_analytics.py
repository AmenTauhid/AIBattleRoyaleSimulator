"""Visualizations and reports for genetic algorithm evolution runs."""

from __future__ import annotations

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from src.agent import BehaviorType
from src.genetic import EvolutionResult, STAT_NAMES, BEHAVIORS


BEHAVIOR_NAMES = [b.value for b in BEHAVIORS]


def generate_evolution_report(result: EvolutionResult, output_dir: str) -> None:
    """Generate all GA charts and the evolution report."""
    charts_dir = os.path.join(output_dir, "charts")
    os.makedirs(charts_dir, exist_ok=True)

    sns.set_theme(style="darkgrid")

    _chart_fitness_curve(result, charts_dir)
    _chart_stat_evolution(result, charts_dir)
    _chart_behavior_evolution(result, charts_dir)
    _chart_best_genome_radar(result, charts_dir)
    _chart_final_population(result, charts_dir)
    _write_evolution_report(result, output_dir)

    plt.close("all")


def _chart_fitness_curve(result: EvolutionResult, charts_dir: str) -> None:
    """Plot best and average fitness over generations."""
    fig, ax = plt.subplots(figsize=(10, 5))
    gens = [log.generation for log in result.logs]
    best = [log.best_fitness for log in result.logs]
    avg = [log.avg_fitness for log in result.logs]

    ax.plot(gens, best, label="Best Fitness", color="#e74c3c", linewidth=2)
    ax.plot(gens, avg, label="Avg Fitness", color="#3498db", linewidth=2, alpha=0.7)
    ax.fill_between(gens, avg, best, alpha=0.1, color="#e74c3c")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Fitness")
    ax.set_title("Fitness Over Generations")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(charts_dir, "fitness_curve.png"), dpi=150)
    plt.close(fig)


def _chart_stat_evolution(result: EvolutionResult, charts_dir: str) -> None:
    """Plot how average stat weights shift over generations."""
    fig, ax = plt.subplots(figsize=(10, 6))
    gens = [log.generation for log in result.logs]
    colors = sns.color_palette("Set2", 6)

    for i, name in enumerate(STAT_NAMES):
        values = [log.avg_stats[i] for log in result.logs]
        ax.plot(gens, values, label=name, color=colors[i], linewidth=2)

    ax.set_xlabel("Generation")
    ax.set_ylabel("Average Stat Weight")
    ax.set_title("Stat Weight Evolution Over Generations")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(os.path.join(charts_dir, "stat_evolution.png"), dpi=150)
    plt.close(fig)


def _chart_behavior_evolution(result: EvolutionResult, charts_dir: str) -> None:
    """Stacked area chart of behavior type frequency over generations."""
    fig, ax = plt.subplots(figsize=(10, 5))
    gens = [log.generation for log in result.logs]
    colors = sns.color_palette("Set2", len(BEHAVIOR_NAMES))

    # Build arrays for stackplot
    counts = np.array([log.behavior_counts for log in result.logs], dtype=np.float64)
    totals = counts.sum(axis=1, keepdims=True)
    fractions = counts / totals * 100

    ax.stackplot(gens, fractions.T, labels=BEHAVIOR_NAMES, colors=colors, alpha=0.8)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Population Share (%)")
    ax.set_title("Behavior Type Distribution Over Generations")
    ax.legend(loc="upper right")
    ax.set_ylim(0, 100)
    fig.tight_layout()
    fig.savefig(os.path.join(charts_dir, "behavior_evolution.png"), dpi=150)
    plt.close(fig)


def _chart_best_genome_radar(result: EvolutionResult, charts_dir: str) -> None:
    """Radar chart of the best evolved genome's stats."""
    best = result.best_genome
    stats = best.to_stats()
    values = stats.to_array().tolist()

    angles = np.linspace(0, 2 * np.pi, len(STAT_NAMES), endpoint=False).tolist()
    values_closed = values + [values[0]]
    angles_closed = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    ax.plot(angles_closed, values_closed, "o-", linewidth=2, color="#e74c3c")
    ax.fill(angles_closed, values_closed, alpha=0.2, color="#e74c3c")
    ax.set_xticks(angles)
    ax.set_xticklabels(STAT_NAMES, fontsize=11)
    ax.set_ylim(0, 10)
    ax.set_title(
        f"Best Evolved Build: {best.behavior.value}\n(Gen {best.generation})",
        pad=20, fontsize=13,
    )

    # Annotate values
    for angle, val, name in zip(angles, values, STAT_NAMES):
        ax.annotate(str(val), xy=(angle, val), fontsize=10, fontweight="bold",
                    ha="center", va="bottom")

    fig.tight_layout()
    fig.savefig(os.path.join(charts_dir, "best_genome_radar.png"), dpi=150)
    plt.close(fig)


def _chart_final_population(result: EvolutionResult, charts_dir: str) -> None:
    """Box plot of stat distributions in the final evolved population."""
    fig, ax = plt.subplots(figsize=(10, 5))

    pop_stats = []
    for genome in result.final_population:
        s = genome.to_stats()
        pop_stats.append(s.to_array())

    pop_array = np.array(pop_stats)
    positions = range(len(STAT_NAMES))
    colors = sns.color_palette("Set2", 6)

    bp = ax.boxplot(
        [pop_array[:, i] for i in range(6)],
        labels=STAT_NAMES,
        patch_artist=True,
        widths=0.6,
    )
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_ylabel("Stat Value")
    ax.set_title("Final Population Stat Distribution")
    ax.axhline(y=5, color="gray", linestyle="--", alpha=0.5, label="Baseline avg (5.0)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(charts_dir, "final_population_stats.png"), dpi=150)
    plt.close(fig)


def _write_evolution_report(result: EvolutionResult, output_dir: str) -> None:
    """Write the evolution analysis markdown report."""
    best = result.best_genome
    best_stats = best.to_stats()

    # Track convergence point (when best fitness stabilizes)
    fitnesses = [log.best_fitness for log in result.logs]
    final_fitness = fitnesses[-1] if fitnesses else 0
    convergence_gen = 0
    for i, f in enumerate(fitnesses):
        if f >= final_fitness * 0.95:
            convergence_gen = i
            break

    # Final population behavior breakdown
    final_behaviors = result.logs[-1].behavior_counts if result.logs else [0] * 4
    total_pop = sum(final_behaviors)

    lines = [
        "# Evolution Report",
        f"## {result.total_generations} Generations",
        "",
        "---",
        "",
        "### Best Evolved Build",
        "",
        f"- **Behavior Type:** {best.behavior.value}",
        f"- **Discovered in Generation:** {best.generation}",
        f"- **Fitness Score:** {best.fitness:.1f}",
        f"- **Stats:** "
        + " / ".join(f"**{STAT_NAMES[i].upper()[:3]}:{getattr(best_stats, STAT_NAMES[i])}**" for i in range(6)),
        "",
        "---",
        "",
        "### Evolution Summary",
        "",
        f"- **Convergence:** ~Generation {convergence_gen} (95% of final fitness)",
        f"- **Initial avg fitness:** {result.logs[0].avg_fitness:.1f}" if result.logs else "",
        f"- **Final avg fitness:** {result.logs[-1].avg_fitness:.1f}" if result.logs else "",
        f"- **Fitness improvement:** {((result.logs[-1].avg_fitness / max(result.logs[0].avg_fitness, 0.01)) - 1) * 100:.1f}%" if result.logs else "",
        "",
        "---",
        "",
        "### Final Population Breakdown",
        "",
        "| Behavior | Count | Share |",
        "|----------|-------|-------|",
    ]

    for i, name in enumerate(BEHAVIOR_NAMES):
        count = final_behaviors[i]
        share = count / total_pop * 100 if total_pop else 0
        lines.append(f"| {name} | {count} | {share:.1f}% |")

    lines.extend([
        "",
        "---",
        "",
        "### Evolved Stat Priorities",
        "",
        "| Stat | Best Build | Population Avg | vs Baseline (5.0) |",
        "|------|-----------|----------------|-------------------|",
    ])

    final_avg = result.logs[-1].avg_stats if result.logs else np.ones(6) * 5
    for i, name in enumerate(STAT_NAMES):
        best_val = getattr(best_stats, name)
        avg_val = final_avg[i]
        diff = avg_val - 5.0
        sign = "+" if diff >= 0 else ""
        lines.append(f"| {name} | {best_val} | {avg_val:.1f} | {sign}{diff:.1f} |")

    lines.extend([
        "",
        "---",
        "",
        "### Charts",
        "",
        "![Fitness Curve](charts/fitness_curve.png)",
        "![Stat Evolution](charts/stat_evolution.png)",
        "![Behavior Evolution](charts/behavior_evolution.png)",
        "![Best Genome](charts/best_genome_radar.png)",
        "![Final Population](charts/final_population_stats.png)",
    ])

    report_path = os.path.join(output_dir, "evolution_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def print_evolution_summary(result: EvolutionResult) -> None:
    """Print a brief terminal summary of the evolution."""
    best = result.best_genome
    best_stats = best.to_stats()

    print(f"\n{'='*50}")
    print(f" EVOLUTION COMPLETE - {result.total_generations} generations")
    print(f"{'='*50}")
    print(f"\n Best evolved build:")
    print(f"   Behavior: {best.behavior.value}")
    print(f"   Fitness:  {best.fitness:.1f}")
    print(f"   Stats:")
    for name in STAT_NAMES:
        val = getattr(best_stats, name)
        bar = "#" * val
        print(f"     {name:12s} {val:2d} {bar}")

    if result.logs:
        print(f"\n Fitness progression:")
        print(f"   Gen 0:     avg {result.logs[0].avg_fitness:.1f}")
        print(f"   Gen {result.total_generations - 1}:  avg {result.logs[-1].avg_fitness:.1f}")

        final_behaviors = result.logs[-1].behavior_counts
        total = sum(final_behaviors)
        print(f"\n Final population behaviors:")
        for i, name in enumerate(BEHAVIOR_NAMES):
            pct = final_behaviors[i] / total * 100 if total else 0
            bar = "#" * int(pct / 2)
            print(f"   {name:12s} {pct:5.1f}% {bar}")

    print(f"{'='*50}\n")
