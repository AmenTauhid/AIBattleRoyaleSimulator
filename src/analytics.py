"""Post-simulation analysis: charts and markdown meta report."""

from __future__ import annotations

import os
from collections import Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from src.agent import BehaviorType, Stats
from src.simulation import SimulationResult


STAT_NAMES = ["aggression", "speed", "stealth", "accuracy", "health", "luck"]
BEHAVIOR_NAMES = [b.value for b in BehaviorType]


def generate_report(
    results: list[SimulationResult],
    output_dir: str,
) -> None:
    """Generate all charts and the markdown meta report."""
    charts_dir = os.path.join(output_dir, "charts")
    os.makedirs(charts_dir, exist_ok=True)

    sns.set_theme(style="darkgrid")

    # Aggregate data
    data = _aggregate(results)

    # Generate charts
    _chart_win_rate_by_behavior(data, charts_dir)
    _chart_win_rate_by_dominant_stat(data, charts_dir)
    _chart_avg_survival_by_behavior(data, charts_dir)
    _chart_kd_by_behavior(data, charts_dir)
    _chart_death_heatmap(data, charts_dir)
    _chart_winner_stats_vs_avg(data, charts_dir)
    _chart_placement_by_stat_level(data, charts_dir)

    # Write markdown report
    _write_meta_report(data, results, output_dir)

    plt.close("all")


def _aggregate(results: list[SimulationResult]) -> dict:
    """Aggregate all simulation results into analysis-ready structures."""
    n = len(results)

    # Winner behavior counts
    winner_behaviors = Counter(r.winner_behavior.value for r in results)

    # Winner dominant stat counts
    winner_dominant_stats = Counter(r.winner_stats.dominant_stat for r in results)

    # Per-agent summaries across all sims
    all_summaries = []
    for r in results:
        all_summaries.extend(r.agent_summaries)

    # Survival by behavior
    survival_by_behavior: dict[str, list[int]] = {b: [] for b in BEHAVIOR_NAMES}
    kills_by_behavior: dict[str, list[int]] = {b: [] for b in BEHAVIOR_NAMES}
    deaths_by_behavior: dict[str, int] = {b: 0 for b in BEHAVIOR_NAMES}
    placements_by_behavior: dict[str, list[int]] = {b: [] for b in BEHAVIOR_NAMES}

    for s in all_summaries:
        bname = s.behavior.value
        survival_by_behavior[bname].append(s.turns_survived)
        kills_by_behavior[bname].append(s.kills)
        placements_by_behavior[bname].append(s.placement)
        if s.cause_of_death != "winner":
            deaths_by_behavior[bname] += 1

    # Death locations
    death_xs = []
    death_ys = []
    map_w = results[0].map_width if results else 100
    map_h = results[0].map_height if results else 100
    for r in results:
        for de in r.death_events:
            death_xs.append(de.x)
            death_ys.append(de.y)

    # Winner stats vs average stats
    winner_stat_arrays = np.array([r.winner_stats.to_array() for r in results], dtype=np.float64)
    all_stat_arrays = np.array([s.base_stats.to_array() for s in all_summaries], dtype=np.float64)
    avg_winner_stats = winner_stat_arrays.mean(axis=0)
    avg_all_stats = all_stat_arrays.mean(axis=0)

    # Stat-placement correlation
    stat_placement_corr = {}
    placements = np.array([s.placement for s in all_summaries], dtype=np.float64)
    for i, sname in enumerate(STAT_NAMES):
        stat_vals = all_stat_arrays[:, i]
        if stat_vals.std() > 0 and placements.std() > 0:
            corr = np.corrcoef(stat_vals, placements)[0, 1]
            stat_placement_corr[sname] = float(corr)
        else:
            stat_placement_corr[sname] = 0.0

    # Placement by stat level
    placement_by_stat_level: dict[str, dict[str, float]] = {}
    for i, sname in enumerate(STAT_NAMES):
        stat_vals = all_stat_arrays[:, i]
        low_mask = stat_vals <= 3
        mid_mask = (stat_vals >= 4) & (stat_vals <= 6)
        high_mask = stat_vals >= 7
        placement_by_stat_level[sname] = {
            "low": float(placements[low_mask].mean()) if low_mask.any() else 50.0,
            "mid": float(placements[mid_mask].mean()) if mid_mask.any() else 50.0,
            "high": float(placements[high_mask].mean()) if high_mask.any() else 50.0,
        }

    return {
        "n": n,
        "winner_behaviors": winner_behaviors,
        "winner_dominant_stats": winner_dominant_stats,
        "survival_by_behavior": survival_by_behavior,
        "kills_by_behavior": kills_by_behavior,
        "deaths_by_behavior": deaths_by_behavior,
        "placements_by_behavior": placements_by_behavior,
        "death_xs": np.array(death_xs),
        "death_ys": np.array(death_ys),
        "map_w": map_w,
        "map_h": map_h,
        "avg_winner_stats": avg_winner_stats,
        "avg_all_stats": avg_all_stats,
        "stat_placement_corr": stat_placement_corr,
        "placement_by_stat_level": placement_by_stat_level,
    }


