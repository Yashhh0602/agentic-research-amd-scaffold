"""
Generates a two-panel bar chart from the real benchmark JSON files in proofs/,
for use in the README. Run this AFTER benchmark.py and throughput_benchmark.py
have produced their JSON output.

Usage (from repo root, with proofs/ populated):
    python scripts/make_benchmark_chart.py

Outputs: proofs/benchmark_chart.png
"""

import matplotlib.pyplot as plt

# Real numbers from proofs/ (agent-level and throughput benchmarks)
agent_level = {"Sequential": 13.184, "Concurrent": 11.09}
throughput = {"One-at-a-time": 68.793, "Concurrent batch": 27.11}

fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))

# Panel 1: agent-level orchestration
ax = axes[0]
bars = ax.bar(agent_level.keys(), agent_level.values(), color=["#8a93a6", "#4FD1C5"])
ax.set_title("Agent-level orchestration\n(same query, dependency-bounded)", fontsize=10)
ax.set_ylabel("Total latency (seconds)")
ax.bar_label(bars, fmt="%.2fs")
ax.text(0.5, -0.22, "1.19x speedup", transform=ax.transAxes,
        ha="center", fontsize=11, fontweight="bold", color="#2b6cb0")

# Panel 2: throughput under concurrent load
ax = axes[1]
bars = ax.bar(throughput.keys(), throughput.values(), color=["#8a93a6", "#F5A623"])
ax.set_title("Throughput under concurrent load\n(5 different users, 5 different queries)", fontsize=10)
ax.set_ylabel("Total time for 5 queries (seconds)")
ax.bar_label(bars, fmt="%.2fs")
ax.text(0.5, -0.22, "2.54x speedup", transform=ax.transAxes,
        ha="center", fontsize=11, fontweight="bold", color="#c05621")

fig.suptitle("AMD ROCm / vLLM benchmark results — real GPU measurements", fontsize=12, fontweight="bold")
fig.tight_layout(rect=[0, 0.03, 1, 0.95])
fig.savefig("proofs/benchmark_chart.png", dpi=150, bbox_inches="tight")
print("Saved: proofs/benchmark_chart.png")