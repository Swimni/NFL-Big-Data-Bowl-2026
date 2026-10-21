"""Does the QB throw to the most open receiver? Stats and figures over every pass.

Run: python3 src/analysis.py   (needs data/processed/receivers.csv)
Writes data/processed/summary_stats.json, assets/most_open_vs_random.png,
assets/sep_vs_depth.png. Python 3.9 compatible.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed"
ASSETS = ROOT / "assets"
POSITIONS = ("WR", "TE", "RB")
BG = "#0e1117"
FG = "#eaf0fa"
C_RATE = "#00e676"
C_BASE = "#f5c518"


def load():
    rec = pd.read_csv(OUT / "receivers.csv")
    target = rec[rec.is_target == 1].copy()
    # One row per play: was the targeted receiver also the most open one?
    target["hit"] = target.is_most_open == 1
    return rec, target


def compute(rec, target):
    n = len(target)
    stats = {
        "n_passes": int(n),
        "most_open_rate": float(target.hit.mean()),
        "random_baseline": float((1.0 / target.n_options).mean()),
        "median_sep_target": float(target.separation.median()),
        "median_sep_others": float(rec[rec.is_target == 0].separation.median()),
        "by_target_position": {},
        "by_coverage": {},
        "open_but_ignored_by_position": {},
    }
    for pos in POSITIONS:
        sub = target[target.position == pos]
        stats["by_target_position"][pos] = {
            "n": int(len(sub)),
            "most_open_rate": float(sub.hit.mean()) if len(sub) else 0.0}
    for cov in ("man", "zone"):
        sub = target[target.coverage == cov]
        stats["by_coverage"][cov] = {
            "n": int(len(sub)),
            "most_open_rate": float(sub.hit.mean()) if len(sub) else 0.0}
    # Among plays where the most open man plays position P, how often was he ignored?
    most_open = rec[rec.is_most_open == 1]
    for pos in POSITIONS:
        sub = most_open[most_open.position == pos]
        stats["open_but_ignored_by_position"][pos] = \
            float((sub.is_target == 0).mean()) if len(sub) else 0.0
    return stats


def fig_rates(stats):
    labels = ["All passes"] + list(POSITIONS)
    values = [stats["most_open_rate"]] + [stats["by_target_position"][p]["most_open_rate"]
                                          for p in POSITIONS]
    counts = [stats["n_passes"]] + [stats["by_target_position"][p]["n"] for p in POSITIONS]
    fig, ax = plt.subplots(figsize=(7.6, 4.4), facecolor=BG)
    ax.set_facecolor(BG)
    bars = ax.bar(labels, [100 * v for v in values], color=C_RATE, width=0.6)
    ax.axhline(100 * stats["random_baseline"], color=C_BASE, linestyle="--", linewidth=2,
               label="random pick (%.0f%%)" % (100 * stats["random_baseline"]))
    for bar, value, count in zip(bars, values, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, 100 * value + 1.2,
                "%.0f%%\nn=%s" % (100 * value, "{:,}".format(count)),
                ha="center", color=FG, fontsize=10)
    ax.set_title("How often did the QB throw to the most open receiver?",
                 color=FG, fontsize=13, pad=12)
    ax.set_ylabel("share of passes (%)", color=FG)
    ax.set_ylim(0, max(100 * max(values) + 12, 100 * stats["random_baseline"] + 12))
    ax.tick_params(colors=FG)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#39415a")
    leg = ax.legend(facecolor=BG, edgecolor="#39415a", labelcolor=FG, loc="upper right")
    leg.get_frame().set_alpha(0.9)
    fig.tight_layout()
    fig.savefig(ASSETS / "most_open_vs_random.png", dpi=150, facecolor=BG)
    plt.close(fig)


def fig_sep_depth(rec):
    fig, ax = plt.subplots(figsize=(7.6, 4.4), facecolor=BG)
    ax.set_facecolor(BG)
    others = rec[rec.is_target == 0]
    target = rec[rec.is_target == 1]
    ax.scatter(others.depth, others.separation, s=3, alpha=0.12, color="#8fa0ba",
               label="not targeted")
    ax.scatter(target.depth, target.separation, s=4, alpha=0.30, color=C_RATE,
               label="targeted")
    mo = rec[rec.is_most_open == 1]
    ax.axhline(mo.separation.median(), color=C_BASE, linestyle="--", linewidth=1.5,
               label="median separation of the most open man (%.1f yd)"
                     % mo.separation.median())
    ax.set_title("The most open man is usually the shallow one", color=FG, fontsize=13, pad=12)
    ax.set_xlabel("depth at the throw (yd past the line of scrimmage)", color=FG)
    ax.set_ylabel("separation (yd)", color=FG)
    ax.set_xlim(-10, 45)
    ax.set_ylim(0, 15)
    ax.tick_params(colors=FG)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#39415a")
    leg = ax.legend(facecolor=BG, edgecolor="#39415a", labelcolor=FG, loc="upper right",
                    markerscale=3, fontsize=9)
    leg.get_frame().set_alpha(0.9)
    fig.tight_layout()
    fig.savefig(ASSETS / "sep_vs_depth.png", dpi=150, facecolor=BG)
    plt.close(fig)


def main():
    ASSETS.mkdir(exist_ok=True)
    rec, target = load()
    stats = compute(rec, target)
    (OUT / "summary_stats.json").write_text(json.dumps(stats, indent=2))

    print("passes analysed        : %s" % "{:,}".format(stats["n_passes"]))
    print("threw to most open     : %.1f%%" % (100 * stats["most_open_rate"]))
    print("random baseline        : %.1f%%" % (100 * stats["random_baseline"]))
    print("median separation      : %.2f yd targeted vs %.2f yd others"
          % (stats["median_sep_target"], stats["median_sep_others"]))
    for pos in POSITIONS:
        d = stats["by_target_position"][pos]
        print("  %-3s targets          : %5s passes, most open %.1f%%"
              % (pos, "{:,}".format(d["n"]), 100 * d["most_open_rate"]))
    for cov in ("man", "zone"):
        d = stats["by_coverage"][cov]
        print("  %-4s coverage        : %5s passes, most open %.1f%%"
              % (cov, "{:,}".format(d["n"]), 100 * d["most_open_rate"]))
    for pos in POSITIONS:
        print("  most open %-3s ignored: %.1f%%"
              % (pos, 100 * stats["open_but_ignored_by_position"][pos]))

    fig_rates(stats)
    fig_sep_depth(rec)
    print("wrote summary_stats.json and 2 figures in assets/")


if __name__ == "__main__":
    main()