def _chart_win_rate_by_behavior(data: dict, charts_dir: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    n = data["n"]
    rates = [data["winner_behaviors"].get(b, 0) / n * 100 for b in BEHAVIOR_NAMES]
    colors = sns.color_palette("Set2", len(BEHAVIOR_NAMES))
    bars = ax.bar(BEHAVIOR_NAMES, rates, color=colors, edgecolor="black", linewidth=0.5)
    ax.set_ylabel("Win Rate (%)")
    ax.set_title("Win Rate by Behavior Type")
    ax.set_ylim(0, max(rates) * 1.3 if rates else 100)
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{rate:.1f}%", ha="center", va="bottom", fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(charts_dir, "win_rate_by_behavior.png"), dpi=150)
    plt.close(fig)


def _chart_win_rate_by_dominant_stat(data: dict, charts_dir: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    n = data["n"]
    rates = [data["winner_dominant_stats"].get(s, 0) / n * 100 for s in STAT_NAMES]
    colors = sns.color_palette("muted", len(STAT_NAMES))
    bars = ax.bar(STAT_NAMES, rates, color=colors, edgecolor="black", linewidth=0.5)
    ax.set_ylabel("Win Rate (%)")
    ax.set_title("Win Rate by Dominant Stat")
    ax.set_ylim(0, max(rates) * 1.3 if rates else 100)
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{rate:.1f}%", ha="center", va="bottom", fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(charts_dir, "win_rate_by_dominant_stat.png"), dpi=150)
    plt.close(fig)


def _chart_avg_survival_by_behavior(data: dict, charts_dir: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    avgs = [np.mean(data["survival_by_behavior"][b]) for b in BEHAVIOR_NAMES]
    colors = sns.color_palette("Set2", len(BEHAVIOR_NAMES))
    bars = ax.bar(BEHAVIOR_NAMES, avgs, color=colors, edgecolor="black", linewidth=0.5)
    ax.set_ylabel("Average Turns Survived")
    ax.set_title("Average Survival Time by Behavior Type")
    for bar, avg in zip(bars, avgs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{avg:.1f}", ha="center", va="bottom", fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(charts_dir, "avg_survival_by_behavior.png"), dpi=150)
    plt.close(fig)


def _chart_kd_by_behavior(data: dict, charts_dir: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    avg_kills = []
    avg_deaths = []
    for b in BEHAVIOR_NAMES:
        k = data["kills_by_behavior"][b]
        avg_kills.append(np.mean(k) if k else 0)
        total_agents = len(k)
        deaths = data["deaths_by_behavior"][b]
        avg_deaths.append(deaths / total_agents if total_agents else 0)

    x = np.arange(len(BEHAVIOR_NAMES))
    w = 0.35
    bars1 = ax.bar(x - w / 2, avg_kills, w, label="Avg Kills", color=sns.color_palette("Set2")[0],
                   edgecolor="black", linewidth=0.5)
    bars2 = ax.bar(x + w / 2, avg_deaths, w, label="Death Rate", color=sns.color_palette("Set2")[1],
                   edgecolor="black", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(BEHAVIOR_NAMES)
    ax.set_ylabel("Count")
    ax.set_title("Kill/Death Statistics by Behavior Type")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(charts_dir, "kd_by_behavior.png"), dpi=150)
    plt.close(fig)


def _chart_death_heatmap(data: dict, charts_dir: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 7))
    bins = 20
    w, h = data["map_w"], data["map_h"]
    if len(data["death_xs"]) == 0:
        heatmap_data = np.zeros((bins, bins))
    else:
        heatmap_data, _, _ = np.histogram2d(
            data["death_xs"], data["death_ys"],
            bins=bins, range=[[0, w], [0, h]],
        )
    sns.heatmap(heatmap_data.T, ax=ax, cmap="YlOrRd", cbar_kws={"label": "Deaths"})
    ax.set_title("Death Heatmap (aggregated across all simulations)")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(os.path.join(charts_dir, "death_heatmap.png"), dpi=150)
    plt.close(fig)


def _chart_winner_stats_vs_avg(data: dict, charts_dir: str) -> None:
    """Radar chart comparing winner stats vs average agent stats."""
    angles = np.linspace(0, 2 * np.pi, len(STAT_NAMES), endpoint=False).tolist()
    angles += angles[:1]

    winner_vals = data["avg_winner_stats"].tolist() + [data["avg_winner_stats"][0]]
    avg_vals = data["avg_all_stats"].tolist() + [data["avg_all_stats"][0]]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    ax.plot(angles, winner_vals, "o-", linewidth=2, label="Winners", color="#e74c3c")
    ax.fill(angles, winner_vals, alpha=0.15, color="#e74c3c")
    ax.plot(angles, avg_vals, "o-", linewidth=2, label="All Agents", color="#3498db")
    ax.fill(angles, avg_vals, alpha=0.15, color="#3498db")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(STAT_NAMES, fontsize=10)
    ax.set_title("Winner Stats vs Average Agent", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.15, 1.1))
    fig.tight_layout()
    fig.savefig(os.path.join(charts_dir, "winner_stats_vs_avg.png"), dpi=150)
    plt.close(fig)


def _chart_placement_by_stat_level(data: dict, charts_dir: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    levels = ["low", "mid", "high"]
    x = np.arange(len(STAT_NAMES))
    w = 0.25

    colors = ["#e74c3c", "#f39c12", "#27ae60"]
    for i, level in enumerate(levels):
        vals = [data["placement_by_stat_level"][s][level] for s in STAT_NAMES]
        ax.bar(x + i * w, vals, w, label=f"{level.capitalize()} (0-3/4-6/7-10)",
               color=colors[i], edgecolor="black", linewidth=0.5)

    ax.set_xticks(x + w)
    ax.set_xticklabels(STAT_NAMES)
    ax.set_ylabel("Average Placement (lower is better)")
    ax.set_title("Average Placement by Stat Level")
    ax.legend()
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(os.path.join(charts_dir, "placement_by_stat_level.png"), dpi=150)
    plt.close(fig)


def _write_meta_report(data: dict, results: list[SimulationResult], output_dir: str) -> None:
    """Write the full markdown analysis report."""
    n = data["n"]

    # Best behavior
    best_behavior = max(BEHAVIOR_NAMES, key=lambda b: data["winner_behaviors"].get(b, 0))
    best_behavior_rate = data["winner_behaviors"].get(best_behavior, 0) / n * 100

    # Best dominant stat
    best_stat = max(STAT_NAMES, key=lambda s: data["winner_dominant_stats"].get(s, 0))
    best_stat_rate = data["winner_dominant_stats"].get(best_stat, 0) / n * 100

    # Ideal stat distribution (average of winners)
    ideal_stats = data["avg_winner_stats"]

    # Average turns per game
    avg_turns = np.mean([r.total_turns for r in results])

    lines = [
        f"# Battle Royale Meta Report",
        f"## {n} Simulations Analyzed",
        f"",
        f"**Average game length:** {avg_turns:.1f} turns",
        f"",
        f"---",
        f"",
        f"### Optimal Build",
        f"",
        f"- **Best Behavior Type:** {best_behavior} ({best_behavior_rate:.1f}% win rate)",
        f"- **Best Dominant Stat:** {best_stat} ({best_stat_rate:.1f}% win rate when dominant)",
        f"- **Ideal Stat Distribution:** "
        + " / ".join(f"{STAT_NAMES[i].upper()[:3]}:{ideal_stats[i]:.1f}" for i in range(6)),
        f"",
        f"---",
        f"",
        f"### Win Rates by Behavior Type",
        f"",
        f"| Behavior | Wins | Win Rate | Avg Placement | Avg Kills |",
        f"|----------|------|----------|---------------|-----------|",
    ]

    for b in BEHAVIOR_NAMES:
        wins = data["winner_behaviors"].get(b, 0)
        rate = wins / n * 100
        avg_place = np.mean(data["placements_by_behavior"][b]) if data["placements_by_behavior"][b] else 0
        avg_kills = np.mean(data["kills_by_behavior"][b]) if data["kills_by_behavior"][b] else 0
        lines.append(f"| {b} | {wins} | {rate:.1f}% | {avg_place:.1f} | {avg_kills:.2f} |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"### Stat Correlation with Placement",
        f"",
        f"Negative correlation = higher stat leads to better (lower) placement.",
        f"",
        f"| Stat | Correlation | Effect |",
        f"|------|-------------|--------|",
    ])

    for sname in STAT_NAMES:
        corr = data["stat_placement_corr"][sname]
        direction = "Higher = Better" if corr < -0.01 else ("Higher = Worse" if corr > 0.01 else "Neutral")
        lines.append(f"| {sname} | {corr:.4f} | {direction} |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"### Kill/Death Statistics",
        f"",
        f"| Behavior | Avg Kills | Death Rate |",
        f"|----------|-----------|------------|",
    ])

    for b in BEHAVIOR_NAMES:
        k = data["kills_by_behavior"][b]
        avg_k = np.mean(k) if k else 0
        total = len(k)
        deaths = data["deaths_by_behavior"][b]
        dr = deaths / total * 100 if total else 0
        lines.append(f"| {b} | {avg_k:.2f} | {dr:.1f}% |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"### Charts",
        f"",
        f"![Win Rate by Behavior](charts/win_rate_by_behavior.png)",
        f"![Win Rate by Dominant Stat](charts/win_rate_by_dominant_stat.png)",
        f"![Avg Survival by Behavior](charts/avg_survival_by_behavior.png)",
        f"![K/D by Behavior](charts/kd_by_behavior.png)",
        f"![Death Heatmap](charts/death_heatmap.png)",
        f"![Winner Stats vs Average](charts/winner_stats_vs_avg.png)",
        f"![Placement by Stat Level](charts/placement_by_stat_level.png)",
    ])

    report_path = os.path.join(output_dir, "meta_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def print_summary(data: dict) -> None:
    """Print a brief terminal summary."""
    n = data["n"]
    print(f"\n{'='*50}")
    print(f" BATTLE ROYALE ANALYSIS - {n} simulations")
    print(f"{'='*50}")

    print(f"\n Win rates by behavior:")
    for b in BEHAVIOR_NAMES:
        wins = data["winner_behaviors"].get(b, 0)
        rate = wins / n * 100
        bar = "#" * int(rate / 2)
        print(f"  {b:12s} {rate:5.1f}% {bar}")

    best_behavior = max(BEHAVIOR_NAMES, key=lambda b: data["winner_behaviors"].get(b, 0))
    best_stat = max(STAT_NAMES, key=lambda s: data["winner_dominant_stats"].get(s, 0))

    print(f"\n Best behavior: {best_behavior}")
    print(f" Best dominant stat: {best_stat}")
    print(f"\n Winner avg stats vs overall avg:")
    for i, s in enumerate(STAT_NAMES):
        w = data["avg_winner_stats"][i]
        a = data["avg_all_stats"][i]
        diff = w - a
        sign = "+" if diff >= 0 else ""
        print(f"  {s:12s}  winner: {w:.1f}  avg: {a:.1f}  ({sign}{diff:.1f})")

    print(f"{'='*50}\n")
