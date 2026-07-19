"""
Orchestrator — coordinates the 4 agents and is the literal implementation
of the "sequential vs concurrent" benchmark toggle described in PROGRESS.md.

Dependency graph (this is the real constraint, not arbitrary):
  - Retriever needs only the query
  - Reasoning needs only the query
    -> Retriever and Reasoning have no dependency on each other, so they
       CAN run concurrently
  - Executor needs the plan (Reasoning's output)
  - Synthesizer needs everything (retrieved_chunks, tool_outputs)

SEQUENTIAL mode: Retriever -> Reasoning -> Executor -> Synthesizer, strictly
one at a time. This is the naive/baseline pipeline — every agent idles
waiting for the previous one, GPU sits idle during the Retriever's DB-only
step, etc.

CONCURRENT mode: Retriever and Reasoning run at the same time
(asyncio.gather), then Executor, then Synthesizer. This is the optimized
pipeline. The measurable ROCm story is: total wall-clock time and GPU
utilization for sequential vs concurrent on the same query, on the pod.

Both modes stream AgentEvents out through `run()` as an async generator so
the API layer can forward them over a WebSocket to the frontend's live
trace panel — the same code path drives both the demo visualization and
the benchmark numbers, which keeps them honest (no separate "demo mode").
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal

from app.agents.base import AgentEvent, AgentResult
from app.agents.executor import ExecutorAgent
from app.agents.reasoning import ReasoningAgent
from app.agents.retriever import RetrieverAgent
from app.agents.synthesizer import SynthesizerAgent

ExecutionMode = Literal["sequential", "concurrent"]


@dataclass
class RunSummary:
    mode: ExecutionMode
    total_latency_seconds: float
    agent_results: list[AgentResult] = field(default_factory=list)
    final_answer: str = ""


class Orchestrator:
    def __init__(self) -> None:
        self.retriever = RetrieverAgent()
        self.reasoning = ReasoningAgent()
        self.executor = ExecutorAgent()
        self.synthesizer = SynthesizerAgent()

    async def run(
        self, query: str, mode: ExecutionMode = "sequential"
    ) -> AsyncIterator[AgentEvent | RunSummary]:
        context: dict[str, Any] = {"query": query}
        start = time.perf_counter()
        results: list[AgentResult] = []

        if mode == "sequential":
            for agent in (self.retriever, self.reasoning, self.executor, self.synthesizer):
                async for item in agent.run(context):
                    if isinstance(item, AgentEvent):
                        yield item
                    else:
                        results.append(item)
        else:
            # Stage 1: Retriever + Reasoning concurrently (no dependency between them)
            async for item in self._run_parallel([self.retriever, self.reasoning], context):
                if isinstance(item, AgentEvent):
                    yield item
                else:
                    results.append(item)

            # Stage 2: Executor (depends on Reasoning's plan)
            async for item in self.executor.run(context):
                if isinstance(item, AgentEvent):
                    yield item
                else:
                    results.append(item)

            # Stage 3: Synthesizer (depends on everything)
            async for item in self.synthesizer.run(context):
                if isinstance(item, AgentEvent):
                    yield item
                else:
                    results.append(item)

        total_latency = time.perf_counter() - start
        final_answer = next(
            (r.output for r in results if r.agent_name == "synthesizer"), ""
        )

        yield RunSummary(
            mode=mode,
            total_latency_seconds=total_latency,
            agent_results=results,
            final_answer=final_answer,
        )

    async def _run_parallel(
        self, agents: list, context: dict[str, Any]
    ) -> AsyncIterator[AgentEvent | AgentResult]:
        """
        Run multiple agents' async generators concurrently and yield items
        as they arrive from any of them, interleaved. Each agent still
        writes into the same shared `context` dict — safe here because
        Retriever and Reasoning write to different keys (retrieved_chunks
        vs plan) and neither reads a key the other writes.
        """
        queue: asyncio.Queue = asyncio.Queue()
        done_count = 0

        async def drain(agent):
            async for item in agent.run(context):
                await queue.put(item)
            await queue.put(None)  # sentinel: this agent is done

        tasks = [asyncio.create_task(drain(agent)) for agent in agents]

        while done_count < len(agents):
            item = await queue.get()
            if item is None:
                done_count += 1
                continue
            yield item

        await asyncio.gather(*tasks)


orchestrator = Orchestrator()
