"""
Synthesizer Agent

Job: combine retrieved_chunks + tool_outputs + the original query into one
coherent, cited final answer. This is the one agent that uses the LARGE
model — everything upstream (retrieval, planning, tool dispatch) can run on
the small model, but the final answer quality is what a judge actually
reads, so it gets the bigger model. This is the other half of the mixed
model-routing optimization story.

TODO (next pass):
- Real citation formatting (map answer claims back to retrieved_chunks/tool
  sources)
- Handle the case where tool_outputs or retrieved_chunks are empty/failed
  gracefully instead of hallucinating
"""

from typing import Any, AsyncIterator

from app.agents.base import AgentEvent, AgentResult, BaseAgent, EventType
from app.core.llm_client import llm_client


class SynthesizerAgent(BaseAgent):
    name = "synthesizer"

    async def run(self, context: dict[str, Any]) -> AsyncIterator[AgentEvent | AgentResult]:
        query = context["query"]
        chunks = context.get("retrieved_chunks", [])
        tool_outputs = context.get("tool_outputs", [])

        yield AgentEvent(
            agent_name=self.name,
            event_type=EventType.STARTED,
            detail="Synthesizing final answer",
        )

        yield AgentEvent(
            agent_name=self.name,
            event_type=EventType.THINKING,
            detail="Calling large model to compose answer",
        )

        context_str = "\n".join([c["text"] for c in chunks] + [str(t) for t in tool_outputs])

        # TODO: real synthesis prompt with citation instructions
        result = await llm_client.generate(
            prompt=f"Query: {query}\n\nContext:\n{context_str}\n\nAnswer:",
            size="large",
            system="You are a research assistant. Answer using only the given context. Cite sources.",
        )

        yield AgentEvent(
            agent_name=self.name,
            event_type=EventType.FINISHED,
            detail="Answer ready",
            payload={"tokens_per_second": result.tokens_per_second},
        )

        yield AgentResult(
            agent_name=self.name,
            output=result.text,
            latency_seconds=result.latency_seconds,
            tokens_per_second=result.tokens_per_second,
        )
