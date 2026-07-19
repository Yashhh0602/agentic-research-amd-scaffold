"""
Benchmark script: runs the same query through the orchestrator in both
sequential and concurrent mode, N times each, and logs latency + tokens/sec
per agent to a timestamped file in proofs/. This is the actual evidence
behind the "concurrent beats sequential" claim in the README.

Run this ON THE POD once vLLM is serving (LLM_BACKEND=vllm in your .env) —
running it against local Ollama/CPU will still work mechanically but the
numbers won't mean anything for the ROCm optimization story.

Usage:
    python scripts/benchmark.py --query "your hero demo query" --runs 5
"""

import argparse
import asyncio
import json
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.orchestrator import RunSummary, orchestrator  # noqa: E402


def get_rocm_smi_snapshot() -> str | None:
    """
    Grabs a raw rocm-smi reading if available (only works on the pod, not
    local dev). Returns None instead of crashing if rocm-smi isn't found,
    so this script stays runnable locally for logic-testing too.
    """
    try:
        result = subprocess.run(
            ["rocm-smi", "--showuse", "--showmemuse"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


async def run_once(query: str, mode: str) -> dict:
    summary: RunSummary | None = None
    async for item in orchestrator.run(query, mode=mode):
        if isinstance(item, RunSummary):
            summary = item

    assert summary is not None
    return {
        "mode": summary.mode,
        "total_latency_seconds": round(summary.total_latency_seconds, 3),
        "agents": [
            {
                "agent": r.agent_name,
                "latency_seconds": round(r.latency_seconds, 3),
                "tokens_per_second": r.tokens_per_second,
            }
            for r in summary.agent_results
        ],
    }


async def main(query: str, runs: int, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_file = output_dir / f"benchmark_{timestamp}.json"

    results = {
        "query": query,
        "runs_per_mode": runs,
        "timestamp_utc": timestamp,
        "rocm_smi_before": get_rocm_smi_snapshot(),
        "sequential": [],
        "concurrent": [],
    }

    for mode in ("sequential", "concurrent"):
        print(f"\n=== {mode.upper()} ({runs} runs) ===")
        for i in range(runs):
            print(f"  run {i + 1}/{runs}...", end=" ", flush=True)
            r = await run_once(query, mode)
            results[mode].append(r)
            print(f"{r['total_latency_seconds']}s")

    results["rocm_smi_after"] = get_rocm_smi_snapshot()

    for mode in ("sequential", "concurrent"):
        totals = [r["total_latency_seconds"] for r in results[mode]]
        results[f"{mode}_mean_seconds"] = round(statistics.mean(totals), 3)
        results[f"{mode}_stdev_seconds"] = round(statistics.stdev(totals), 3) if len(totals) > 1 else 0.0

    if results["sequential_mean_seconds"] > 0:
        speedup = results["sequential_mean_seconds"] / results["concurrent_mean_seconds"]
        results["speedup_factor"] = round(speedup, 2)

    output_file.write_text(json.dumps(results, indent=2))

    print(f"\nSaved: {output_file}")
    print(f"Sequential mean: {results['sequential_mean_seconds']}s")
    print(f"Concurrent mean: {results['concurrent_mean_seconds']}s")
    if "speedup_factor" in results:
        print(f"Speedup: {results['speedup_factor']}x")

    if results["rocm_smi_before"] is None:
        print("\nNOTE: rocm-smi not found -- this run did NOT capture real GPU")
        print("telemetry. Fine for local logic-testing, but re-run this ON THE")
        print("POD before using these numbers in the README/proofs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True, help="The hero demo query to benchmark")
    parser.add_argument("--runs", type=int, default=5, help="Runs per mode (default 5)")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "proofs",
    )
    args = parser.parse_args()

    asyncio.run(main(args.query, args.runs, args.output_dir))