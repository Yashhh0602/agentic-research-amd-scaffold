"""
Throughput benchmark: measures how the system handles MULTIPLE SIMULTANEOUS
queries, as opposed to benchmark.py which measures concurrent AGENTS within
a single query. This is where vLLM's continuous batching on GPU actually
shows its advantage -- a single query's agent-level concurrency is limited
by real dependencies (Executor needs Reasoning's plan, etc.), but multiple
independent queries have no such dependency and can be fully parallelized.

Run this ON THE POD once vLLM is serving.

Usage:
    python scripts/throughput_benchmark.py --queries 5
"""

import argparse
import asyncio
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.orchestrator import RunSummary, orchestrator  # noqa: E402

# A handful of distinct queries so results aren't just cache/repeat artifacts
QUERY_POOL = [
    "What are the differences between ROCm's memory model and CUDA's, and what changes are needed to port a CUDA kernel to HIP?",
    "What is coarse-grained versus fine-grained memory coherence in HIP?",
    "How does unified memory management work in HIP?",
    "What are the basic steps to port a CUDA kernel to HIP?",
    "Explain HIP's virtual memory management API.",
]


def get_rocm_smi_snapshot() -> str | None:
    try:
        result = subprocess.run(
            ["rocm-smi", "--showuse", "--showmemuse"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


async def run_one_query(query: str) -> dict:
    start = time.perf_counter()
    summary: RunSummary | None = None
    async for item in orchestrator.run(query, mode="sequential"):
        if isinstance(item, RunSummary):
            summary = item
    elapsed = time.perf_counter() - start
    assert summary is not None
    return {"query": query, "latency_seconds": round(elapsed, 3)}


async def run_sequential_baseline(queries: list[str]) -> dict:
    """One query at a time, waiting for each to fully finish before starting the next."""
    start = time.perf_counter()
    results = []
    for q in queries:
        r = await run_one_query(q)
        results.append(r)
        print(f"    {r['query'][:50]}... -> {r['latency_seconds']}s")
    total = time.perf_counter() - start
    return {"total_wall_seconds": round(total, 3), "per_query": results}


async def run_concurrent_batch(queries: list[str]) -> dict:
    """All queries fired at once, relying on vLLM's batching to serve them together."""
    start = time.perf_counter()
    results = await asyncio.gather(*(run_one_query(q) for q in queries))
    total = time.perf_counter() - start
    for r in results:
        print(f"    {r['query'][:50]}... -> {r['latency_seconds']}s")
    return {"total_wall_seconds": round(total, 3), "per_query": results}


async def main(num_queries: int, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_file = output_dir / f"throughput_{timestamp}.json"

    queries = [QUERY_POOL[i % len(QUERY_POOL)] for i in range(num_queries)]

    print(f"\n=== ONE-AT-A-TIME BASELINE ({num_queries} queries) ===")
    baseline = await run_sequential_baseline(queries)

    print(f"\n=== CONCURRENT BATCH ({num_queries} queries fired simultaneously) ===")
    concurrent = await run_concurrent_batch(queries)

    speedup = round(baseline["total_wall_seconds"] / concurrent["total_wall_seconds"], 2)

    results = {
        "num_queries": num_queries,
        "timestamp_utc": timestamp,
        "rocm_smi_snapshot": get_rocm_smi_snapshot(),
        "one_at_a_time": baseline,
        "concurrent_batch": concurrent,
        "throughput_speedup_factor": speedup,
    }

    output_file.write_text(json.dumps(results, indent=2))

    print(f"\nSaved: {output_file}")
    print(f"One-at-a-time total: {baseline['total_wall_seconds']}s")
    print(f"Concurrent batch total: {concurrent['total_wall_seconds']}s")
    print(f"Throughput speedup: {speedup}x")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=int, default=5, help="Number of simultaneous queries to test")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "proofs",
    )
    args = parser.parse_args()

    asyncio.run(main(args.queries, args.output_dir))