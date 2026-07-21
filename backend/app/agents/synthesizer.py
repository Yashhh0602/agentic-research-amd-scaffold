"""
Synthesizer Agent
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

        context_str = self._build_context(chunks, tool_outputs)

        result = await llm_client.generate(
            prompt=f"Query: {query}\n\n{context_str}\n\n"
                   f"Answer the query using ONLY the context above. For every factual "
                   f"statement you make, you MUST end that sentence with a citation tag "
                   f"indicating exactly where it came from, in this format: "
                   f"[Source: <source name>] for document chunks, or [Tool: <tool name>] "
                   f"for tool output. If you cannot attach a real citation tag to a "
                   f"statement, do not make that statement at all, even if you believe it "
                   f"is true from general knowledge. If the context does not cover part of "
                   f"the query, write one sentence saying so explicitly, uncited, rather "
                   f"than answering that part yourself. If a tool's exact output is given, "
                   f"report that exact value rather than recalculating or guessing.",
            size="large",
            system="You are a research assistant restricted to a closed-book context. "
                   "Every factual sentence you write must carry a [Source: ...] or "
                   "[Tool: ...] citation tag naming where it came from. A sentence with "
                   "no citation tag is only allowed if it is explicitly stating that the "
                   "context does not cover something. You must not use any knowledge "
                   "outside the given context, even if you are confident it is correct.",
            temperature=0.1,
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

    def _build_context(self, chunks: list[dict], tool_outputs: list[dict]) -> str:
        parts = []

        if chunks:
            parts.append("=== Retrieved document chunks ===")
            for c in chunks:
                source = c.get("source", "unknown")
                parts.append(f"[Source: {source}]\n{c['text']}")

        for t in tool_outputs:
            tool_name = t.get("tool", "unknown")
            if t.get("error"):
                parts.append(f"=== Tool: {tool_name} (FAILED) ===\nError: {t['error']}")
                continue

            result = t.get("result")
            if tool_name == "code_exec" and isinstance(result, dict):
                parts.append(
                    f"=== Tool: code_exec (executed successfully) ===\n"
                    f"stdout: {result.get('stdout', '').strip()}\n"
                    f"stderr: {result.get('stderr', '').strip()}\n"
                    f"exit_code: {result.get('exit_code')}"
                )
            elif tool_name == "web_search" and isinstance(result, list):
                parts.append("=== Tool: web_search results ===")
                for r in result:
                    parts.append(f"- {r.get('title', '')}: {r.get('snippet', '')} ({r.get('url', '')})")
            else:
                parts.append(f"=== Tool: {tool_name} ===\n{result}")

        return "\n\n".join(parts) if parts else "No context retrieved."