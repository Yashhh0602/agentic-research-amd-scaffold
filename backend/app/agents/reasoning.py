"""
Reasoning Agent

Job: break the user query down into sub-tasks and decide which downstream
agents/tools are needed. This is a SMALL-model call — it's a routing/planning
decision, not the final answer, so it doesn't need the big model. This is
one half of the "mixed model routing" ROCm optimization story (the other
half is that Synthesizer uses the large model).

TODO (next pass):
- Real prompt: ask model to output a structured plan (JSON: list of
  sub-tasks, each tagged with which agent/tool handles it)
- Handle the case where no tool calls are needed (simple factual query)
- Feed retrieved_chunks from context into the planning prompt so the plan
  accounts for what's already known vs what needs external lookup
"""

from typing import Any, AsyncIterator

from app.agents.base import AgentEvent, AgentResult, BaseAgent, EventType
from app.core.llm_client import llm_client


class ReasoningAgent(BaseAgent):
    name = "reasoning"

    async def run(self, context: dict[str, Any]) -> AsyncIterator[AgentEvent | AgentResult]:
        query = context["query"]

        yield AgentEvent(
            agent_name=self.name,
            event_type=EventType.STARTED,
            detail="Decomposing query into sub-tasks",
        )

        yield AgentEvent(
            agent_name=self.name,
            event_type=EventType.THINKING,
            detail="Calling small model to plan sub-tasks",
        )

        # TODO: replace with a real structured-output planning prompt
        result = await llm_client.generate(
            prompt=f"Break this query into sub-tasks: {query}",
            size="small",
            system="You are a planning agent. List concrete sub-tasks needed to answer the query.",
        )

        plan = {"raw_plan": result.text, "needs_web_search": True, "needs_code_exec": False}

        yield AgentEvent(
            agent_name=self.name,
            event_type=EventType.FINISHED,
            detail="Plan ready",
            payload={"tokens_per_second": result.tokens_per_second},
        )

        context["plan"] = plan
        yield AgentResult(
            agent_name=self.name,
            output=plan,
            latency_seconds=result.latency_seconds,
            tokens_per_second=result.tokens_per_second,
        )
